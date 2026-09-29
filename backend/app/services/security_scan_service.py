"""Repository security scan orchestration.

This is the seam between the deterministic engines and the rest of the system.
It owns four concerns and delegates the rest:

1. **Target selection.** From the provider's tree, decide which files to read.
   Selection is path-based and happens *before* any download, so a repository
   with 10 000 files of which 40 are scannable costs 40 provider calls.
2. **Bounded concurrency.** File reads are issued with a semaphore. Without a
   bound, a 5 000-file scan would open 5 000 concurrent HTTP requests and get
   the whole request rate-limited, failing a scan that should have succeeded.
3. **Partial failure.** A file that cannot be read is recorded in ``errors`` and
   the scan completes. Losing one unreadable file is strictly better than
   failing a scan that has already produced 200 findings.
4. **Determinism.** Files are read concurrently but the findings are sorted by
   the normalizer afterwards, so a scan's output does not depend on which
   request finished first.

Scanning never mutates provider state and never calls a model.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable

from app.schemas.security import (
    RepositoryPosture,
    SecurityFinding,
    SecurityScan,
)
from app.services import (
    security_code_scanner,
    security_dependency_scanner,
    security_normalizer,
    security_repository,
    security_risk_service,
    security_secret_scanner,
    security_sources,
)
from app.services.scm import ScmAPIError, ScmProvider, get_scm_client

logger = logging.getLogger(__name__)

#: Concurrent file reads. Eight keeps a large scan inside provider rate limits
#: while still using the available bandwidth; a single-file repository is
#: unaffected.
MAX_CONCURRENT_FETCHES = 8

#: Upper bound on files read per scan, applied after path screening. A request
#: may lower it via ``max_files``; nothing may raise it above this.
DEFAULT_MAX_FILES = 600

#: Hard ceiling, so a client cannot ask the server to read 100 000 files.
HARD_MAX_FILES = 2000

#: Stated in every scan response so a reader knows what coverage they have.
METHODOLOGY = (
    "Deterministic rule and pattern analysis. No model participates in severity "
    "assignment, scoring, or the existence of any finding. Known-CVE coverage "
    "depends on the configured vulnerability provider."
)

MAX_ERRORS_REPORTED = 20


class SecurityScanError(Exception):
    """Raised when a scan cannot run at all (provider unavailable, no repo)."""


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _client(provider: ScmProvider, token: str):
    return get_scm_client(provider.value, token)


def _supports(client: Any, method: str) -> bool:
    return callable(getattr(client, method, None))


def select_scan_targets(
    tree_entries: Iterable[dict[str, Any]],
    *,
    max_files: int = DEFAULT_MAX_FILES,
) -> tuple[list[str], int]:
    """Choose which repository files a scan will read.

    Returns ``(paths, skipped_count)``. Three filters apply, in increasing
    order of cost:

    * the entry must be a blob (``type`` absent or ``"blob"``, since the GitHub
      trees API omits the type for blobs in some responses);
    * the path must pass :func:`app.services.security_sources.is_ignored_path`;
    * the path must be a recognised code/config/manifest file.

    The third filter is what keeps the count low on a real repository: a
    repository of 8 000 files typically yields well under 200 scannable ones
    once vendored, generated and binary paths are removed.

    Truncation is explicit. When the candidate list exceeds ``max_files`` the
    result is the first ``max_files`` candidates in tree order, which is stable
    across runs for the same tree — a scan is reproducible, not arbitrary.
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
        path = security_sources.normalize_path_for_scan(raw_path)
        if not path:
            continue
        if security_sources.is_ignored_path(path):
            skipped += 1
            continue
        if not (
            security_code_scanner.is_code_path(path)
            or security_sources.is_manifest_path(path)
        ):
            skipped += 1
            continue
        paths.append(path)

    limit = max(1, min(int(max_files or DEFAULT_MAX_FILES), HARD_MAX_FILES))
    if len(paths) > limit:
        skipped += len(paths) - limit
        paths = paths[:limit]
    return paths, skipped


