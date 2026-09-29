from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from typing import Any

from app.services.database import get_db

WORKFLOWS_COLLECTION = "workflows"
WORKFLOW_EVENTS_COLLECTION = "workflow_events"
CICD_RUNS_COLLECTION = "cicd_runs"
CICD_PROVIDER_CONFIGS_COLLECTION = "cicd_provider_configs"

# Legacy stage constants for backward compatibility
RECEIVED_STAGE = "RECEIVED"

# ---------------------------------------------------------------------------
# Indexes
# ---------------------------------------------------------------------------


async def ensure_indexes() -> None:
    db = get_db()

    # Workflows
    await db[WORKFLOWS_COLLECTION].create_index(
        "workflow_id",
        unique=True,
        name="idx_workflows_id",
    )
    await db[WORKFLOWS_COLLECTION].create_index(
        [("user_id", 1), ("created_at", -1)],
        name="idx_workflows_user_created",
    )
    await db[WORKFLOWS_COLLECTION].create_index(
        [("owner", 1), ("repository", 1), ("created_at", -1)],
        name="idx_workflows_owner_repo_created",
    )

    # Workflow Events
    await db[WORKFLOW_EVENTS_COLLECTION].create_index(
        "event_id",
        unique=True,
        name="idx_workflow_events_id",
    )
    await db[WORKFLOW_EVENTS_COLLECTION].create_index(
        "workflow_run_id",
        name="idx_workflow_events_run_id",
    )
    await db[WORKFLOW_EVENTS_COLLECTION].create_index(
        [("workflow_run_id", 1), ("started_at", 1)],
        name="idx_workflow_events_run_started",
    )
    await db[WORKFLOW_EVENTS_COLLECTION].create_index(
        [("user_id", 1), ("created_at", -1)],
        name="idx_workflow_events_user_created",
    )

    # CI/CD Runs
    await db[CICD_RUNS_COLLECTION].create_index(
        [("owner", 1), ("repository", 1), ("started_at", -1)],
        name="idx_cicd_runs_owner_repo_started",
    )
    await db[CICD_RUNS_COLLECTION].create_index(
        "run_id",
        unique=True,
        name="idx_cicd_runs_id",
    )

    # CI/CD Provider Configs
    await db[CICD_PROVIDER_CONFIGS_COLLECTION].create_index(
        [("user_id", 1), ("provider", 1)],
        unique=True,
        name="idx_cicd_provider_configs_user_provider",
    )


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_workflow_id() -> str:
    return uuid.uuid4().hex


def _new_event_id() -> str:
    return uuid.uuid4().hex


def _new_cicd_run_id() -> str:
    return uuid.uuid4().hex


# ---------------------------------------------------------------------------
# Workflow CRUD
# ---------------------------------------------------------------------------


async def create_workflow(
    *,
    user_id: int | None,
    owner: str,
    repository: str,
    pull_request_number: int | None = None,
    trigger: str = "manual",
    provider: str = "github",
    initiated_by: str = "api",
    stages: list[str] | None = None,
    stage_sequence: list[str] | None = None,
) -> dict[str, Any]:
    db = get_db()
    now = _utcnow()
    workflow_id = uuid.uuid4().hex
    doc = {
        "workflow_id": workflow_id,
        "user_id": user_id,
        "owner": owner,
        "repository": repository,
        "pull_request_number": pull_request_number,
        "trigger": trigger,
        "provider": provider,
        "initiated_by": initiated_by,
        "status": "pending",
        "current_stage": RECEIVED_STAGE,
        "stages": [RECEIVED_STAGE],
        "stage_sequence": stage_sequence or [],
        "error": None,
        "duration_ms": None,
        "created_at": _utcnow(),
        "updated_at": _utcnow(),
        "completed_at": None,
        "events": [],
        "history": [{"stage": RECEIVED_STAGE, "at": now, "detail": None}],
    }
    await get_db()[WORKFLOWS_COLLECTION].insert_one(doc)
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


# ---------------------------------------------------------------------------
# Workflow Events
# ---------------------------------------------------------------------------


