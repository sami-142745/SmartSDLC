from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.database import get_db

REVIEWS_COLLECTION = "reviews"
FINDINGS_COLLECTION = "review_findings"
FEEDBACK_COLLECTION = "review_feedback"

SEVERITY_KEYS = ("critical", "high", "medium", "low", "info")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _severity_counts(findings: list[dict[str, Any]]) -> dict[str, int]:
    counts = {key: 0 for key in SEVERITY_KEYS}
    for finding in findings:
        severity = finding.get("severity")
        if severity in counts:
            counts[severity] += 1
    return counts


async def ensure_indexes() -> None:
    db = get_db()
    await db[REVIEWS_COLLECTION].create_index(
        [("owner", 1), ("repository", 1), ("pull_request_number", 1)],
        name="idx_reviews_pr",
    )
    await db[REVIEWS_COLLECTION].create_index(
        [("commit_sha", 1)],
        name="idx_reviews_commit",
    )
    await db[REVIEWS_COLLECTION].create_index(
        [("user_id", 1), ("created_at", -1)],
        name="idx_reviews_user_created",
    )
    await db[REVIEWS_COLLECTION].create_index(
        [("repository", 1), ("created_at", -1)],
        name="idx_reviews_repo_created",
    )
    await db[FINDINGS_COLLECTION].create_index(
        [("review_id", 1)],
        name="idx_findings_review",
    )
    await db[FINDINGS_COLLECTION].create_index(
        [("user_id", 1), ("category", 1)],
        name="idx_findings_user_category",
    )
    await db[FINDINGS_COLLECTION].create_index(
        [("user_id", 1), ("severity", 1)],
        name="idx_findings_user_severity",
    )
    await db[FEEDBACK_COLLECTION].create_index(
        [("user_id", 1), ("created_at", -1)],
        name="idx_feedback_user_created",
    )
    await db[FEEDBACK_COLLECTION].create_index(
        [("review_id", 1), ("finding_id", 1), ("user_id", 1)],
        unique=True,
        name="idx_feedback_unique",
    )
    await db[FEEDBACK_COLLECTION].create_index(
        [("user_id", 1), ("action", 1)],
        name="idx_feedback_user_action",
    )


async def save_review(
    *,
    status: str,
    owner: str,
    repository: str,
    pull_request_number: int,
    pull_request_title: str | None,
    commit_sha: str | None,
    findings: list[dict[str, Any]],
    review_score: float | None,
    review_severity: str | None,
    duration_ms: int | None,
    error: str | None = None,
    user_id: int | None = None,
) -> str:
    db = get_db()
    now = _utcnow()
    severity_counts = _severity_counts(findings)
    review_doc = {
        "status": status,
        "owner": owner,
        "repository": repository,
        "pull_request_number": pull_request_number,
        "pull_request_title": pull_request_title,
        "commit_sha": commit_sha,
        "review_score": review_score,
        "review_severity": review_severity,
        "duration_ms": duration_ms,
        "error": error,
        "user_id": user_id,
        "total_finding_count": len(findings),
        "critical_count": severity_counts["critical"],
        "high_count": severity_counts["high"],
        "medium_count": severity_counts["medium"],
        "low_count": severity_counts["low"],
        "info_count": severity_counts["info"],
        "heuristic_finding_count": sum(1 for f in findings if f.get("source") in ("heuristic", "combined")),
        "gemini_finding_count": sum(1 for f in findings if f.get("source") in ("gemini", "combined")),
        "created_at": now,
        "updated_at": now,
    }
    result = await db[REVIEWS_COLLECTION].insert_one(review_doc)
    review_id = str(result.inserted_id)

    if findings:
        await db[FINDINGS_COLLECTION].insert_many(
            [
                {**finding, "review_id": review_id, "user_id": user_id, "created_at": now}
                for finding in findings
            ]
        )

    return review_id


async def find_review_by_id(review_id: str) -> dict[str, Any] | None:
    from bson import ObjectId

    try:
        _id = ObjectId(review_id)
    except Exception:
        return None
    db = get_db()
    return await db[REVIEWS_COLLECTION].find_one({"_id": _id})


