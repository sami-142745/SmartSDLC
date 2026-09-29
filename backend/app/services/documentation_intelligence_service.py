"""Documentation Intelligence orchestration.

Separates the deterministic analysis in
:mod:`app.services.documentation_analysis` from the outside world. It owns:

1. **Target selection.** Documentation files and source files are chosen from the
   provider tree by path, before any download, so a large repository costs a
   bounded number of requests.
2. **Bounded concurrency and partial failure.** Reads run under a semaphore; a
   file that cannot be read is recorded and skipped rather than failing the run.
3. **Caching.** Results live in the shared ``repository_analysis`` collection
   under the ``documentation`` analysis kind, so no new persistence layer is
   introduced.

It never mutates provider state and never calls a model.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Iterable

from app.schemas.documentation_intelligence import DocumentationIntelligence
from app.services import (
    documentation_analysis,
    documentation_parser,
    repository_analysis_repository,
    security_repository,
)
from app.services.scm import ScmAPIError, ScmProvider, get_scm_client

logger = logging.getLogger(__name__)

#: Concurrent file reads, matching the architecture and security engines so a
#: user running several analyses stays inside provider rate limits.
MAX_CONCURRENT_FETCHES = 8

#: Documentation files read per analysis.
DEFAULT_MAX_DOC_FILES = 200

#: Source files read to measure docstring coverage. Coverage is a ratio, so a
#: large sample is enough and reading every file would not change the signal.
DEFAULT_MAX_SOURCE_FILES = 200

#: Hard ceiling on either category, so a client cannot ask the server to read an
#: entire monorepo.
HARD_MAX_FILES = 2000

MAX_ERRORS_REPORTED = 20

CACHE_KIND = "documentation"

#: Path prefixes whose source files are most representative of the project.
_SOURCE_PRIORITY_PREFIXES = (
    "src/",
    "app/",
    "backend/",
    "frontend/",
    "lib/",
    "core/",
    "server/",
    "packages/",
    "internal/",
)

#: Documentation kinds, most important first, so a capped selection keeps the
#: files a reader most needs.
_DOC_KIND_PRIORITY = {
    "readme": 0,
    "license": 1,
    "changelog": 1,
    "contributing": 2,
    "security_policy": 2,
    "code_of_conduct": 2,
    "api_reference": 3,
    "guide": 3,
    "tutorial": 3,
    "adr": 4,
    "documentation": 4,
    "other": 5,
}


class DocumentationIntelligenceError(Exception):
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


def _doc_priority(path: str) -> tuple[int, str]:
    return (_DOC_KIND_PRIORITY.get(documentation_parser.documentation_kind(path), 5), path)


def _source_priority(path: str) -> tuple[int, str]:
    priority = 0 if path.startswith(_SOURCE_PRIORITY_PREFIXES) else 1
    return (priority, path)


def select_targets(
    tree_entries: Iterable[dict[str, Any]],
    *,
    max_doc_files: int = DEFAULT_MAX_DOC_FILES,
    max_source_files: int = DEFAULT_MAX_SOURCE_FILES,
) -> tuple[list[str], list[str], int, frozenset[str], bool]:
    """Choose which files to read.

    Returns ``(doc_paths, coverage_paths, source_file_count, existing_paths,
    truncated)``. ``existing_paths`` is every non-ignored blob in the tree, used
    only to decide whether a relative documentation link resolves. Selection is
    deterministic: candidates are ordered by a fixed priority then by path.
    """
    existing: set[str] = set()
    doc_candidates: list[str] = []
    source_candidates: list[str] = []

    for entry in tree_entries or []:
        if not isinstance(entry, dict):
            continue
        if entry.get("type") not in (None, "blob"):
            continue
        raw_path = entry.get("path")
        if not isinstance(raw_path, str) or not raw_path:
            continue
        path = documentation_parser.normalise_path(raw_path)
        if not path:
            continue
        if documentation_parser.is_documentation_path(path):
            existing.add(path)
            doc_candidates.append(path)
        elif documentation_parser.is_source_path(path):
            existing.add(path)
            source_candidates.append(path)

    doc_limit = max(1, min(int(max_doc_files or DEFAULT_MAX_DOC_FILES), HARD_MAX_FILES))
    source_limit = max(1, min(int(max_source_files or DEFAULT_MAX_SOURCE_FILES), HARD_MAX_FILES))

    truncated = len(doc_candidates) > doc_limit or len(source_candidates) > source_limit

    doc_paths = sorted(doc_candidates, key=_doc_priority)[:doc_limit]
    coverage_paths = sorted(source_candidates, key=_source_priority)[:source_limit]
    return doc_paths, coverage_paths, len(source_candidates), frozenset(existing), truncated


async def _fetch(
    client: Any, owner: str, repository: str, path: str, ref: str | None
) -> tuple[str, str | bytes | None, str | None]:
    try:
        content = await client.get_file_content(owner, repository, path, ref=ref)
    except ScmAPIError as error:
        if error.category == "not_found":
            return path, None, None
        return path, None, f"{path}: {error.category}"
    except Exception as exc:  # noqa: BLE001 - one bad file must not fail a run
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
) -> DocumentationIntelligence:
    """Analyse a repository's documentation and return the report."""
    if use_cache and not refresh:
        cached = await _read_cache(user_id, owner, repository)
        if cached is not None:
            try:
                return DocumentationIntelligence.model_validate(cached)
            except Exception:
                logger.warning("Discarding an unreadable cached documentation report", exc_info=True)

    client = _client(provider, token)
    if not _supports(client, "get_repository_tree"):
        raise DocumentationIntelligenceError("This provider does not expose a repository tree.")
    if not _supports(client, "get_file_content"):
        raise DocumentationIntelligenceError("This provider does not expose repository file content.")

    started = time.perf_counter()
    try:
        tree_payload = await client.get_repository_tree(owner, repository, ref=ref)
    except ScmAPIError as error:
        raise DocumentationIntelligenceError(
            f"Could not read the repository tree: {error.category}"
        ) from error
    except Exception as exc:  # noqa: BLE001
        raise DocumentationIntelligenceError("Could not read the repository tree.") from exc

    entries = _tree_entries(tree_payload)
    if not entries:
        raise DocumentationIntelligenceError("The repository tree is empty or unreadable.")

    limit = max_files if max_files is not None else DEFAULT_MAX_DOC_FILES
    doc_paths, coverage_paths, source_count, existing_paths, truncated = select_targets(
        entries,
        max_doc_files=limit,
        max_source_files=limit,
    )

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_FETCHES)

    async def guarded(path: str) -> tuple[str, str | bytes | None, str | None]:
        async with semaphore:
            return await _fetch(client, owner, repository, path, ref)

    doc_results, source_results = await asyncio.gather(
        asyncio.gather(*(guarded(path) for path in doc_paths)),
        asyncio.gather(*(guarded(path) for path in coverage_paths)),
    )

    errors: list[str] = []
    assets = []
    coverage_rows = []

    for path, content, error in doc_results:
        if error:
            if len(errors) < MAX_ERRORS_REPORTED:
                errors.append(error)
            continue
        if content is None:
            continue
        assets.append(
            documentation_parser.parse_documentation(
                path, content, existing_paths=existing_paths
            )
        )

    for path, content, error in source_results:
        if error:
            if len(errors) < MAX_ERRORS_REPORTED:
                errors.append(error)
            continue
        if content is None:
            continue
        row = documentation_parser.parse_source_coverage(path, content)
        if row is not None:
            coverage_rows.append(row)

    gaps, summary = documentation_analysis.build_analysis(
        assets, coverage_rows, source_files=source_count
    )

    report = DocumentationIntelligence(
        repository_id=security_repository.repository_id_for(owner, repository),
        owner=owner,
        repository=repository,
        full_name=f"{owner}/{repository}",
        provider=provider.value,
        ref=ref,
        commit_sha=_commit_sha(tree_payload),
        analyzed_at=_utcnow_iso(),
        duration_ms=int((time.perf_counter() - started) * 1000),
        assets=assets,
        coverage=coverage_rows,
        gaps=gaps,
        summary=summary,
        errors=errors,
        truncated=truncated,
    )

    await _write_cache(user_id, owner, repository, report)
    logger.info(
        "Documentation analysis for %s/%s: %d assets, %d gaps, score %d",
        owner,
        repository,
        len(assets),
        len(gaps),
        summary.coverage_score,
    )
    return report


async def _read_cache(user_id: int, owner: str, repository: str) -> dict[str, Any] | None:
    try:
        entry = await repository_analysis_repository.get_cached(
            user_id, owner, repository, CACHE_KIND
        )
    except Exception:
        logger.warning("Documentation cache read failed", exc_info=True)
        return None
    if not entry:
        return None
    payload = entry.get("payload")
    return payload if isinstance(payload, dict) else None


async def _write_cache(
    user_id: int, owner: str, repository: str, report: DocumentationIntelligence
) -> None:
    try:
        await repository_analysis_repository.set_cached(
            user_id, owner, repository, CACHE_KIND, report.model_dump(mode="json")
        )
    except Exception:
        logger.warning("Documentation cache write failed", exc_info=True)


async def get_documentation_intelligence(
    user_id: int,
    token: str,
    provider: ScmProvider,
    owner: str,
    repository: str,
    *,
    ref: str | None = None,
    max_files: int | None = None,
    refresh: bool = False,
) -> DocumentationIntelligence:
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
    return await repository_analysis_repository.invalidate(user_id, owner, repository)
