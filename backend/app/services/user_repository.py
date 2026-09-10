from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.database import get_db

USERS_COLLECTION = "users"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def to_safe_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "github_id": user.get("github_id"),
        "login": user.get("login"),
        "name": user.get("name"),
        "email": user.get("email"),
        "avatar_url": user.get("avatar_url"),
        "created_at": user.get("created_at"),
        "updated_at": user.get("updated_at"),
    }


async def upsert_github_user(profile: dict[str, Any], access_token: str) -> dict[str, Any]:
    github_id = profile.get("id")
    if not github_id:
        raise ValueError("GitHub profile is missing id")

    db = get_db()
    now = _utcnow()
    settable = {
        "login": profile.get("login"),
        "name": profile.get("name"),
        "email": profile.get("email"),
        "avatar_url": profile.get("avatar_url"),
        "github_access_token": access_token,
        "updated_at": now,
    }

    await db[USERS_COLLECTION].update_one(
        {"github_id": github_id},
        {"$set": settable, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )

    user = await db[USERS_COLLECTION].find_one({"github_id": github_id})
    if user is None:
        raise RuntimeError("Failed to retrieve user after upsert")
    return user


async def get_user_by_github_id(github_id: int) -> dict[str, Any] | None:
    db = get_db()
    return await db[USERS_COLLECTION].find_one({"github_id": github_id})


async def get_user_by_login(login: str) -> dict[str, Any] | None:
    db = get_db()
    return await db[USERS_COLLECTION].find_one({"login": login})


async def ensure_indexes() -> None:
    db = get_db()
    await db[USERS_COLLECTION].create_index("github_id", unique=True)