async def list_reviews(owner: str, repository: str, pull_request_number: int) -> list[dict[str, Any]]:
    db = get_db()
    cursor = db[REVIEWS_COLLECTION].find(
        {
            "owner": owner,
            "repository": repository,
            "pull_request_number": pull_request_number,
        }
    ).sort("created_at", -1)
    return [review async for review in cursor]


async def list_findings(review_id: str) -> list[dict[str, Any]]:
    db = get_db()
    cursor = db[FINDINGS_COLLECTION].find({"review_id": review_id}, {"_id": 0})
    return [finding async for finding in cursor]


async def list_reviews_by_user(
    *,
    user_id: int,
    page: int = 1,
    per_page: int = 20,
    repository: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    db = get_db()
    query: dict[str, Any] = {"user_id": user_id}
    if repository:
        query["repository"] = repository
    if status:
        query["status"] = status
    total = await db[REVIEWS_COLLECTION].count_documents(query)
    cursor = (
        db[REVIEWS_COLLECTION]
        .find(query)
        .sort("created_at", -1)
        .skip((page - 1) * per_page)
        .limit(per_page)
    )
    reviews = [review async for review in cursor]
    return {"reviews": reviews, "total": total, "page": page, "per_page": per_page}


async def find_review_for_user(
    user_id: int,
    owner: str,
    repository: str,
    pull_request_number: int,
) -> dict[str, Any] | None:
    db = get_db()
    return await db[REVIEWS_COLLECTION].find_one(
        {
            "user_id": user_id,
            "owner": owner,
            "repository": repository,
            "pull_request_number": pull_request_number,
        }
    )


async def find_finding(review_id: str, finding_id: str) -> dict[str, Any] | None:
    db = get_db()
    return await db[FINDINGS_COLLECTION].find_one(
        {"review_id": review_id, "id": finding_id}
    )


async def count_reviews(user_id: int) -> int:
    db = get_db()
    return await db[REVIEWS_COLLECTION].count_documents({"user_id": user_id})


async def count_reviews_since(user_id: int, since: datetime) -> int:
    db = get_db()
    return await db[REVIEWS_COLLECTION].count_documents(
        {"user_id": user_id, "created_at": {"$gte": since}}
    )


async def list_recent_reviews(user_id: int, limit: int = 10) -> list[dict[str, Any]]:
    db = get_db()
    cursor = (
        db[REVIEWS_COLLECTION]
        .find({"user_id": user_id})
        .sort("created_at", -1)
        .limit(limit)
    )
    return [review async for review in cursor]


async def aggregate_findings_by_severity(user_id: int) -> list[dict[str, Any]]:
    db = get_db()
    pipeline = [
        {"$match": {"user_id": user_id}},
        {"$group": {"_id": "$severity", "count": {"$sum": 1}}},
    ]
    return [doc async for doc in db[FINDINGS_COLLECTION].aggregate(pipeline)]


async def aggregate_findings_by_category(user_id: int) -> list[dict[str, Any]]:
    db = get_db()
    pipeline = [
        {"$match": {"user_id": user_id}},
        {"$group": {"_id": "$category", "count": {"$sum": 1}}},
    ]
    return [doc async for doc in db[FINDINGS_COLLECTION].aggregate(pipeline)]


async def aggregate_repository_metrics(
    *,
    user_id: int,
    page: int = 1,
    per_page: int = 20,
) -> dict[str, Any]:
    db = get_db()
    pipeline: list[dict[str, Any]] = [
        {"$match": {"user_id": user_id}},
        {
            "$group": {
                "_id": {"owner": "$owner", "repository": "$repository"},
                "review_count": {"$sum": 1},
                "finding_count": {"$sum": {"$ifNull": ["$total_finding_count", 0]}},
                "critical_count": {"$sum": {"$ifNull": ["$critical_count", 0]}},
                "high_count": {"$sum": {"$ifNull": ["$high_count", 0]}},
                "medium_count": {"$sum": {"$ifNull": ["$medium_count", 0]}},
                "low_count": {"$sum": {"$ifNull": ["$low_count", 0]}},
                "info_count": {"$sum": {"$ifNull": ["$info_count", 0]}},
                "last_review_at": {"$max": "$created_at"},
            }
        },
        {"$sort": {"last_review_at": -1}},
        {
            "$facet": {
                "metadata": [{"$count": "total"}],
                "data": [{"$skip": (page - 1) * per_page}, {"$limit": per_page}],
            }
        },
    ]
    facet_doc = [doc async for doc in db[REVIEWS_COLLECTION].aggregate(pipeline)]
    facet = facet_doc[0] if facet_doc else {"metadata": [{"total": 0}], "data": []}
    total = facet.get("metadata", [{}])[0].get("total") if facet.get("metadata") else 0
    return {
        "repositories": facet.get("data", []),
        "total": total or 0,
        "page": page,
        "per_page": per_page,
    }


async def save_feedback(
    *,
    review_id: str,
    finding_id: str,
    user_id: int,
    action: str,
    category: str | None,
    severity: str | None,
    owner: str,
    repository: str,
    pull_request_number: int,
) -> dict[str, Any]:
    db = get_db()
    now = _utcnow()
    await db[FEEDBACK_COLLECTION].update_one(
        {"review_id": review_id, "finding_id": finding_id, "user_id": user_id},
        {
            "$set": {
                "action": action,
                "category": category,
                "severity": severity,
                "owner": owner,
                "repository": repository,
                "pull_request_number": pull_request_number,
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )
    feedback = await db[FEEDBACK_COLLECTION].find_one(
        {"review_id": review_id, "finding_id": finding_id, "user_id": user_id}
    )
    return feedback or {}


async def list_feedback_for_user(
    *,
    user_id: int,
    page: int = 1,
    per_page: int = 20,
) -> dict[str, Any]:
    db = get_db()
    query = {"user_id": user_id}
    total = await db[FEEDBACK_COLLECTION].count_documents(query)
    cursor = (
        db[FEEDBACK_COLLECTION]
        .find(query)
        .sort("created_at", -1)
        .skip((page - 1) * per_page)
        .limit(per_page)
    )
    items = [doc async for doc in cursor]
    return {"items": items, "total": total, "page": page, "per_page": per_page}


async def count_feedback(user_id: int, action: str) -> int:
    db = get_db()
    return await db[FEEDBACK_COLLECTION].count_documents(
        {"user_id": user_id, "action": action}
    )


async def aggregate_feedback_by_category(user_id: int) -> list[dict[str, Any]]:
    db = get_db()
    pipeline = [
        {"$match": {"user_id": user_id}},
        {
            "$group": {
                "_id": {"category": "$category", "action": "$action"},
                "count": {"$sum": 1},
            }
        },
    ]
    return [doc async for doc in db[FEEDBACK_COLLECTION].aggregate(pipeline)]


async def aggregate_feedback_by_severity(user_id: int) -> list[dict[str, Any]]:
    db = get_db()
    pipeline = [
        {"$match": {"user_id": user_id}},
        {
            "$group": {
                "_id": {"severity": "$severity", "action": "$action"},
                "count": {"$sum": 1},
            }
        },
    ]
    return [doc async for doc in db[FEEDBACK_COLLECTION].aggregate(pipeline)]


async def list_reviews_for_scope(
    user_id: int,
    owner: str,
    repository: str,
    pull_request_number: int | None = None,
) -> list[dict[str, Any]]:
    """Chronological (oldest-first) reviews for a repository, optionally scoped to a PR."""
    db = get_db()
    query: dict[str, Any] = {"user_id": user_id, "owner": owner, "repository": repository}
    if pull_request_number is not None:
        query["pull_request_number"] = pull_request_number
    cursor = db[REVIEWS_COLLECTION].find(query).sort("created_at", 1)
    return [review async for review in cursor]


async def list_findings_for_reviews(review_ids: list[str]) -> list[dict[str, Any]]:
    if not review_ids:
        return []
    db = get_db()
    cursor = db[FINDINGS_COLLECTION].find({"review_id": {"$in": review_ids}}, {"_id": 0})
    return [finding async for finding in cursor]


async def list_feedback_for_scope(
    user_id: int,
    owner: str,
    repository: str,
    pull_request_number: int | None = None,
) -> list[dict[str, Any]]:
    db = get_db()
    query: dict[str, Any] = {"user_id": user_id, "owner": owner, "repository": repository}
    if pull_request_number is not None:
        query["pull_request_number"] = pull_request_number
    cursor = db[FEEDBACK_COLLECTION].find(query).sort("created_at", 1)
    return [doc async for doc in cursor]