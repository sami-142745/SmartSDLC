from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.database import get_db

LEARNING_COLLECTION = "feedback_learning"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def ensure_indexes() -> None:
    db = get_db()
    await db[LEARNING_COLLECTION].create_index(
        [("user_id", 1), ("owner", 1), ("repository", 1), ("category", 1)],
        unique=True,
        name="idx_learning_scope",
    )
    await db[LEARNING_COLLECTION].create_index(
        [("user_id", 1), ("category", 1)],
        name="idx_learning_user_category",
    )


async def list_profiles(
    user_id: int,
    owner: str | None = None,
    repository: str | None = None,
) -> list[dict[str, Any]]:
    db = get_db()
    query: dict[str, Any] = {"user_id": user_id}
    if owner and repository:
        query["owner"] = owner
        query["repository"] = repository
    cursor = db[LEARNING_COLLECTION].find(query).sort("updated_at", -1)
    return [doc async for doc in cursor]


async def find_profile(
    user_id: int,
    owner: str,
    repository: str,
    category: str,
) -> dict[str, Any] | None:
    db = get_db()
    return await db[LEARNING_COLLECTION].find_one(
        {"user_id": user_id, "owner": owner, "repository": repository, "category": category}
    )


async def upsert_counts(
    *,
    user_id: int,
    owner: str,
    repository: str,
    category: str,
    accepted_delta: int = 0,
    dismissed_delta: int = 0,
) -> dict[str, Any]:
    db = get_db()
    now = _utcnow()
    existing = await db[LEARNING_COLLECTION].find_one(
        {"user_id": user_id, "owner": owner, "repository": repository, "category": category}
    )
    accepted = (existing or {}).get("accepted_count", 0)
    dismissed = (existing or {}).get("dismissed_count", 0)
    if accepted_delta > 0 or dismissed_delta > 0:
        await db[LEARNING_COLLECTION].update_one(
            {"user_id": user_id, "owner": owner, "repository": repository, "category": category},
            {
                "$set": {
                    "accepted_count": accepted + accepted_delta,
                    "dismissed_count": dismissed + dismissed_delta,
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )
    stored = await find_profile(user_id, owner, repository, category)
    return stored or {}


async def set_counts(
    *,
    user_id: int,
    owner: str,
    repository: str,
    category: str,
    accepted: int,
    dismissed: int,
) -> None:
    db = get_db()
    now = _utcnow()
    await db[LEARNING_COLLECTION].update_one(
        {"user_id": user_id, "owner": owner, "repository": repository, "category": category},
        {
            "$set": {
                "accepted_count": accepted,
                "dismissed_count": dismissed,
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )


async def delete_profiles(user_id: int) -> None:
    db = get_db()
    await db[LEARNING_COLLECTION].delete_many({"user_id": user_id})


async def delete_profile(
    *,
    user_id: int,
    owner: str,
    repository: str,
    category: str,
) -> None:
    db = get_db()
    await db[LEARNING_COLLECTION].delete_many(
        {"user_id": user_id, "owner": owner, "repository": repository, "category": category}
    )