def _tree_entries(payload: Any) -> list[dict[str, Any]]:
    """Extract the entry list from a provider tree payload.

    Handles both provider shapes: GitHub returns ``{"tree": [...]}`` and GitLab
    returns ``{"tree": [...]}`` as well, but a client may hand back a bare list
    in tests. Anything unrecognised yields an empty list, which surfaces as
    "nothing to scan" rather than a crash.
    """
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        tree = payload.get("tree")
        if isinstance(tree, list):
            return [item for item in tree if isinstance(item, dict)]
    return []


def _entry_size(path: str, entries: dict[str, dict[str, Any]]) -> int:
    entry = entries.get(path) or {}
    size = entry.get("size")
    return int(size) if isinstance(size, (int, float)) else 0


def _commit_sha(payload: Any) -> str | None:
    """Best-effort commit SHA from a tree payload, for scan provenance."""
    if isinstance(payload, dict):
        sha = payload.get("sha")
        if isinstance(sha, str) and sha:
            return sha
    return None


async def _fetch(
    client: Any, owner: str, repository: str, path: str, ref: str | None
) -> tuple[str, str | None, str | None]:
    """Fetch one file. Returns ``(path, content, error)``.

    A missing file is not an error — the tree can be stale relative to the ref —
    so it is reported as ``None`` content and left out of ``errors``.
    """
    try:
        content = await client.get_file_content(owner, repository, path, ref=ref)
    except ScmAPIError as error:
        if error.category == "not_found":
            return path, None, None
        return path, None, f"{path}: {error.category}"
    except Exception as exc:  # noqa: BLE001 - a single bad file must not fail a scan
        return path, None, f"{path}: {type(exc).__name__}"
    if content is None:
        return path, None, None
    if isinstance(content, bytes):
        try:
            content = content.decode("utf-8", errors="replace")
        except Exception:
            return path, None, f"{path}: undecodable"
    return path, str(content), None


async def scan_repository(
    user_id: int,
    token: str,
    provider: ScmProvider,
    owner: str,
    repository: str,
    *,
    ref: str | None = None,
    max_files: int | None = None,
    persist: bool = True,
) -> SecurityScan:
    """Run the full pipeline and return the stored scan.

    Raises :class:`SecurityScanError` only when the scan cannot start — a
    provider without a tree capability, or a tree request that fails. Everything
    after that point degrades into ``errors`` on a completed scan.
    """
    client = _client(provider, token)
    if not _supports(client, "get_repository_tree"):
        raise SecurityScanError("This provider does not expose a repository tree.")
    if not _supports(client, "get_file_content"):
        raise SecurityScanError("This provider does not expose repository file content.")

    started = time.perf_counter()
    try:
        tree_payload = await client.get_repository_tree(owner, repository, ref=ref)
    except ScmAPIError as error:
        raise SecurityScanError(
            f"Could not read the repository tree: {error.category}"
        ) from error
    except Exception as exc:  # noqa: BLE001
        raise SecurityScanError("Could not read the repository tree.") from exc

    entries = _tree_entries(tree_payload)
    if not entries:
        raise SecurityScanError("The repository tree is empty or unreadable.")

    entry_index = {
        str(entry.get("path", "")).replace("\\", "/"): entry
        for entry in entries
        if isinstance(entry.get("path"), str)
    }
    limit = max_files if max_files is not None else DEFAULT_MAX_FILES
    targets, skipped = select_scan_targets(entries, max_files=limit)

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_FETCHES)

    async def guarded(path: str) -> tuple[str, str | None, str | None]:
        async with semaphore:
            return await _fetch(client, owner, repository, path, ref)

    results = await asyncio.gather(*(guarded(path) for path in targets))

    errors: list[str] = []
    payloads: list[dict[str, Any]] = []
    manifests: dict[str, str] = {}
    files_scanned = 0

    for path, content, error in results:
        if error:
            if len(errors) < MAX_ERRORS_REPORTED:
                errors.append(error)
            continue
        if content is None:
            skipped += 1
            continue
        size = _entry_size(path, entry_index)
        lines = security_sources.extract_source_lines(content, path)
        if not lines:
            skipped += 1
            continue
        files_scanned += 1

        if security_sources.is_manifest_path(path):
            manifests[path] = content

        for match in security_secret_scanner.DEFAULT_SECRET_SCANNER.scan_lines(path, lines):
            payloads.append(match.as_finding())
        for match in security_code_scanner.DEFAULT_CODE_SCANNER.scan_lines(path, lines):
            payload = match.as_finding()
            payload["rule_id"] = match.rule_id
            payloads.append(payload)

    dependency_matches, dependency_count, vulnerability_source = (
        await security_dependency_scanner.scan_dependencies(manifests)
    )
    for match in dependency_matches:
        payloads.append(match.as_finding())

    repository_id = security_repository.repository_id_for(owner, repository)
    findings = security_normalizer.normalize_findings(payloads, repository_id=repository_id)

    summary = security_risk_service.summarize(
        findings,
        files_scanned=files_scanned,
        files_skipped=skipped,
        dependencies_analyzed=dependency_count,
    )
    duration_ms = int((time.perf_counter() - started) * 1000)

    scan = SecurityScan(
        scan_id=uuid.uuid4().hex,
        status="complete",
        repository_id=repository_id,
        owner=owner,
        repository=repository,
        full_name=f"{owner}/{repository}",
        provider=provider.value,
        ref=ref,
        commit_sha=_commit_sha(tree_payload),
        summary=summary,
        findings=findings,
        errors=errors,
        duration_ms=duration_ms,
        scanned_at=_utcnow_iso(),
    )

    if persist:
        try:
            await security_repository.save_scan(user_id=user_id, scan=scan, findings=findings)
        except Exception:
            logger.warning("Failed to persist security scan", exc_info=True)
            errors.append("scan completed but could not be stored")

    scan = scan.model_copy(
        update={"errors": errors, "vulnerability_source": vulnerability_source}
    )
    return scan