async def create_workflow_event(
    *,
    workflow_run_id: str,
    user_id: int | None,
    event_type: str,
    stage: str | None = None,
    metadata: dict[str, Any] | None = None,
    source: str = "api",
    triggered_by: int | None = None,
) -> dict[str, Any] | None:
    """Create a new workflow event."""
    db = get_db()
    event_id = uuid.uuid4().hex
    now = _utcnow()
    doc = {
        "event_id": uuid.uuid4().hex,
        "workflow_run_id": workflow_run_id,
        "user_id": None,  # Events are tied to workflow_run_id, not directly to user
        "event_type": event_type,
        "status": "pending",
        "stage": stage,
        "started_at": now,
        "completed_at": None,
        "duration_ms": None,
        "metadata": metadata or {},
        "error": None,
        "source": source,
        "triggered_by": triggered_by,
        "created_at": now,
    }
    try:
        await get_db()[WORKFLOW_EVENTS_COLLECTION].insert_one(doc)
        return doc
    except Exception:
        return None


async def start_workflow_event(
    workflow_run_id: str,
    event_id: str,
    metadata: dict[str, Any] | None = None,
) -> bool:
    """Mark an event as running."""
    db = get_db()
    now = _utcnow()
    result = await db[WORKFLOW_EVENTS_COLLECTION].update_one(
        {"event_id": event_id, "workflow_run_id": workflow_run_id},
        {"$set": {"status": "running", "started_at": now, "metadata": metadata}},
    )
    return result.modified_count > 0


