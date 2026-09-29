"""Dependency & Supply Chain Intelligence orchestration.

Separates the deterministic analysis in :mod:`app.services.supply_chain_analysis`
from the outside world. It owns:

1. **Target selection.** Dependency manifests and lockfiles are chosen from the
   provider tree by path, before any download. There are only a handful of
   recognised filenames, so the cost is one tree walk plus a handful of reads.
2. **Bounded concurrency and partial failure.** Reads run under a semaphore; a
   file that cannot be read is recorded and skipped rather than failing the run.
3. **Caching.** Results live in the shared ``repository_analysis`` collection
   under the ``supply_chain`` analysis kind, so no new persistence layer is
   introduced.

It never mutates provider state and never calls a model. Nothing here consults a
package registry, an advisory feed, or a licence database: every fact in the
report comes from a file in the repository, and the report says so when a file
does not settle a question.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Iterable

from app.schemas.supply_chain import (
    DEFAULT_MAX_DEPENDENCIES,
    SupplyChainDependency,
    SupplyChainManifest,
    SupplyChainReport,
)
from app.services import (
    repository_analysis_repository,
    security_repository,
    supply_chain_analysis,
    supply_chain_parser,
)
from app.services.scm import ScmAPIError, ScmProvider, get_scm_client

logger = logging.getLogger(__name__)

#: Concurrent file reads, matching the architecture, documentation and security
#: engines so a user running several analyses stays inside provider rate limits.
MAX_CONCURRENT_FETCHES = 8

#: Hard ceiling on the inventory. A large lockfile is the normal case for a big
#: project, and truncating it silently would misreport the dependency count, so
#: the cap is generous and reported through ``truncated``.
HARD_MAX_DEPENDENCIES = 20000

#: Extra files read to identify the project's *own* licence, which is reported
#: separately from its dependencies' licences.
MAX_LICENSE_FILES = 2

MAX_ERRORS_REPORTED = 20

CACHE_KIND = "supply_chain"

#: Paths for the repository's own licence, in preference order.
_LICENSE_PATHS: tuple[str, ...] = (
    "LICENSE",
    "LICENSE.md",
    "LICENCE",
    "COPYING",
)


class SupplyChainError(Exception):
    """Raised when an analysis cannot start at all."""


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _client(provider: ScmProvider, token: str):
    return get_scm_client(provider.value, token)


def _supports(client: Any, method: str) -> bool:
    return callable(getattr(client, method, None))


def _tree_entries(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        tree = payload.get("tree")
        if isinstance(tree, list):
            return [item for item in tree if isinstance(item, dict)]
    return []


def _commit_sha(payload: Any) -> str | None:
    if isinstance(payload, dict):
        sha = payload.get("sha")
        if isinstance(sha, str) and sha:
            return sha
    return None


def _known_paths(entries: Iterable[dict[str, Any]]) -> set[str]:
    return {
        entry["path"]
        for entry in entries
        if isinstance(entry, dict) and isinstance(entry.get("path"), str)
    }


async def _fetch(
    client: Any,
    owner: str,
    repository: str,
    path: str,
    ref: str | None,
) -> tuple[str, str | bytes | None, str | None]:
    """Read one file, mapping absence and failure to a reportable outcome."""
    try:
        content = await client.get_file_content(owner, repository, path, ref=ref)
    except ScmAPIError as error:
        if error.category == "not_found":
            return path, None, None
        return path, None, f"{path}: {error.category}"
    except Exception as exc:  # noqa: BLE001 - one bad file must not fail a run
        return path, None, f"{path}: {type(exc).__name__}"
    return path, content, None


def _decode(content: str | bytes | None) -> str | None:
    if content is None:
        return None
    if isinstance(content, bytes):
        try:
            return content.decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001 - decode never fails with replace
            return None
    return content


async def analyze_repository(
    user_id: int,
    token: str,
    provider: ScmProvider,
    owner: str,
    repository: str,
    *,
    ref: str | None = None,
    max_dependencies: int | None = None,
    refresh: bool = False,
    use_cache: bool = True,
) -> SupplyChainReport:
    """Analyse a repository's dependency supply chain and return the report."""
    if use_cache and not refresh:
        cached = await _read_cache(user_id, owner, repository)
        if cached is not None:
            try:
                report = SupplyChainReport.model_validate(cached)
            except Exception:
                logger.warning("Discarding an unreadable cached supply chain report", exc_info=True)
            else:
                report.cached = True
                return report

    client = _client(provider, token)
    if not _supports(client, "get_repository_tree"):
        raise SupplyChainError("This provider does not expose a repository tree.")
    if not _supports(client, "get_file_content"):
        raise SupplyChainError("This provider does not expose repository file content.")

    started = time.perf_counter()
    try:
        tree_payload = await client.get_repository_tree(owner, repository, ref=ref)
    except ScmAPIError as error:
        raise SupplyChainError(
            f"Could not read the repository tree: {error.category}"
        ) from error
    except Exception as exc:  # noqa: BLE001
        raise SupplyChainError("Could not read the repository tree.") from exc

    entries = _tree_entries(tree_payload)
    if not entries:
        raise SupplyChainError("The repository tree is empty or unreadable.")

    known = _known_paths(entries)
    targets = supply_chain_parser.select_targets(entries)

    # The project's own licence is read only when a manifest does not already
    # declare it, and only for a path that actually exists in the tree.
    license_targets = [path for path in _LICENSE_PATHS if path in known][:MAX_LICENSE_FILES]

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_FETCHES)

    async def guarded(path: str) -> tuple[str, str | bytes | None, str | None]:
        async with semaphore:
            return await _fetch(client, owner, repository, path, ref)

    results = await asyncio.gather(
        *(guarded(path) for path in [*targets, *license_targets])
    )
    fetched = {path: (content, error) for path, content, error in results}

    errors: list[str] = []
    manifests: list[SupplyChainManifest] = []
    dependencies: list[SupplyChainDependency] = []
    declared_license: str | None = None

    for path in targets:
        content, error = fetched.get(path, (None, None))
        if error:
            if len(errors) < MAX_ERRORS_REPORTED:
                errors.append(error)
            continue
        text = _decode(content)
        if text is None:
            continue
        manifest, rows, project_license = supply_chain_parser.parse_file(path, text)
        manifests.append(manifest)
        dependencies.extend(rows)
        if declared_license is None and project_license is not None:
            declared_license = project_license

    for path in license_targets:
        if declared_license is not None:
            break
        content, error = fetched.get(path, (None, None))
        if error:
            if len(errors) < MAX_ERRORS_REPORTED:
                errors.append(error)
            continue
        text = _decode(content)
        if text is None:
            continue
        expression = supply_chain_parser.project_license_expression(path, text)
        if expression is not None:
            declared_license = expression

    # A repository with no dependency files is a result the page can explain,
    # not an error, so the expected-but-absent manifests are reported instead.
    if not manifests:
        manifests = supply_chain_parser.missing_manifest(
            supply_chain_parser.MANIFEST_FILES
        )

    limit = (
        max_dependencies
        if max_dependencies is not None
        else DEFAULT_MAX_DEPENDENCIES
    )
    limit = max(1, min(limit, HARD_MAX_DEPENDENCIES))
    truncated = len(dependencies) > limit
    if truncated:
        dependencies = dependencies[:limit]

    licenses, issues, summary = supply_chain_analysis.build_analysis(
        manifests, dependencies, declared_license=declared_license
    )

    report = SupplyChainReport(
        repository_id=security_repository.repository_id_for(owner, repository),
        owner=owner,
        repository=repository,
        full_name=f"{owner}/{repository}",
        provider=provider.value,
        ref=ref,
        commit_sha=_commit_sha(tree_payload),
        analyzed_at=_utcnow_iso(),
        duration_ms=int((time.perf_counter() - started) * 1000),
        manifests=manifests,
        dependencies=dependencies,
        licenses=licenses,
        issues=issues,
        summary=summary,
        errors=errors,
        truncated=truncated,
    )

    await _write_cache(user_id, owner, repository, report)
    logger.info(
        "Supply chain analysis for %s/%s: %d dependencies (%d direct, %d transitive), "
        "%d licences, %d issues, score %d (%s)",
        owner,
        repository,
        summary.total_dependencies,
        summary.direct_dependencies,
        summary.transitive_dependencies,
        len(licenses),
        len(issues),
        summary.hygiene_score,
        summary.score_band,
    )
    return report


