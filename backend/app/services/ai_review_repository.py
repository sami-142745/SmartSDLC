"""Persistence for Sprint 3 AI pull-request reviews (schema v2).

Deliberately stored in its own collections (``ai_reviews`` /
``ai_review_findings``) rather than the legacy ``reviews`` /
``review_findings`` pair used by :mod:`app.services.review_repository`.

Why not share? The legacy documents are read by the dashboard, insights,
feedback-learning and adaptive-ranking features, all of which assume the
``id``/``code``/``recommendation`` field names and the legacy category
vocabulary. Mixing generations in one collection would make every one of those
queries ambiguous, and would put a v2-shaped document behind a legacy
``GET /reviews/{owner}/{repo}/{number}`` response model. Separate collections
mean both generations coexist with zero cross-talk and zero migration.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId

from app.schemas.ai_review import (
    AI_CATEGORIES,
    AI_SEVERITIES,
    SEVERITY_RANK,
    Review,
    ReviewFinding,
)
from app.services.database import get_db

REVIEWS_COLLECTION = "ai_reviews"
FINDINGS_COLLECTION = "ai_review_findings"

#: Sort keys accepted by :func:`list_findings`.
FINDING_SORT_FIELDS = frozenset({"severity", "confidence", "category", "file", "line"})


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def to_object_id(review_id: Any) -> ObjectId | None:
    """Parse a review id, returning ``None`` when it is not a valid ObjectId.

    The API contract is a 404 for an unknown id, not a 500, so a malformed id
    must be indistinguishable from a missing one.
    """
    if isinstance(review_id, ObjectId):
        return review_id
    if not isinstance(review_id, str) or not review_id.strip():
        return None
    try:
        return ObjectId(review_id.strip())
    except Exception:
        return None


async def ensure_indexes() -> None:
    db = get_db()
    await db[REVIEWS_COLLECTION].create_index(
        [("owner", 1), ("repository", 1), ("pull_request_number", 1)],
        name="idx_ai_reviews_pr",
    )
    await db[REVIEWS_COLLECTION].create_index(
        [("user_id", 1), ("created_at", -1)],
        name="idx_ai_reviews_user_created",
    )
    await db[REVIEWS_COLLECTION].create_index(
        [("commit_sha", 1)],
        name="idx_ai_reviews_commit",
    )
    await db[FINDINGS_COLLECTION].create_index(
        [("review_id", 1)],
        name="idx_ai_findings_review",
    )
    await db[FINDINGS_COLLECTION].create_index(
        [("review_id", 1), ("severity", 1)],
        name="idx_ai_findings_review_severity",
    )
    await db[FINDINGS_COLLECTION].create_index(
        [("review_id", 1), ("category", 1)],
        name="idx_ai_findings_review_category",
    )
    await db[FINDINGS_COLLECTION].create_index(
        [("review_id", 1), ("file", 1)],
        name="idx_ai_findings_review_file",
    )
    # finding_id is the stable public key used for navigation and feedback.
    await db[FINDINGS_COLLECTION].create_index(
        [("review_id", 1), ("finding_id", 1)],
        unique=True,
        name="idx_ai_findings_unique",
    )


def _counts(values: list[str], keys: tuple[str, ...]) -> dict[str, int]:
    counts = {key: 0 for key in keys}
    for value in values:
        if value in counts:
            counts[value] += 1
    return counts


async def save_review(review: Review, *, user_id: int | None = None) -> str:
    """Persist a completed review and its findings, returning the new id."""
    db = get_db()
    now = _utcnow()

    findings = [finding.model_dump(mode="json") for finding in review.findings]
    severities = [finding.severity for finding in review.findings]
    categories = [finding.category for finding in review.findings]
    severity_counts = _counts(severities, AI_SEVERITIES)
    category_counts = _counts(categories, AI_CATEGORIES)

    # Severity sorts by rank rather than alphabetically, so "critical" would
    # otherwise sort after "high" and "info". Stored on the document to keep
    # the default finding order a plain indexed sort.
    ranked = [
        {**finding, "severity_rank": severity_rank}
        for finding, severity_rank in zip(findings, [SEVERITY_RANK[s] for s in severities])
    ]

    review_doc: dict[str, Any] = {
        "schema_version": 2,
        "status": review.status,
        "ai_status": review.ai_status,
        "owner": review.owner,
        "repository": review.repository,
        "pull_request_number": review.pull_request_number,
        "pull_request_title": review.pull_request_title,
        "commit_sha": review.commit_sha,
        "provider": review.provider,
        "error": review.error,
        "duration_ms": review.duration_ms,
        "user_id": user_id,
        "summary": review.summary.model_dump(mode="json"),
        "files": [file.model_dump(mode="json") for file in review.files],
        "suggestions": [item.model_dump(mode="json") for item in review.suggestions],
        "total_finding_count": len(findings),
        "severity_counts": severity_counts,
        "category_counts": category_counts,
        "file_count": len(review.files),
        "created_at": now,
        "updated_at": now,
    }

    result = await db[REVIEWS_COLLECTION].insert_one(review_doc)
    review_id = str(result.inserted_id)

    if findings:
        await db[FINDINGS_COLLECTION].insert_many(
            [
                {**finding, "review_id": review_id, "user_id": user_id, "created_at": now}
                for finding in ranked
            ]
        )

    return review_id


def project_finding(raw: dict[str, Any]) -> dict[str, Any]:
    """Keep only the fields ``ReviewFinding`` declares.

    Finding documents carry denormalized and internal keys (``severity_rank``,
    ``review_id``, ``user_id``, ``created_at``) that exist for indexing and
    joins, not for the API. ``ReviewFinding`` forbids extra fields, so they are
    stripped here rather than loosening the contract.
    """
    declared = set(ReviewFinding.model_fields)
    return {key: value for key, value in raw.items() if key in declared}


def serialize_review(document: dict[str, Any] | None, *, findings: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
    """Rehydrate a stored document into the public response shape.

    Accepts documents written by older code paths and fills in defaults, so a
    review stored before a field existed still reads cleanly.
    """
    if document is None:
        return None

    document = dict(document)
    object_id = document.pop("_id", None)

    resolved = findings if findings is not None else document.get("findings") or []
    validated: list[dict[str, Any]] = []
    for raw in resolved:
        if not isinstance(raw, dict):
            continue
        try:
            validated.append(ReviewFinding.model_validate(project_finding(raw)).model_dump(mode="json"))
        except Exception:
            # A finding we can no longer validate is dropped rather than
            # crashing the read of an otherwise-good review.
            continue

    return {
        "review_id": str(document.get("review_id") or object_id or ""),
        "schema_version": int(document.get("schema_version") or 2),
        "status": document.get("status") or "complete",
        "ai_status": document.get("ai_status") or "complete",
        "owner": document.get("owner") or "",
        "repository": document.get("repository") or "",
        "pull_request_number": int(document.get("pull_request_number") or 0),
        "pull_request_title": document.get("pull_request_title"),
        "commit_sha": document.get("commit_sha"),
        "provider": document.get("provider") or "github",
        "summary": document.get("summary") or {},
        "files": document.get("files") or [],
        "findings": validated,
        "suggestions": document.get("suggestions") or [],
        "error": document.get("error"),
        "duration_ms": document.get("duration_ms"),
        "created_at": document.get("created_at"),
        "updated_at": document.get("updated_at"),
    }


async def find_review_by_id(review_id: str, *, user_id: int) -> dict[str, Any] | None:
    """Fetch one review owned by ``user_id``.

    ``user_id`` is a required filter, not an optional convenience: every read
    path scopes by it, so a review id belonging to another account resolves to
    ``None`` here and the caller reports a plain 404. That keeps the response
    for "not yours" identical to the response for "does not exist", so a
    review id cannot be used to probe for other users' reviews.
    """
    object_id = to_object_id(review_id)
    if object_id is None:
        return None
    db = get_db()
    return await db[REVIEWS_COLLECTION].find_one({"_id": object_id, "user_id": user_id})


async def list_findings(
    review_id: str,
    *,
    user_id: int,
    severity: str | None = None,
    category: str | None = None,
    file: str | None = None,
    sort: str | None = None,
) -> list[dict[str, Any]]:
    """Findings for one review owned by ``user_id``, optionally filtered and sorted.

    Sorts by descending severity then descending confidence by default, so the
    most serious finding is first without the caller asking for an order.

    Scoped by ``user_id`` for the same reason as :func:`find_review_by_id`, and
    for defence in depth: a caller that reaches this function without first
    passing the ownership check still cannot read another account's findings.
    """
    db = get_db()
    query: dict[str, Any] = {"review_id": review_id, "user_id": user_id}
    if severity:
        query["severity"] = severity
    if category:
        query["category"] = category
    if file:
        query["file"] = file

    if sort not in FINDING_SORT_FIELDS:
        # severity_rank is 0 for "critical", so the most serious finding sorts
        # first with an ASCENDING rank; confidence is descending so the
        # best-evidenced finding wins a tie.
        order = [("severity_rank", 1), ("confidence", -1), ("line", 1)]
    else:
        descending = sort != "line"
        order = [(sort, -1 if descending else 1), ("confidence", -1)]

    # Motor's sort takes a single list of (field, direction) pairs.
    cursor = db[FINDINGS_COLLECTION].find(query, {"_id": 0}).sort(order)
    return [finding async for finding in cursor]

