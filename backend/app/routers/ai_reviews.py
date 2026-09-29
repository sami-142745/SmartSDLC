"""HTTP surface for Sprint 3 AI pull-request reviews.

Three endpoints, registered twice — at the root and under ``/api`` — so both the
codebase's existing root-mounted convention and the documented ``/api`` paths
resolve to the same handlers (see :func:`app.main.create_app`).

Authentication and provider-error mapping match the rest of the review surface:
``require_github_token`` supplies the provider credential, ``get_current_user``
scopes the review to the caller, and provider failures go through
:func:`app.services.scm.scm_error_response` so a provider auth problem never
logs the user out of SmartSDLC.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.schemas.ai_review import (
    AI_CATEGORIES,
    AI_SEVERITIES,
    CreateReviewRequest,
    Review,
    ReviewFinding,
    ReviewFindingsResponse,
)
from app.services import ai_review_repository, ai_review_service
from app.services.scm import ScmAPIError, ScmProvider, get_scm_client, scm_error_response
from app.services.security import get_current_user, require_github_token

router = APIRouter()


@router.post("/reviews", response_model=Review, status_code=201)
async def create_review(
    payload: CreateReviewRequest,
    token: str = Depends(require_github_token),
    user: dict = Depends(get_current_user),
) -> Review:
    """Run a full AI review of a pull request and persist the result.

    Returns 201 even when the AI leg failed: the diff was still analyzed and a
    usable review was stored, with ``ai_status`` and ``error`` explaining what
    the model did. A 5xx here means the provider lookup itself failed.
    """
    provider = ScmProvider(payload.provider)
    client = get_scm_client(provider, token)
    try:
        return await ai_review_service.run_ai_review(
            client,
            payload.owner,
            payload.repository,
            payload.pull_request_number,
            provider=provider,
            user_id=user["github_id"],
        )
    except ScmAPIError as exc:
        raise scm_error_response(provider, exc)


async def _require_document(review_id: str, user_id: int):
    """Load a review that the caller owns, or raise a 404.

    The ownership filter lives in the query, not in a check after the fetch,
    so another account's review is never loaded into the process in the first
    place. The 404 is deliberately identical for "not yours" and "does not
    exist": distinguishing them would turn review ids into an oracle for
    enumerating other users' reviews.
    """
    document = await ai_review_repository.find_review_by_id(review_id, user_id=user_id)
    if document is None:
        # Also covers a malformed id, which `to_object_id` reports as absent.
        raise HTTPException(status_code=404, detail="Review not found")
    return document


@router.get("/reviews/{review_id}", response_model=Review)
async def get_review(
    review_id: str,
    token: str = Depends(require_github_token),
    user: dict = Depends(get_current_user),
) -> Review:
    """Fetch one review by id, with its files, findings and suggestions.

    A review embeds repository code and security findings, so it is never
    public and never shared: reading one requires a connected provider token
    and ownership of the review. Both reads are scoped to the caller, matching
    how the legacy review surface isolates per-user history.
    """
    user_id = user["github_id"]
    document = await _require_document(review_id, user_id)
    findings = await ai_review_repository.list_findings(review_id, user_id=user_id)
    return Review.model_validate(ai_review_repository.serialize_review(document, findings=findings))


@router.get("/reviews/{review_id}/findings", response_model=ReviewFindingsResponse)
async def get_review_findings(
    review_id: str,
    severity: str | None = Query(None),
    category: str | None = Query(None),
    file: str | None = Query(None, min_length=1),
    sort: str | None = Query(None),
    token: str = Depends(require_github_token),
    user: dict = Depends(get_current_user),
) -> ReviewFindingsResponse:
    """Findings for one review, filterable by severity, category and file.

    Unknown filter values are rejected rather than silently matching nothing, so
    a client bug surfaces as a 422 instead of a misleading empty list.

    Ownership is checked before any finding is read, so a caller who does not
    own the review gets the same 404 as one who guessed an id that never
    existed — and in particular never sees a filtered view of someone else's
    findings.
    """
    if severity is not None and severity not in AI_SEVERITIES:
        raise HTTPException(status_code=422, detail=f"Unknown severity '{severity}'")
    if category is not None and category not in AI_CATEGORIES:
        raise HTTPException(status_code=422, detail=f"Unknown category '{category}'")
    if sort is not None and sort not in ai_review_repository.FINDING_SORT_FIELDS:
        raise HTTPException(status_code=422, detail=f"Unknown sort field '{sort}'")

    user_id = user["github_id"]
    await _require_document(review_id, user_id)
    findings = await ai_review_repository.list_findings(
        review_id, user_id=user_id, severity=severity, category=category, file=file, sort=sort
    )
    return ReviewFindingsResponse(
        review_id=review_id,
        total=len(findings),
        findings=[
            ReviewFinding.model_validate(ai_review_repository.project_finding(raw))
            for raw in findings
            if isinstance(raw, dict)
        ],
    )

