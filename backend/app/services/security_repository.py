"""MongoDB persistence for security scans and findings.

Document shapes
---------------
``security_scans``
    One document per completed scan: identity (``user_id``/``owner``/
    ``repository``), the provider coordinates it was taken from, the computed
    :class:`~app.schemas.security.SecurityRiskSummary`, and the error list from
    any scanner that degraded. Findings are **not** stored here — they live in
    their own collection so a findings query with filters does not have to load
    a risk summary of unrelated size.

``security_findings``
    One document per finding, carrying the full
    :class:`~app.schemas.security.SecurityFinding` payload plus ``scan_id`` and
    the owning ``user_id``.

Why two collections
-------------------
A scan is read far more often than a finding: posture pages read the summary for
every repository, while a findings read is one scan with a filter. Splitting
them keeps the common read small and gives findings their own indexes. The
trade-off is that a scan's finding list requires a second query, which
:func:`findings_for_scan` performs and the service awaits.

Ownership
---------
Every read takes ``user_id`` explicitly and filters on it in the query, never in
Python after the fact. A missing scan and a scan belonging to another user are
indistinguishable to the caller — the query simply does not match — which is the
same 404 contract the Sprint 3 review routes use.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.schemas.security import SecurityFinding, SecurityScan
from app.services.database import get_db

SCAN_COLLECTION = "security_scans"
FINDING_COLLECTION = "security_findings"

#: Bumped when the stored finding shape changes incompatibly. Kept explicit so a
#: migration can find affected documents rather than guessing.
SCHEMA_VERSION = 1


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _scans():
    return get_db()[SCAN_COLLECTION]


def _findings():
    return get_db()[FINDING_COLLECTION]


async def ensure_indexes() -> None:
    """Create the indexes the read paths depend on.

    Called from the application lifespan. Each index serves a specific query:
    scan-by-id for ownership, latest-scan-per-repository for posture, and the
    compound finding index for filtered finding reads.
    """
    db = get_db()
    await db[SCAN_COLLECTION].create_index("scan_id", name="idx_security_scan_id", unique=True)
    await db[SCAN_COLLECTION].create_index(
        [("user_id", 1), ("owner", 1), ("repository", 1), ("scanned_at", -1)],
        name="idx_security_scan_repository",
    )
    await db[SCAN_COLLECTION].create_index(
        [("user_id", 1), ("owner", 1), ("repository", 1)],
        name="idx_security_scan_identity",
    )
    # Serves the posture read. It keys on the normalized ``repository_id`` rather
    # than ``owner``/``repository`` so a differently-cased request still matches
    # the stored scan, which is what keeps one repository to one posture.
    await db[SCAN_COLLECTION].create_index(
        [("user_id", 1), ("repository_id", 1), ("scanned_at", -1)],
        name="idx_security_scan_repository_id",
    )
    await db[FINDING_COLLECTION].create_index(
        [("user_id", 1), ("scan_id", 1)],
        name="idx_security_finding_scan",
    )
    # Serves the default findings read: filter within a scan, ordered by the
    # canonical sort order (severity rank, then location).
    await db[FINDING_COLLECTION].create_index(
        [("user_id", 1), ("scan_id", 1), ("severity", 1), ("file", 1), ("line", 1)],
        name="idx_security_finding_filter",
    )
    # Serves the single-finding read used by the explanation endpoint.
    await db[FINDING_COLLECTION].create_index(
        "finding_id", name="idx_security_finding_id", unique=True
    )
    await db[FINDING_COLLECTION].create_index(
        [("user_id", 1), ("repository_id", 1), ("fingerprint", 1)],
        name="idx_security_finding_fingerprint",
    )


def repository_id_for(owner: str, repository: str) -> str:
    """Stable identifier for a repository.

    Lowercased because GitHub treats owner/repo case-insensitively, so two
    spellings of the same repository must not produce two postures.
    """
    return f"{str(owner).strip().lower()}/{str(repository).strip().lower()}"


async def save_scan(
    *,
    user_id: int,
    scan: SecurityScan,
    findings: list[SecurityFinding],
) -> SecurityScan:
    """Persist a scan and its findings, replacing any previous scan's findings.

    A new scan supersedes the old one for the same repository: the previous
    scan's findings are deleted so a stale finding cannot be counted in a later
    posture. The previous scan document itself is kept for history.
    """
    now = _utcnow()

    # A finding read by id is a real access path (the explanation endpoint), so
    # every persisted finding must carry one. An id that arrives empty is filled
    # here rather than trusted from the caller.
    stored_findings: list[SecurityFinding] = []
    for finding in findings:
        if not finding.finding_id:
            finding = finding.model_copy(update={"finding_id": uuid.uuid4().hex})
        stored_findings.append(finding)

    scan_document = {
        "scan_id": scan.scan_id,
        "schema_version": scan.schema_version or SCHEMA_VERSION,
        "user_id": user_id,
        "repository_id": scan.repository_id,
        "owner": scan.owner,
        "repository": scan.repository,
        "full_name": scan.full_name,
        "provider": scan.provider,
        "ref": scan.ref,
        "commit_sha": scan.commit_sha,
        "status": scan.status,
        "summary": scan.summary.as_response(),
        "errors": list(scan.errors),
        "duration_ms": scan.duration_ms,
        "scanned_at": scan.scanned_at,
        "vulnerability_source": scan.vulnerability_source,
        "created_at": now,
    }

    if stored_findings:
        finding_documents = [
            {
                **finding.as_response(),
                "user_id": user_id,
                "scan_id": scan.scan_id,
                "repository_id": scan.repository_id,
                "created_at": finding.created_at or now,
            }
            for finding in stored_findings
        ]
        await _findings().insert_many(finding_documents)

    await _scans().insert_one(scan_document)
    return scan.model_copy(update={"findings": stored_findings})


async def get_scan(
    user_id: int, scan_id: str, *, include_findings: bool = True
) -> SecurityScan | None:
    """Return one scan owned by ``user_id``, or ``None``.

    The ownership filter is part of the query, so another user's scan is
    indistinguishable from a missing one.
    """
    if not scan_id:
        return None
    document = await _scans().find_one({"scan_id": scan_id, "user_id": user_id})
    if document is None:
        return None

    findings: list[SecurityFinding] = []
    if include_findings:
        findings = await findings_for_scan(user_id, scan_id)

    return SecurityScan(
        scan_id=document.get("scan_id", ""),
        schema_version=document.get("schema_version", SCHEMA_VERSION),
        status=document.get("status", "complete"),
        repository_id=document.get("repository_id", ""),
        owner=document.get("owner", ""),
        repository=document.get("repository", ""),
        full_name=document.get("full_name", ""),
        provider=document.get("provider", "github"),
        ref=document.get("ref"),
        commit_sha=document.get("commit_sha"),
        summary=_summary_from_document(document.get("summary")),
        findings=findings,
        errors=list(document.get("errors") or []),
        duration_ms=document.get("duration_ms"),
        scanned_at=document.get("scanned_at"),
        vulnerability_source=document.get("vulnerability_source", "none"),
    )


async def latest_scan(user_id: int, owner: str, repository: str) -> SecurityScan | None:
    """Most recent scan for a repository, without its findings."""
    return await get_scan(
        user_id,
        await _latest_scan_id(user_id, owner, repository),
        include_findings=False,
    )


async def _latest_scan_id(user_id: int, owner: str, repository: str) -> str:
    # Matched on the normalized ``repository_id`` rather than the raw
    # ``owner``/``repository`` pair: the stored values keep the spelling the
    # provider returned, so a request that spells the repository differently
    # (``OctoCat/Hello-World`` vs ``octocat/hello-world``) would otherwise miss
    # the scan it already owns and report a false "never scanned" posture.
    document = await _scans().find_one(
        {
            "user_id": user_id,
            "repository_id": repository_id_for(owner, repository),
            "status": "complete",
        },
        sort=[("scanned_at", -1), ("created_at", -1)],
    )
    return (document or {}).get("scan_id", "")


async def findings_for_scan(
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
    """Read findings for one scan with optional validated filters.

    The sort mirrors :func:`app.services.security_normalizer.sort_key` closely
    enough to be stable and useful (severity, then location) without paying for
    a computed field on every document.
    """
    if not scan_id:
        return []
    query: dict[str, Any] = {"user_id": user_id, "scan_id": scan_id}
    if severity:
        query["severity"] = severity
    if category:
        query["category"] = category
    if scanner:
        query["scanner"] = scanner
    if file:
        query["file"] = file

    cursor = (
        _findings()
        .find(query)
        .sort(
            [
                ("severity", 1),
                ("confidence", -1),
                ("file", 1),
                ("line", 1),
                ("fingerprint", 1),
            ]
        )
        .skip(max(0, offset))
    )
    if limit is not None:
        cursor = cursor.limit(max(1, limit))

    results: list[SecurityFinding] = []
    async for document in cursor:
        finding = _finding_from_document(document)
        if finding is not None:
            results.append(finding)

    # The database sort orders by the severity *string*, which is alphabetical
    # and therefore not the canonical critical-high-medium order. Re-sorting in
    # Python makes the response order identical on every backend and matches the
    # order a scan returns, so a client sees the same sequence whether it read
    # one scan or a filtered page of findings.
    from app.services.security_normalizer import sort_key  # noqa: PLC0415

    return sorted(results, key=sort_key)


async def get_finding(user_id: int, finding_id: str) -> SecurityFinding | None:
    """Read one finding by id, scoped to its owner."""
    if not finding_id:
        return None
    document = await _findings().find_one({"finding_id": finding_id, "user_id": user_id})
    if document is None:
        return None
    return _finding_from_document(document)


async def count_findings(
    user_id: int,
    scan_id: str,
    *,
    severity: str | None = None,
    category: str | None = None,
    scanner: str | None = None,
    file: str | None = None,
) -> int:
    """Count findings matching a filter set, for a paginated response."""
    if not scan_id:
        return 0
    query: dict[str, Any] = {"user_id": user_id, "scan_id": scan_id}
    if severity:
        query["severity"] = severity
    if category:
        query["category"] = category
    if scanner:
        query["scanner"] = scanner
    if file:
        query["file"] = file
    return int(await _findings().count_documents(query))


async def repository_posture(
    user_id: int, owner: str, repository: str
) -> tuple[SecurityScan | None, str]:
    """Return ``(latest_scan, repository_id)`` for a repository."""
    return await latest_scan(user_id, owner, repository), repository_id_for(owner, repository)


async def list_scans(
    user_id: int, *, limit: int = 20, offset: int = 0
) -> list[SecurityScan]:
    """Recent scans for a user, newest first, without findings."""
    cursor = (
        _scans()
        .find({"user_id": user_id})
        .sort([("created_at", -1)])
        .skip(max(0, offset))
        .limit(max(1, limit))
    )
    results: list[SecurityScan] = []
    async for document in cursor:
        results.append(
            SecurityScan(
                scan_id=document.get("scan_id", ""),
                schema_version=document.get("schema_version", SCHEMA_VERSION),
                status=document.get("status", "complete"),
                repository_id=document.get("repository_id", ""),
                owner=document.get("owner", ""),
                repository=document.get("repository", ""),
                full_name=document.get("full_name", ""),
                provider=document.get("provider", "github"),
                ref=document.get("ref"),
                commit_sha=document.get("commit_sha"),
                summary=_summary_from_document(document.get("summary")),
                errors=list(document.get("errors") or []),
                duration_ms=document.get("duration_ms"),
                scanned_at=document.get("scanned_at"),
                vulnerability_source=document.get("vulnerability_source", "none"),
            )
        )
    return results


def _summary_from_document(raw: Any) -> Any:
    """Rebuild a summary, tolerating a partial or older stored document.

    A missing or partial summary must not break a posture read: it degrades to
    zeros, which the page renders as "no findings" rather than erroring.
    """
    from app.schemas.security import SecurityRiskSummary  # noqa: PLC0415

    if not isinstance(raw, dict):
        return SecurityRiskSummary()
    allowed = set(SecurityRiskSummary.model_fields)
    return SecurityRiskSummary(**{k: v for k, v in raw.items() if k in allowed})


def _finding_from_document(document: dict[str, Any]) -> SecurityFinding | None:
    """Rebuild a finding, dropping the ownership columns on the way in.

    ``model_config`` forbids extra fields, so the document's ``_id``,
    ``user_id`` and ``scan_id`` have to be removed rather than passed through.
    """
    payload = {
        key: value
        for key, value in document.items()
        if key not in ("_id", "user_id", "scan_id")
    }
    try:
        return SecurityFinding(**payload)
    except Exception:
        # A document written by an older schema should not fail the whole read.
        return None