async def get_scan(
    user_id: int, scan_id: str, *, include_findings: bool = True
) -> SecurityScan | None:
    """Read a scan owned by ``user_id``, or ``None``."""
    return await security_repository.get_scan(
        user_id, scan_id, include_findings=include_findings
    )


async def list_findings(
    user_id: int,
    scan_id: str,
    *,
    severity: str | None = None,
    category: str | None = None,
    scanner: str | None = None,
    file: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[SecurityFinding]:
    """Read filtered findings for a scan owned by ``user_id``."""
    return await security_repository.findings_for_scan(
        user_id,
        scan_id,
        severity=severity,
        category=category,
        scanner=scanner,
        file=file,
        limit=limit,
        offset=offset,
    )


async def count_findings(
    user_id: int,
    scan_id: str,
    *,
    severity: str | None = None,
    category: str | None = None,
    scanner: str | None = None,
    file: str | None = None,
) -> int:
    return await security_repository.count_findings(
        user_id, scan_id, severity=severity, category=category, scanner=scanner, file=file
    )


async def get_posture(
    user_id: int, owner: str, repository: str
) -> RepositoryPosture:
    """Posture for one repository, or an explicit unscanned state.

    A repository that has never been scanned is *not* an error: the response
    carries ``has_scan=False`` and a zeroed summary, so the page can prompt for
    a scan rather than showing a failure.
    """
    repository_id = security_repository.repository_id_for(owner, repository)
    scan = await security_repository.latest_scan(user_id, owner, repository)
    if scan is None:
        return RepositoryPosture(
            repository_id=repository_id,
            owner=owner,
            repository=repository,
            full_name=f"{owner}/{repository}",
            has_scan=False,
            methodology=METHODOLOGY,
        )
    return RepositoryPosture(
        repository_id=repository_id,
        owner=scan.owner,
        repository=scan.repository,
        full_name=scan.full_name,
        has_scan=True,
        scan_id=scan.scan_id,
        scanned_at=scan.scanned_at,
        summary=scan.summary,
        methodology=METHODOLOGY,
    )


async def list_scans(user_id: int, *, limit: int = 20, offset: int = 0) -> list[SecurityScan]:
    return await security_repository.list_scans(user_id, limit=limit, offset=offset)


async def get_finding(user_id: int, finding_id: str) -> SecurityFinding | None:
    """Read one finding owned by ``user_id``, or ``None``.

    Scoped by ``user_id`` in the query, so a finding from another user's scan is
    indistinguishable from one that does not exist.
    """
    return await security_repository.get_finding(user_id, finding_id)