async def _read_cache(user_id: int, owner: str, repository: str) -> dict[str, Any] | None:
    try:
        entry = await repository_analysis_repository.get_cached(
            user_id, owner, repository, CACHE_KIND
        )
    except Exception:
        logger.warning("Supply chain cache read failed", exc_info=True)
        return None
    if not entry:
        return None
    payload = entry.get("payload")
    return payload if isinstance(payload, dict) else None


async def _write_cache(
    user_id: int, owner: str, repository: str, report: SupplyChainReport
) -> None:
    try:
        await repository_analysis_repository.set_cached(
            user_id, owner, repository, CACHE_KIND, report.model_dump(mode="json")
        )
    except Exception:
        logger.warning("Supply chain cache write failed", exc_info=True)


async def get_supply_chain(
    user_id: int,
    token: str,
    provider: ScmProvider,
    owner: str,
    repository: str,
    *,
    ref: str | None = None,
    max_dependencies: int | None = None,
    refresh: bool = False,
) -> SupplyChainReport:
    """Public entry point used by the router."""
    return await analyze_repository(
        user_id,
        token,
        provider,
        owner,
        repository,
        ref=ref,
        max_dependencies=max_dependencies,
        refresh=refresh,
    )


async def invalidate(user_id: int, owner: str, repository: str) -> int:
    return await repository_analysis_repository.invalidate(user_id, owner, repository)
