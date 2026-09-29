"""HTTP surface for the Security Intelligence Engine.

Authentication
--------------
Every route requires a signed-in user (``get_current_user``), and every route
that touches a repository also requires a connected SCM token
(``require_github_token``) because scanning reads live provider content.
Reads of an existing scan and its posture need only the user: they never call
the provider, so demanding a token for them would make stored results
unreadable after a token is disconnected.

Ownership
---------
Scan and finding reads pass ``user_id`` into the repository layer, which filters
on it in the query. A scan belonging to another user is indistinguishable from a
scan that does not exist — both return ``404 {"detail": "Scan not found"}``. The
same 404 covers a malformed id, so the response cannot be used to probe which
scan ids are real.

Route registration
------------------
The router is mounted twice by :mod:`app.main`: at the root, matching every
other router in this app, and under ``/api``, matching the documented public
contract. Both registrations hit the same handlers.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.schemas.security import (
    CATEGORIES,
    SCANNERS,
    SEVERITIES,
    CreateSecurityScanRequest,
    RepositoryPosture,
    SecurityExplanation,
    SecurityFindingsResponse,
    SecurityScan,
)
from app.services import security_explanation_service, security_scan_service
from app.services.security_scan_service import SecurityScanError
from app.services.scm import ScmAPIError, ScmProvider, scm_error_response
from app.services.security import get_current_user, require_github_token

router = APIRouter()

BASE = "/security"

#: Cap on a single findings page. A client wanting everything pages through.
MAX_FINDINGS_PAGE = 500

_SCAN_NOT_FOUND = "Scan not found"


def _not_found() -> HTTPException:
    """The single 404 used for every unreadable scan.

    Missing, malformed and unauthorized all produce this identical response so
    the endpoint reveals nothing about scan existence.
    """
    return HTTPException(status_code=404, detail=_SCAN_NOT_FOUND)


@router.get(f"{BASE}/scanners", response_model=dict[str, Any])
async def list_scanners(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """The rule catalogues the engine actually runs.

    Returned so the UI can explain coverage without duplicating a rule list on
    the frontend, and so a reader can tell which findings a scan *could*
    produce versus which the provider consulted.
    """
    from app.services import (  # noqa: PLC0415 - imported lazily to keep the router import light
        security_code_scanner,
        security_dependency_scanner,
        security_secret_scanner,
    )

    return {
        "secret": security_secret_scanner.rule_summary(),
        "code": security_code_scanner.rule_summary(),
        "dependency": security_dependency_scanner.rule_summary(),
        "severities": list(SEVERITIES),
        "categories": list(CATEGORIES),
        "scanners": list(SCANNERS),
    }


@router.post(f"{BASE}/scans", response_model=SecurityScan, status_code=201)
async def create_security_scan(
    payload: CreateSecurityScanRequest,
    user: dict[str, Any] = Depends(get_current_user),
    token: str = Depends(require_github_token),
) -> SecurityScan:
    """Scan a repository and return the stored result with its findings.

    The scan is synchronous: the caller waits for the findings. A long scan
    surfaces as a provider error rather than as a queued job the client has no
    way to poll.
    """
    try:
        provider = ScmProvider(payload.provider)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Unsupported provider") from exc

    try:
        return await security_scan_service.scan_repository(
            user["github_id"],
            token,
            provider,
            payload.owner,
            payload.repository,
            ref=payload.ref,
            max_files=payload.max_files,
        )
    except SecurityScanError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ScmAPIError as exc:
        raise scm_error_response(provider, exc)


@router.get(f"{BASE}/scans", response_model=list[SecurityScan])
async def list_security_scans(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: dict[str, Any] = Depends(get_current_user),
) -> list[SecurityScan]:
    """Recent scans for the signed-in user, newest first, without findings."""
    return await security_scan_service.list_scans(
        user["github_id"], limit=limit, offset=offset
    )


@router.get(f"{BASE}/scans/{{scan_id}}", response_model=SecurityScan)
async def get_security_scan(
    scan_id: str,
    include_findings: bool = Query(True),
    user: dict[str, Any] = Depends(get_current_user),
) -> SecurityScan:
    """Read one scan and, by default, its findings."""
    scan = await security_scan_service.get_scan(
        user["github_id"], scan_id, include_findings=include_findings
    )
    if scan is None:
        raise _not_found()
    return scan


@router.get(f"{BASE}/scans/{{scan_id}}/findings", response_model=SecurityFindingsResponse)
async def list_scan_findings(
    scan_id: str,
    severity: str | None = Query(None),
    category: str | None = Query(None),
    scanner: str | None = Query(None),
    file: str | None = Query(None, min_length=1),
    limit: int = Query(200, ge=1, le=MAX_FINDINGS_PAGE),
    offset: int = Query(0, ge=0),
    user: dict[str, Any] = Depends(get_current_user),
) -> SecurityFindingsResponse:
    """Read findings for a scan, optionally filtered.

    An unknown filter value is a 422 rather than an empty list: a client that
    misspells ``severity=critial`` should learn about it, not conclude the
    repository is clean.
    """
    if severity is not None and severity.lower() not in SEVERITIES:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown severity '{severity}'. Expected one of: {', '.join(SEVERITIES)}",
        )
    if category is not None and category.lower() not in CATEGORIES:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown category '{category}'. Expected one of: {', '.join(CATEGORIES)}",
        )
    if scanner is not None and scanner.lower() not in SCANNERS:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown scanner '{scanner}'. Expected one of: {', '.join(SCANNERS)}",
        )

    # Confirm the scan is readable by this user before returning a filtered
    # page, so a filter on someone else's scan is a 404 rather than an empty
    # 200 that implies "no findings matched".
    scan = await security_scan_service.get_scan(
        user["github_id"], scan_id, include_findings=False
    )
    if scan is None:
        raise _not_found()

    findings = await security_scan_service.list_findings(
        user["github_id"],
        scan_id,
        severity=severity.lower() if severity else None,
        category=category.lower() if category else None,
        scanner=scanner.lower() if scanner else None,
        file=file,
        limit=limit,
        offset=offset,
    )
    total = await security_scan_service.count_findings(
        user["github_id"],
        scan_id,
        severity=severity.lower() if severity else None,
        category=category.lower() if category else None,
        scanner=scanner.lower() if scanner else None,
        file=file,
    )
    return SecurityFindingsResponse(scan_id=scan_id, total=total, findings=findings)


@router.get(
    f"{BASE}/findings/{{finding_id}}/explanation",
    response_model=SecurityExplanation,
)
async def explain_security_finding(
    finding_id: str,
    user: dict[str, Any] = Depends(get_current_user),
) -> SecurityExplanation:
    """Optional Gemini prose for one finding.

    The finding must belong to a scan this user can read; the lookup is scoped by
    ``user_id`` so a finding from another user's scan is a 404 like any other.

    This endpoint never returns 502 when the model is unavailable. The scanner
    already produced the finding, and a missing explanation is a degraded
    response, not a failed request.
    """
    finding = await security_scan_service.get_finding(user["github_id"], finding_id)
    if finding is None:
        raise _not_found()
    return await security_explanation_service.explain_finding(finding)


@router.get(
    f"{BASE}/repositories/{{owner}}/{{repository}}/posture",
    response_model=RepositoryPosture,
)
async def get_repository_posture(
    owner: str,
    repository: str,
    user: dict[str, Any] = Depends(get_current_user),
) -> RepositoryPosture:
    """Posture for one repository.

    A repository that has never been scanned returns ``200`` with
    ``has_scan=false`` and a zeroed summary rather than a 404: "not scanned
    yet" is a state the page renders, not an error.
    """
    return await security_scan_service.get_posture(
        user["github_id"], owner, repository
    )
