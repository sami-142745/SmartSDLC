from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from app.services.database import get_db

DOCUMENTS_COLLECTION = "documents"

_OBJECT_ID_RE = re.compile(r"^[0-9a-f]{24}$")

DOCUMENT_SECTIONS = ("summary", "architecture", "modules", "api", "changes", "configuration", "security", "setup")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def is_valid_document_id(doc_id: str | None) -> bool:
    return bool(doc_id and _OBJECT_ID_RE.fullmatch(doc_id))


async def ensure_indexes() -> None:
    db = get_db()
    await db[DOCUMENTS_COLLECTION].create_index(
        [("user_id", 1), ("created_at", -1)],
        name="idx_documents_user_created",
    )
    await db[DOCUMENTS_COLLECTION].create_index(
        [("user_id", 1), ("owner", 1), ("repository", 1), ("created_at", -1)],
        name="idx_documents_user_repo_created",
    )


def _documentation_rows(documentation: dict[str, Any]) -> dict[str, Any]:
    rows: dict[str, Any] = {"title": documentation.get("title") or "Untitled documentation"}
    for section in DOCUMENT_SECTIONS:
        rows[section] = documentation.get(section)
    return rows


async def save_document(
    *,
    user_id: int,
    owner: str,
    repository: str,
    pull_request_number: int | None,
    pull_request_title: str | None,
    commit_sha: str | None,
    default_branch: str | None,
    documentation: dict[str, Any],
    model: str,
    status: str,
    duration_ms: int,
    error: str | None = None,
) -> str:
    db = get_db()
    now = _utcnow()
    doc = {
        "user_id": user_id,
        "owner": owner,
        "repository": repository,
        "pull_request_number": pull_request_number,
        "pull_request_title": pull_request_title,
        "commit_sha": commit_sha,
        "default_branch": default_branch,
        "model": model,
        "status": status,
        "error": error,
        "duration_ms": duration_ms,
        "created_at": now,
        "updated_at": now,
        **_documentation_rows(documentation),
    }
    result = await db[DOCUMENTS_COLLECTION].insert_one(doc)
    return str(result.inserted_id)


async def get_document(doc_id: str, user_id: int) -> dict[str, Any] | None:
    if not is_valid_document_id(doc_id):
        return None
    from bson import ObjectId

    db = get_db()
    return await db[DOCUMENTS_COLLECTION].find_one({"_id": ObjectId(doc_id), "user_id": user_id})


async def get_latest_document(
    user_id: int,
    owner: str,
    repository: str,
    pull_request_number: int | None = None,
) -> dict[str, Any] | None:
    db = get_db()
    query: dict[str, Any] = {"user_id": user_id, "owner": owner, "repository": repository}
    if pull_request_number is not None:
        query["pull_request_number"] = pull_request_number
    cursor = db[DOCUMENTS_COLLECTION].find(query).sort("created_at", -1).limit(1)
    async for doc in cursor:
        return doc
    return None


async def list_documents(
    user_id: int,
    *,
    page: int = 1,
    per_page: int = 20,
    repository: str | None = None,
    owner: str | None = None,
) -> dict[str, Any]:
    db = get_db()
    query: dict[str, Any] = {"user_id": user_id}
    if repository:
        query["repository"] = repository
    if owner:
        query["owner"] = owner
    total = await db[DOCUMENTS_COLLECTION].count_documents(query)
    cursor = (
        db[DOCUMENTS_COLLECTION]
        .find(query)
        .sort("created_at", -1)
        .skip((page - 1) * per_page)
        .limit(per_page)
    )
    items = [doc async for doc in cursor]
    return {"items": items, "total": total, "page": page, "per_page": per_page}


async def count_documents(user_id: int) -> int:
    db = get_db()
    return await db[DOCUMENTS_COLLECTION].count_documents({"user_id": user_id})