async def complete_workflow_event(
    workflow_run_id: str,
    event_id: str,
    status: str = "completed",
    error: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> bool:
    """Mark an event as completed or failed."""
    db = get_db()
    now = _utcnow()
    update: dict[str, Any] = {
        "status": status,
        "completed_at": now,
        "duration_ms": None,  # Will be computed from started_at
    }
    if error:
        update["error"] = error
    if metadata:
        update["metadata"] = metadata

    # Try to get the event to compute duration
    event = await get_workflow_event(workflow_run_id, event_id)
    if event and event.get("started_at"):
        started = event["started_at"]
        if isinstance(started, datetime):
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            update["duration_ms"] = max(0, int((now - started).total_seconds() * 1000))

    result = await get_db()[WORKFLOW_EVENTS_COLLECTION].update_one(
        {"event_id": event_id, "workflow_run_id": workflow_run_id},
        {"$set": update},
    )
    return result.modified_count > 0


async def get_workflow_event(
    workflow_run_id: str,
    event_id: str,
) -> dict[str, Any] | None:
    db = get_db()
    return await db[WORKFLOW_EVENTS_COLLECTION].find_one(
        {"event_id": event_id, "workflow_run_id": workflow_run_id}
    )


async def list_workflow_events(
    *,
    workflow_run_id: str,
    user_id: int | None = None,
    page: int = 1,
    per_page: int = 50,
) -> dict[str, Any]:
    db = get_db()
    query: dict[str, Any] = {"workflow_run_id": workflow_run_id}
    total = await db[WORKFLOW_EVENTS_COLLECTION].count_documents(query)
    cursor = (
        db[WORKFLOW_EVENTS_COLLECTION]
        .find(query)
        .sort("started_at", 1)
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


async def list_workflow_events_by_user(
    *,
    user_id: int,
    page: int = 1,
    per_page: int = 50,
    event_type: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    """List workflow events for a user across all their workflow runs."""
    db = get_db()

    # First get the user's workflow run IDs
    workflows = await db[WORKFLOWS_COLLECTION].find(
        {"user_id": user_id}, {"workflow_id": 1}
    ).to_list(length=None)
    workflow_ids = [w["workflow_id"] for w in workflows]

    if not workflow_ids:
        return {"items": [], "total": 0, "page": 1, "per_page": per_page, "total_pages": 0}

    query: dict[str, Any] = {"workflow_run_id": {"$in": workflow_ids}}
    if event_type:
        query["event_type"] = event_type
    if status:
        query["status"] = status

    total = await db[WORKFLOW_EVENTS_COLLECTION].count_documents(query)
    cursor = (
        db[WORKFLOW_EVENTS_COLLECTION]
        .find(query)
        .sort("started_at", -1)
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


# ---------------------------------------------------------------------------
# CI/CD Runs
# ---------------------------------------------------------------------------


async def create_cicd_run(
    *,
    owner: str,
    repository: str,
    provider: str,
    workflow_name: str | None,
    branch: str,
    commit_sha: str,
    status: str = "pending",
    url: str | None = None,
    workflow_name_external: str | None = None,
    jobs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Record a CI/CD run from an external provider."""
    db = get_db()
    run_id = uuid.uuid4().hex
    now = _utcnow()
    doc = {
        "run_id": uuid.uuid4().hex,
        "owner": owner,
        "repository": repository,
        "provider": provider,
        "workflow_name": workflow_name,
        "branch": branch,
        "commit_sha": commit_sha,
        "status": status,
        "conclusion": None,
        "url": url,
        "started_at": None,
        "completed_at": None,
        "duration_seconds": None,
        "jobs": jobs or [],
        "created_at": now,
        "updated_at": now,
    }
    await db[CICD_RUNS_COLLECTION].insert_one(doc)
    return doc


async def update_cicd_run(
    run_id: str,
    status: str | None = None,
    conclusion: str | None = None,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
    jobs: list[dict[str, Any]] | None = None,
    url: str | None = None,
) -> bool:
    """Update a CI/CD run."""
    db = get_db()
    now = _utcnow()
    update: dict[str, Any] = {"updated_at": now}
    if status:
        update["status"] = status
    if conclusion:
        update["conclusion"] = conclusion
    if started_at:
        update["started_at"] = started_at
    if completed_at:
        update["completed_at"] = completed_at
        # Calculate duration if we have both start and end
        existing = await get_cicd_run(run_id)
        if existing and existing.get("started_at"):
            started = existing["started_at"]
            if isinstance(started, datetime):
                if started.tzinfo is None:
                    started = started.replace(tzinfo=timezone.utc)
                update["duration_seconds"] = max(0, int((completed_at - started).total_seconds()))
    if jobs is not None:
        update["jobs"] = jobs
    if url:
        update["url"] = url

    result = await db[CICD_RUNS_COLLECTION].update_one(
        {"run_id": run_id},
        {"$set": update},
    )
    return result.modified_count > 0


async def get_cicd_run(run_id: str) -> dict[str, Any] | None:
    db = get_db()
    return await db[CICD_RUNS_COLLECTION].find_one({"run_id": run_id})


async def list_cicd_runs(
    *,
    owner: str,
    repository: str,
    page: int = 1,
    per_page: int = 20,
    status: str | None = None,
) -> dict[str, Any]:
    db = get_db()
    query: dict[str, Any] = {"owner": owner, "repository": repository}
    if status:
        query["status"] = status
    total = await db[CICD_RUNS_COLLECTION].count_documents(query)
    cursor = (
        db[CICD_RUNS_COLLECTION]
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


# ---------------------------------------------------------------------------
# CI/CD Provider Configs
# ---------------------------------------------------------------------------


async def upsert_cicd_provider_config(
    *,
    user_id: int,
    provider: str,
    enabled: bool = True,
    external_url: str | None = None,
    api_token: str | None = None,
    webhook_secret: str | None = None,
    repository_patterns: list[str] | None = None,
    branch_patterns: list[str] | None = None,
) -> dict[str, Any]:
    db = get_db()
    now = _utcnow()
    doc = {
        "user_id": user_id,
        "provider": provider,
        "enabled": enabled,
        "external_url": external_url,
        "api_token": api_token,  # Should be encrypted in production
        "webhook_secret": webhook_secret,  # Should be encrypted in production
        "repository_patterns": repository_patterns or [],
        "branch_patterns": branch_patterns or [],
        "updated_at": now,
    }
    await db[CICD_PROVIDER_CONFIGS_COLLECTION].update_one(
        {"user_id": user_id, "provider": provider},
        {"$set": doc, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    return await db[CICD_PROVIDER_CONFIGS_COLLECTION].find_one(
        {"user_id": user_id, "provider": provider}
    )


async def get_cicd_provider_config(
    user_id: int,
    provider: str,
) -> dict[str, Any] | None:
    db = get_db()
    return await db[CICD_PROVIDER_CONFIGS_COLLECTION].find_one(
        {"user_id": user_id, "provider": provider}
    )


async def list_cicd_provider_configs(user_id: int) -> list[dict[str, Any]]:
    db = get_db()
    cursor = db[CICD_PROVIDER_CONFIGS_COLLECTION].find({"user_id": user_id})
    return [doc async for doc in cursor]


async def delete_cicd_provider_config(user_id: int, provider: str) -> bool:
    db = get_db()
    result = await db[CICD_PROVIDER_CONFIGS_COLLECTION].delete_one(
        {"user_id": user_id, "provider": provider}
    )
    return result.deleted_count > 0