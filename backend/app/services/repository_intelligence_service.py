"""Orchestration for the Repository Intelligence module.

This service is the single entry point the router talks to. It owns three
concerns and delegates everything else:

1. **Provider access** — resolves the SCM client for the request and calls the
   narrow capability it needs. Providers are not assumed to implement every
   capability: GitLab exposes the tree and file reads but not the rich
   repository profile, language census or README endpoint, so those analyses
   degrade to an explicit "not available for this provider" result instead of
   failing the request.
2. **Caching** — every public analysis goes through :func:`_cached_or_compute`,
   which reads the MongoDB cache, computes on a miss, and writes the result
   back. Cache access is fully guarded: a database outage costs a slower
   response, never an error, because each analysis is recomputable from the
   provider.
3. **Composition** — :func:`get_dashboard` assembles profile, health,
   languages, dependencies and README into a single response, fetching the
   independent parts concurrently.

Analysis granularity
--------------------
The five sub-analyses can also be requested individually. That matters because
they have very different costs: a language census is a single cheap call, while
the dependency inspector probes four manifest paths. Endpoints for a single
analysis accept ``refresh`` to bypass the cache on demand.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, TypeVar

from app.schemas.repository_intelligence import (
    DependencyReport,
    LanguageBreakdown,
    ReadmeIntelligence,
    RepositoryDashboard,
    RepositoryFileContent,
    RepositoryHealth,
    RepositoryProfile,
    RepositoryTree,
)
from app.services import (
    repository_analysis_repository,
    repository_dependency_service,
    repository_explorer_service,
    repository_health_service,
    repository_language_service,
    repository_readme_service,
)
from app.services.scm import ScmAPIError, ScmProvider, get_scm_client

logger = logging.getLogger(__name__)

T = TypeVar("T")

ANALYSIS_PROFILE = "profile"
ANALYSIS_DASHBOARD = "dashboard"
ANALYSIS_HEALTH = "health"
ANALYSIS_LANGUAGES = "languages"
ANALYSIS_DEPENDENCIES = "dependencies"
ANALYSIS_README = "readme"
ANALYSIS_TREE = "tree"


class RepositoryIntelligenceError(Exception):
    """Raised when repository intelligence cannot be produced at all."""


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _client(provider: ScmProvider, token: str):
    return get_scm_client(provider.value, token)


# ---------------------------------------------------------------------------
# Cache plumbing
# ---------------------------------------------------------------------------


async def _read_cache(
    user_id: int,
    owner: str,
    repository: str,
    analysis: str,
    model: type[T],
) -> T | None:
    """Return a validated cached model, or None on miss/expiry/corruption."""
    try:
        doc = await repository_analysis_repository.get_cached(
            user_id, owner, repository, analysis
        )
    except Exception:
        logger.warning("Repository analysis cache read failed", exc_info=True)
        return None

    if doc is None:
        return None

    payload = doc.get("payload")
    if payload is None:
        return None

    try:
        instance = model.model_validate(payload)
    except Exception:
        logger.warning("Discarding corrupt cache entry %s", analysis, exc_info=True)
        return None

    # Mark the response as cache-derived so the UI can show it.
    if hasattr(instance, "cached"):
        instance.cached = True
    return instance


async def _write_cache(
    user_id: int,
    owner: str,
    repository: str,
    analysis: str,
    instance: Any,
) -> None:
    try:
        await repository_analysis_repository.set_cached(
            user_id,
            owner,
            repository,
            analysis,
            instance.model_dump(mode="json"),
        )
    except Exception:
        logger.warning("Repository analysis cache write failed", exc_info=True)


async def _cached_or_compute(
    *,
    user_id: int,
    owner: str,
    repository: str,
    analysis: str,
    model: type[T],
    compute: Callable[[], Awaitable[T]],
    refresh: bool = False,
) -> T:
    if not refresh:
        cached = await _read_cache(user_id, owner, repository, analysis, model)
        if cached is not None:
            return cached

    instance = await compute()
    if hasattr(instance, "cached"):
        instance.cached = False
    await _write_cache(user_id, owner, repository, analysis, instance)
    return instance


# ---------------------------------------------------------------------------
# Capability helpers
# ---------------------------------------------------------------------------


def _supports(client: Any, method: str) -> bool:
    return callable(getattr(client, method, None))


async def _fetch_optional(
    client: Any,
    method: str,
    *args: Any,
    **kwargs: Any,
) -> tuple[bool, Any, str | None]:
    """Call an optional client method, classifying a 404 as "no such data".

    Returns ``(found, value, reason)``. A missing capability and a 404 both
    yield ``found=False`` with a reason, because from the caller's perspective
    they mean the same thing: this analysis has no data. Any other provider
    error is re-raised so genuine failures still surface as 5xx.
    """
    if not _supports(client, method):
        return False, None, f"This provider does not expose repository {method.replace('get_repository_', '')} data."

    try:
        result = await getattr(client, method)(*args, **kwargs)
    except ScmAPIError as error:
        if error.category == "not_found":
            return False, None, error.message
        raise
    return True, result, None


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


async def get_profile(
    user_id: int,
    token: str,
    provider: ScmProvider,
    owner: str,
    repo: str,
    *,
    refresh: bool = False,
) -> RepositoryProfile:
    client = _client(provider, token)

    async def compute() -> RepositoryProfile:
        found, payload, reason = await _fetch_optional(
            client, "get_repository_profile", owner, repo
        )
        if not found or not isinstance(payload, dict):
            raise RepositoryIntelligenceError(
                reason or "Repository metadata is not available for this repository."
            )
        normalized = dict(payload)
        normalized.setdefault("owner", owner)
        normalized.setdefault("repository", repo)
        return RepositoryProfile.model_validate(normalized)

    return await _cached_or_compute(
        user_id=user_id,
        owner=owner,
        repository=repo,
        analysis="profile",
        model=RepositoryProfile,
        compute=compute,
        refresh=refresh,
    )


# ---------------------------------------------------------------------------
# Individual analyses
# ---------------------------------------------------------------------------


async def _readme_payload(
    user_id: int,
    token: str,
    provider: ScmProvider,
    owner: str,
    repo: str,
) -> tuple[str | None, str | None]:
    """Fetch README text plus the reason it is absent, for the health signal."""
    client = _client(provider, token)
    found, raw, reason = await _fetch_optional(client, "get_readme", owner, repo)
    if not found:
        return None, reason or "No README is published for this repository."
    if not isinstance(raw, str) or not raw.strip():
        return None, "The README is empty."
    return raw, None


async def get_readme(
    user_id: int,
    token: str,
    provider: ScmProvider,
    owner: str,
    repo: str,
    *,
    refresh: bool = False,
) -> ReadmeIntelligence:
    async def compute() -> ReadmeIntelligence:
        raw, reason = await _readme_payload(user_id, token, provider, owner, repo)
        return repository_readme_service.build_readme_intelligence(
            raw, owner=owner, repository=repo, reason=reason
        )

    return await _cached_or_compute(
        user_id=user_id,
        owner=owner,
        repository=repo,
        analysis="readme",
        model=ReadmeIntelligence,
        compute=compute,
        refresh=refresh,
    )


async def get_health(
    user_id: int,
    token: str,
    provider: ScmProvider,
    owner: str,
    repo: str,
    *,
    refresh: bool = False,
) -> RepositoryHealth:
    async def compute() -> RepositoryHealth:
        profile: dict[str, Any] | None = None
        try:
            profile_model = await get_profile(user_id, token, provider, owner, repo)
            profile = profile_model.model_dump()
        except RepositoryIntelligenceError:
            profile = None

        has_readme: bool | None
        try:
            raw, _ = await _readme_payload(user_id, token, provider, owner, repo)
            has_readme = raw is not None
        except ScmAPIError:
            has_readme = None

        return repository_health_service.compute_health(
            profile,
            has_readme=has_readme,
            now=datetime.now(timezone.utc),
            owner=owner,
            repository=repo,
        )

    return await _cached_or_compute(
        user_id=user_id,
        owner=owner,
        repository=repo,
        analysis="health",
        model=RepositoryHealth,
        compute=compute,
        refresh=refresh,
    )


async def get_languages(
    user_id: int,
    token: str,
    provider: ScmProvider,
    owner: str,
    repo: str,
    *,
    refresh: bool = False,
) -> LanguageBreakdown:
    async def compute() -> LanguageBreakdown:
        client = _client(provider, token)
        found, payload, _ = await _fetch_optional(
            client, "get_repository_languages", owner, repo
        )
        return repository_language_service.build_language_breakdown(
            payload if found else None,
            owner=owner,
            repository=repo,
        )

    return await _cached_or_compute(
        user_id=user_id,
        owner=owner,
        repository=repo,
        analysis="languages",
        model=LanguageBreakdown,
        compute=compute,
        refresh=refresh,
    )


async def get_dependencies(
    user_id: int,
    token: str,
    provider: ScmProvider,
    owner: str,
    repo: str,
    *,
    refresh: bool = False,
) -> DependencyReport:
    async def compute() -> DependencyReport:
        client = _client(provider, token)
        candidates = repository_dependency_service.CANDIDATE_MANIFESTS

        async def fetch(path: str) -> tuple[str, str | None]:
            try:
                content = await client.get_file_content(owner, repo, path)
            except ScmAPIError as error:
                if error.category == "not_found":
                    return path, None
                raise
            return path, content

        results = await asyncio.gather(*(fetch(path) for path, _ in candidates))
        contents = {path: content for path, content in results if content is not None}

        return repository_dependency_service.build_dependency_report(
            contents, owner=owner, repository=repo
        )

    return await _cached_or_compute(
        user_id=user_id,
        owner=owner,
        repository=repo,
        analysis="dependencies",
        model=DependencyReport,
        compute=compute,
        refresh=refresh,
    )


async def get_tree(
    user_id: int,
    token: str,
    provider: ScmProvider,
    owner: str,
    repo: str,
    *,
    ref: str | None = None,
    refresh: bool = False,
) -> RepositoryTree:
    client = _client(provider, token)

    if not _supports(client, "get_repository_tree"):
        return RepositoryTree(
            owner=owner,
            repository=repo,
            ref=ref,
            truncated=False,
            total_files=0,
            total_directories=0,
            total_bytes=0,
            entries=[],
        )

    async def compute() -> RepositoryTree:
        payload = await client.get_repository_tree(owner, repo, ref=ref)
        return repository_explorer_service.build_tree(
            payload, owner=owner, repository=repo, ref=ref
        )

    # The tree is ref-specific, so it is cached under the ref it was fetched at.
    analysis_key = ANALYSIS_TREE if not ref else f"{ANALYSIS_TREE}:{ref}"

    if not refresh:
        try:
            doc = await repository_analysis_repository.get_cached(
                user_id, owner, repo, analysis_key
            )
        except Exception:
            logger.warning("Repository tree cache read failed", exc_info=True)
            doc = None
        if doc is not None and isinstance(doc.get("payload"), dict):
            try:
                tree = RepositoryTree.model_validate(doc["payload"])
                tree.cached = True
                return tree
            except Exception:
                logger.warning("Discarding corrupt tree cache entry", exc_info=True)

    tree = await compute()
    await _write_cache(user_id, owner, repo, analysis_key, tree)
    return tree


async def get_file(
    user_id: int,
    token: str,
    provider: ScmProvider,
    owner: str,
    repo: str,
    path: str,
    *,
    ref: str | None = None,
) -> RepositoryFileContent:
    client = _client(provider, token)
    if not _supports(client, "get_file_content"):
        raise RepositoryIntelligenceError(
            "This provider does not support reading repository files."
        )
    try:
        raw = await client.get_file_content(owner, repo, path, ref=ref)
    except ScmAPIError as error:
        if error.category == "not_found":
            raise RepositoryIntelligenceError(f"{path} was not found in this repository.")
        raise
    return repository_explorer_service.build_file_content(raw, path)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


async def get_dashboard(
    user_id: int,
    token: str,
    provider: ScmProvider,
    owner: str,
    repo: str,
    *,
    refresh: bool = False,
) -> RepositoryDashboard:
    """Compose the full repository intelligence dashboard.

    The five components are fetched concurrently. Individual components are
    allowed to degrade — a provider without a language census still yields a
    dashboard with an empty breakdown rather than a failed request — so each
    task is wrapped to fall back to an empty, explicitly-marked result.
    """

    async def compute() -> RepositoryDashboard:
        try:
            profile = await get_profile(
                user_id, token, provider, owner, repo, refresh=refresh
            )
        except RepositoryIntelligenceError:
            profile = RepositoryProfile(
                owner=owner,
                repository=repo,
                name=repo,
                full_name=f"{owner}/{repo}",
            )

        async def safe(coro: Awaitable[Any], fallback: Any) -> Any:
            try:
                return await coro
            except (RepositoryIntelligenceError, ScmAPIError):
                logger.info(
                    "Repository intelligence component unavailable for %s/%s", owner, repo
                )
                return fallback

        health, languages, dependencies, readme = await asyncio.gather(
            safe(
                get_health(user_id, token, provider, owner, repo, refresh=refresh),
                repository_health_service.compute_health(
                    None, owner=owner, repository=repo
                ),
            ),
            safe(
                get_languages(user_id, token, provider, owner, repo, refresh=refresh),
                repository_language_service.build_language_breakdown(
                    None, owner=owner, repository=repo
                ),
            ),
            safe(
                get_dependencies(user_id, token, provider, owner, repo, refresh=refresh),
                repository_dependency_service.build_dependency_report(
                    None, owner=owner, repository=repo
                ),
            ),
            safe(
                get_readme(user_id, token, provider, owner, repo, refresh=refresh),
                repository_readme_service.build_readme_intelligence(
                    None, owner=owner, repository=repo
                ),
            ),
        )

        return RepositoryDashboard(
            owner=owner,
            repository=repo,
            profile=profile,
            health=health,
            languages=languages,
            dependencies=dependencies,
            readme=readme,
            generated_at=_utcnow_iso(),
            cached=False,
        )

    return await _cached_or_compute(
        user_id=user_id,
        owner=owner,
        repository=repo,
        analysis=ANALYSIS_DASHBOARD,
        model=RepositoryDashboard,
        compute=compute,
        refresh=refresh,
    )


async def invalidate(user_id: int, owner: str, repo: str) -> int:
    """Drop every cached analysis for one repository."""
    try:
        return await repository_analysis_repository.invalidate(user_id, owner, repo)
    except Exception:
        logger.warning("Repository analysis cache invalidation failed", exc_info=True)
        return 0


async def list_cached_repositories(user_id: int) -> list[dict[str, Any]]:
    """Repositories with at least one live cache entry."""
    try:
        return await repository_analysis_repository.list_cached_repositories(user_id)
    except Exception:
        logger.warning("Repository analysis cache listing failed", exc_info=True)
        return []
