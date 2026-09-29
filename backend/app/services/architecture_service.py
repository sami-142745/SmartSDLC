"""Architecture analysis orchestration.

This is the seam between the deterministic analysis in
:mod:`app.services.architecture_analysis` and the rest of the system. It owns the
concerns that the pure module deliberately does not:

1. **Target selection.** From the provider's tree, pick the source files worth
   reading. Selection is path-based and happens before any download, so a
   repository with 10 000 files of which 300 are analysable costs 300 requests.
2. **Bounded concurrency and partial failure.** Reads are issued under a
   semaphore, and a file that cannot be read is recorded and skipped. One
   unreadable file degrades the graph; it does not end the analysis.
3. **Caching.** Results are stored in the existing ``repository_analysis``
   collection under the ``architecture`` analysis kind, so this module adds no
   new persistence layer.

The service never mutates provider state and never calls a model.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Iterable

from app.schemas.architecture import ArchitectureGraph
from app.services import (
    architecture_analysis,
    architecture_parser,
    repository_analysis_repository,
    security_repository,
)
from app.services.scm import ScmAPIError, ScmProvider, get_scm_client

logger = logging.getLogger(__name__)

#: Concurrent file reads. Matches the security scan so a user running both
#: features against one repository stays inside provider rate limits.
MAX_CONCURRENT_FETCHES = 8

#: Upper bound on source files read per analysis, applied after path screening.
DEFAULT_MAX_FILES = 800

#: Hard ceiling, so a client cannot ask the server to read every file in a
#: 200 000-file monorepo.
HARD_MAX_FILES = 3000

#: Errors reported on the graph, so the payload stays bounded.
MAX_ERRORS_REPORTED = 20

#: Analysis kind used in the shared ``repository_analysis`` cache collection.
CACHE_KIND = "architecture"


class ArchitectureError(Exception):
    """Raised when an analysis cannot start at all."""


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _client(provider: ScmProvider, token: str):
    return get_scm_client(provider.value, token)


def _supports(client: Any, method: str) -> bool:
    return callable(getattr(client, method, None))


def select_analysis_targets(
    tree_entries: Iterable[dict[str, Any]],
    *,
    max_files: int = DEFAULT_MAX_FILES,
) -> tuple[list[str], int]:
    """Choose which repository files an analysis will read.

    Returns ``(paths, skipped)``. A file qualifies when the tree entry is a blob
    and its path is a supported source file outside vendored and generated
    directories. Truncation is explicit and deterministic: the first ``max_files``
    candidates in tree order, so the same tree always yields the same selection.
    """
    paths: list[str] = []
    skipped = 0
    for entry in tree_entries or []:
        if not isinstance(entry, dict):
            continue
        if entry.get("type") not in (None, "blob"):
            continue
        raw_path = entry.get("path")
        if not isinstance(raw_path, str) or not raw_path:
            continue
        path = architecture_parser.normalise_path(raw_path)
        if not path or not architecture_parser.is_analysable_path(path):
            skipped += 1
            continue
        paths.append(path)

    limit = max(1, min(int(max_files or DEFAULT_MAX_FILES), HARD_MAX_FILES))
    if len(paths) > limit:
        skipped += len(paths) - limit
        paths = paths[:limit]
    return paths, skipped


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


async def _fetch(
    client: Any, owner: str, repository: str, path: str, ref: str | None
) -> tuple[str, str | bytes | None, str | None]:
    """Fetch one file. Returns ``(path, content, error)``.

    A missing file is not an error — the tree can be stale relative to the ref —
    so it returns ``None`` content and is left out of ``errors``.
    """
    try:
        content = await client.get_file_content(owner, repository, path, ref=ref)
    except ScmAPIError as error:
        if error.category == "not_found":
            return path, None, None
        return path, None, f"{path}: {error.category}"
    except Exception as exc:  # noqa: BLE001 - one bad file must not fail an analysis
        return path, None, f"{path}: {type(exc).__name__}"
    return path, content, None


async def analyze_repository(
    user_id: int,
    token: str,
    provider: ScmProvider,
    owner: str,
    repository: str,
    *,
    ref: str | None = None,
    max_files: int | None = None,
    refresh: bool = False,
    use_cache: bool = True,
) -> ArchitectureGraph:
    """Analyse a repository's structure and return the graph.

    ``use_cache`` reads a live entry from the shared repository-analysis cache
    first. Caching is a pure optimization: a miss, an expired entry or an
    unavailable database all degrade to a recompute rather than an error.
    """
    if use_cache and not refresh:
        cached = await _read_cache(user_id, owner, repository)
        if cached is not None:
            try:
                return ArchitectureGraph.model_validate(cached)
            except Exception:
                # A cache entry written by an older schema must degrade to a
                # recompute. Letting the validation error escape would let a
                # stale document turn a working analysis into a 500.
                logger.warning("Discarding an unreadable cached graph", exc_info=True)

    client = _client(provider, token)
    if not _supports(client, "get_repository_tree"):
        raise ArchitectureError("This provider does not expose a repository tree.")
    if not _supports(client, "get_file_content"):
        raise ArchitectureError("This provider does not expose repository file content.")

    started = time.perf_counter()
    try:
        tree_payload = await client.get_repository_tree(owner, repository, ref=ref)
    except ScmAPIError as error:
        raise ArchitectureError(
            f"Could not read the repository tree: {error.category}"
        ) from error
    except Exception as exc:  # noqa: BLE001
        raise ArchitectureError("Could not read the repository tree.") from exc

    entries = _tree_entries(tree_payload)
    if not entries:
        raise ArchitectureError("The repository tree is empty or unreadable.")

    limit = max_files if max_files is not None else DEFAULT_MAX_FILES
    targets, skipped = select_analysis_targets(entries, max_files=limit)
    truncated = len(targets) >= max(1, min(limit, HARD_MAX_FILES)) and skipped > 0

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_FETCHES)

    async def guarded(path: str) -> tuple[str, str | bytes | None, str | None]:
        async with semaphore:
            return await _fetch(client, owner, repository, path, ref)

    results = await asyncio.gather(*(guarded(path) for path in targets))

    errors: list[str] = []
    parsed_modules: list[architecture_parser.ParsedModule] = []
    files_read = 0

    for path, content, error in results:
        if error:
            if len(errors) < MAX_ERRORS_REPORTED:
                errors.append(error)
            continue
        if content is None:
            skipped += 1
            continue
        files_read += 1
        module = architecture_parser.parse_module(path, content)
        if module.parse_error and len(errors) < MAX_ERRORS_REPORTED:
            errors.append(f"{path}: {module.parse_error}")
        if module.name:
            parsed_modules.append(module)

    resolution = architecture_parser.resolve(parsed_modules)
    nodes, edges, inventory, issues, summary = architecture_analysis.build_analysis(resolution)

    graph = ArchitectureGraph(
        repository_id=security_repository.repository_id_for(owner, repository),
        owner=owner,
        repository=repository,
        full_name=f"{owner}/{repository}",
        provider=provider.value,
        ref=ref,
        commit_sha=_commit_sha(tree_payload),
        analyzed_at=_utcnow_iso(),
        duration_ms=int((time.perf_counter() - started) * 1000),
        nodes=nodes,
        edges=edges,
        modules=inventory,
        issues=issues,
        summary=summary,
        errors=errors,
        truncated=truncated,
    )

    await _write_cache(user_id, owner, repository, graph)
    logger.info(
        "Architecture analysis for %s/%s: %d modules, %d edges, %d issues",
        owner,
        repository,
        len(nodes),
        len(edges),
        len(issues),
    )
    return graph


async def _read_cache(user_id: int, owner: str, repository: str) -> dict[str, Any] | None:
    """Read a live cached graph, or ``None``.

    Every failure — database down, document written by an older schema, payload
    that no longer validates — is swallowed into a miss. A stale schema must not
    turn a working analysis into a 500.
    """
    try:
        entry = await repository_analysis_repository.get_cached(
            user_id, owner, repository, CACHE_KIND
        )
    except Exception:
        logger.warning("Architecture cache read failed", exc_info=True)
        return None
    if not entry:
        return None
    payload = entry.get("payload")
    if not isinstance(payload, dict):
        return None
    return payload


async def _write_cache(user_id: int, owner: str, repository: str, graph: ArchitectureGraph) -> None:
    """Cache a graph. A write failure is logged, never raised."""
    try:
        await repository_analysis_repository.set_cached(
            user_id, owner, repository, CACHE_KIND, graph.model_dump(mode="json")
        )
    except Exception:
        logger.warning("Architecture cache write failed", exc_info=True)


async def get_architecture(
    user_id: int,
    token: str,
    provider: ScmProvider,
    owner: str,
    repository: str,
    *,
    ref: str | None = None,
    max_files: int | None = None,
    refresh: bool = False,
) -> ArchitectureGraph:
    """Public entry point used by the router."""
    return await analyze_repository(
        user_id,
        token,
        provider,
        owner,
        repository,
        ref=ref,
        max_files=max_files,
        refresh=refresh,
    )


async def invalidate(user_id: int, owner: str, repository: str) -> int:
    """Drop the cached architecture for a repository."""
    return await repository_analysis_repository.invalidate(user_id, owner, repository)
