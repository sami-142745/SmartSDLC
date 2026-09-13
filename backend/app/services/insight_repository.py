from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from app.services.database import get_db

INSIGHTS_COLLECTION = "insights"

_OBJECT_ID_RE = re.compile(r"^[0-9a-f]{24}$")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def is_valid_insight_id(insight_id: str | None) -> bool:
    return bool(insight_id and _OBJECT_ID_RE.fullmatch(insight_id))


async def ensure_indexes() -> None:
    db = get_db()
    await db[INSIGHTS_COLLECTION].create_index(
        [("user_id", 1), ("created_at", -1)],
        name="idx_insights_user_created",
    )
    await db[INSIGHTS_COLLECTION].create_index(
        [("user_id", 1), ("owner", 1), ("repository", 1), ("created_at", -1)],
        name="idx_insights_user_repo_created",
    )


async def save_insight(insight: dict[str, Any]) -> str:
    db = get_db()
    result = await db[INSIGHTS_COLLECTION].insert_one(insight)
    return str(result.inserted_id)


async def get_insight(insight_id: str, user_id: int) -> dict[str, Any] | None:
    if not is_valid_insight_id(insight_id):
        return None
    from bson import ObjectId

    db = get_db()
    return await db[INSIGHTS_COLLECTION].find_one({"_id": ObjectId(insight_id), "user_id": user_id})


async def get_latest_insight(
    user_id: int,
    owner: str,
    repository: str,
    pull_request: int | None = None,
    report_type: str | None = None,
) -> dict[str, Any] | None:
    db = get_db()
    query: dict[str, Any] = {"user_id": user_id, "owner": owner, "repository": repository}
    if pull_request is not None:
        query["pull_request"] = pull_request
        query["report_type"] = "pull_request"
    elif report_type:
        query["report_type"] = report_type
    cursor = db[INSIGHTS_COLLECTION].find(query).sort("created_at", -1).limit(1)
    async for doc in cursor:
        return doc
    return None


async def list_insights(
    user_id: int,
    *,
    page: int = 1,
    per_page: int = 20,
    repository: str | None = None,
    report_type: str | None = None,
) -> dict[str, Any]:
    db = get_db()
    query: dict[str, Any] = {"user_id": user_id}
    if repository:
        query["repository"] = repository
    if report_type:
        query["report_type"] = report_type
    total = await db[INSIGHTS_COLLECTION].count_documents(query)
    cursor = (
        db[INSIGHTS_COLLECTION]
        .find(query)
        .sort("created_at", -1)
        .skip((page - 1) * per_page)
        .limit(per_page)
    )
    items = [doc async for doc in cursor]
    return {"items": items, "total": total, "page": page, "per_page": per_page}