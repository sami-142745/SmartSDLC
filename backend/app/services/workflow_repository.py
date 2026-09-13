from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from typing import Any

from app.services.database import get_db

WORKFLOWS_COLLECTION = "workflows"
RECEIVED_STAGE = "RECEIVED"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_workflow_id() -> str:
    return uuid.uuid4().hex


async def ensure_indexes() -> None:
    db = get_db()
    await db[WORKFLOWS_COLLECTION].create_index(
        "workflow_id",
        unique=True,
        name="idx_workflows_id",
    )
    await db[WORKFLOWS_COLLECTION].create_index(
        [("user_id", 1), ("created_at", -1)],
        name="idx_workflows_user_created",
    )


async def create_workflow(
    *,
    user_id: int | None,
    owner: str,
    repository: str,
    pull_request_number: int,
    trigger: str,
    provider: str = "github",
    initiated_by: str = "api",
) -> dict[str, Any]:
    db = get_db()
    now = _utcnow()
    workflow_id = _new_workflow_id()
    doc = {
        "workflow_id": workflow_id,
        "user_id": user_id,
        "owner": owner,
        "repository": repository,
        "pull_request_number": pull_request_number,
        "trigger": trigger,
        "provider": provider,
        "initiated_by": initiated_by,
        "status": "queued",
        "stage": RECEIVED_STAGE,
        "error": None,
        "review_id": None,
        "history": [{"stage": RECEIVED_STAGE, "at": now}],
        "created_at": now,
        "updated_at": now,
    }
    await db[WORKFLOWS_COLLECTION].insert_one(doc)
    return doc


async def _transition(workflow_id: str, stage: str, status: str, **extra: Any) -> None:
    db = get_db()
    now = _utcnow()
    existing = await db[WORKFLOWS_COLLECTION].find_one({"workflow_id": workflow_id})
    if existing is None:
        return
    history = list(existing.get("history") or [])
    history.append({"stage": stage, "at": now, "detail": extra.get("detail")})
    set_fields: dict[str, Any] = {
        "stage": stage,
        "status": status,
        "history": history,
        "updated_at": now,
    }
    if extra.get("error") is not None:
        set_fields["error"] = extra["error"]
    if extra.get("review_id") is not None:
        set_fields["review_id"] = extra["review_id"]

    created_at = existing.get("created_at")
    if isinstance(created_at, datetime):
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        set_fields["duration_ms"] = max(0, int((now - created_at).total_seconds() * 1000))

    await db[WORKFLOWS_COLLECTION].update_one(
        {"workflow_id": workflow_id},
        {"$set": set_fields},
    )


async def update_stage(workflow_id: str, stage: str) -> None:
    await _transition(workflow_id, stage, "running")


async def complete(workflow_id: str, review_id: str | None = None) -> None:
    await _transition(workflow_id, "COMPLETED", "completed", review_id=review_id)


async def fail(workflow_id: str, error: str | None = None) -> None:
    await _transition(workflow_id, "FAILED", "failed", error=error)


async def get_workflow(workflow_id: str, user_id: int | None = None) -> dict[str, Any] | None:
    db = get_db()
    query: dict[str, Any] = {"workflow_id": workflow_id}
    if user_id is not None:
        query["user_id"] = user_id
    return await db[WORKFLOWS_COLLECTION].find_one(query)


async def list_workflows(
    *,
    user_id: int,
    page: int = 1,
    per_page: int = 20,
    status: str | None = None,
    repository: str | None = None,
) -> dict[str, Any]:
    db = get_db()
    query: dict[str, Any] = {"user_id": user_id}
    if status:
        query["status"] = status
    if repository:
        query["repository"] = repository
    total = await db[WORKFLOWS_COLLECTION].count_documents(query)
    cursor = (
        db[WORKFLOWS_COLLECTION]
        .find(query)
        .sort("created_at", -1)
        .skip((page - 1) * per_page)
        .limit(per_page)
    )
    items = [doc async for doc in cursor]
    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": math.ceil(total / per_page) if total else 0,
    }