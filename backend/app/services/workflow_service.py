from __future__ import annotations

import logging
from typing import Any

from app.services import workflow_repository

logger = logging.getLogger(__name__)

STAGE_SEQUENCE = (
    "RECEIVED",
    "VALIDATED",
    "FETCHING",
    "ANALYZING",
    "GENERATING_REVIEW",
    "PERSISTING",
    "COMPLETED",
)
FAILED_STAGE = "FAILED"


def _to_workflow(doc: dict[str, Any]) -> dict[str, Any]:
    history = [
        {
            "stage": entry.get("stage"),
            "at": entry.get("at"),
            "detail": entry.get("detail"),
        }
        for entry in (doc.get("history") or [])
    ]
    return {
        "workflow_id": doc.get("workflow_id"),
        "owner": doc.get("owner"),
        "repository": doc.get("repository"),
        "pull_request_number": doc.get("pull_request_number"),
        "trigger": doc.get("trigger", "manual"),
        "provider": doc.get("provider", "github"),
        "status": doc.get("status"),
        "stage": doc.get("stage"),
        "error": doc.get("error"),
        "review_id": doc.get("review_id"),
        "duration_ms": doc.get("duration_ms"),
        "history": history,
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }


async def begin_workflow(
    *,
    user_id: int | None,
    owner: str,
    repository: str,
    pull_request_number: int,
    trigger: str,
    provider: str = "github",
    initiated_by: str = "api",
) -> str | None:
    """Create a workflow record. Returns the workflow id or None (best effort)."""
    try:
        doc = await workflow_repository.create_workflow(
            user_id=user_id,
            owner=owner,
            repository=repository,
            pull_request_number=pull_request_number,
            trigger=trigger,
            provider=provider,
            initiated_by=initiated_by,
        )
        return doc["workflow_id"]
    except Exception:
        logger.exception("Failed to create workflow record; continuing without one")
        return None


async def advance_workflow(workflow_id: str | None, stage: str) -> None:
    if not workflow_id:
        return
    try:
        await workflow_repository.update_stage(workflow_id, stage)
    except Exception:
        logger.exception("Failed to advance workflow %s to %s", workflow_id, stage)


async def complete_workflow(workflow_id: str | None, review_id: str | None = None) -> None:
    if not workflow_id:
        return
    try:
        await workflow_repository.complete(workflow_id, review_id=review_id)
    except Exception:
        logger.exception("Failed to complete workflow %s", workflow_id)


async def fail_workflow(workflow_id: str | None, error: str | None = None) -> None:
    if not workflow_id:
        return
    try:
        await workflow_repository.fail(workflow_id, error=error)
    except Exception:
        logger.exception("Failed to mark workflow %s failed", workflow_id)


async def get_workflow(user_id: int, workflow_id: str) -> dict[str, Any] | None:
    doc = await workflow_repository.get_workflow(workflow_id, user_id=user_id)
    return _to_workflow(doc) if doc else None


async def list_workflows(
    user_id: int,
    *,
    page: int = 1,
    per_page: int = 20,
    status: str | None = None,
    repository: str | None = None,
) -> dict[str, Any]:
    data = await workflow_repository.list_workflows(
        user_id=user_id,
        page=page,
        per_page=per_page,
        status=status,
        repository=repository,
    )
    return {
        "items": [_to_workflow(doc) for doc in data["items"]],
        "page": data["page"],
        "per_page": data["per_page"],
        "total": data["total"],
        "total_pages": data["total_pages"],
    }