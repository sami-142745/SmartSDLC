from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from app.schemas.workflow import (
    CICDProvider,
    CICDProviderConfig,
    CICDWorkflowRun,
    WorkflowEvent,
    WorkflowEventCreate,
    WorkflowEventType,
    WorkflowRun,
    WorkflowRunCreate,
    WorkflowRunStatus,
    WorkflowRunUpdate,
    WorkflowStage,
    WorkflowStageSummary,
    WorkflowSummary,
    DEFAULT_STAGE_SEQUENCE,
)
from app.services import workflow_repository

logger = logging.getLogger(__name__)

# Legacy stage constants for backward compatibility
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


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _to_workflow(doc: dict[str, Any]) -> dict[str, Any]:
    """Convert a workflow document to the API response format."""
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


def _to_event(doc: dict[str, Any]) -> dict[str, Any]:
    """Convert a workflow event document to the API response format."""
    return {
        "event_id": doc.get("event_id"),
        "workflow_run_id": doc.get("workflow_run_id"),
        "event_type": doc.get("event_type"),
        "status": doc.get("status"),
        "stage": doc.get("stage"),
        "started_at": doc.get("started_at"),
        "completed_at": doc.get("completed_at"),
        "duration_ms": doc.get("duration_ms"),
        "metadata": doc.get("metadata", {}),
        "error": doc.get("error"),
        "source": doc.get("source", "api"),
        "triggered_by": doc.get("triggered_by"),
    }


def _to_cicd_run(doc: dict[str, Any]) -> dict[str, Any]:
    """Convert a CI/CD run document to the API response format."""
    return {
        "run_id": doc.get("run_id"),
        "provider": doc.get("provider"),
        "owner": doc.get("owner"),
        "repository": doc.get("repository"),
        "workflow_name": doc.get("workflow_name"),
        "branch": doc.get("branch"),
        "commit_sha": doc.get("commit_sha"),
        "status": doc.get("status"),
        "conclusion": doc.get("conclusion"),
        "url": doc.get("url"),
        "started_at": doc.get("started_at"),
        "completed_at": doc.get("completed_at"),
        "duration_seconds": doc.get("duration_seconds"),
        "jobs": doc.get("jobs", []),
    }


# ---------------------------------------------------------------------------
# Legacy Workflow Operations (backward compatibility)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Workflow Events
# ---------------------------------------------------------------------------


async def create_workflow_event(
    *,
    workflow_run_id: str,
    user_id: int | None,
    event_type: WorkflowEventType | str,
    stage: WorkflowStage | str | None = None,
    metadata: dict[str, Any] | None = None,
    source: str = "api",
    triggered_by: int | None = None,
) -> dict[str, Any] | None:
    """Create a new workflow event."""
    try:
        doc = await workflow_repository.create_workflow_event(
            workflow_run_id=workflow_run_id,
            user_id=user_id,
            event_type=str(event_type),
            stage=str(stage) if stage else None,
            metadata=metadata,
            source=source,
            triggered_by=triggered_by,
        )
        return _to_event(doc) if doc else None
    except Exception:
        logger.exception("Failed to create workflow event")
        return None


async def start_workflow_event(
    workflow_run_id: str,
    event_id: str,
    metadata: dict[str, Any] | None = None,
) -> bool:
    """Mark an event as running."""
    try:
        return await workflow_repository.start_workflow_event(
            workflow_run_id, event_id, metadata
        )
    except Exception:
        logger.exception("Failed to start workflow event")
        return False


async def complete_workflow_event(
    workflow_run_id: str,
    event_id: str,
    status: str = "completed",
    error: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> bool:
    """Mark an event as completed or failed."""
    try:
        return await workflow_repository.complete_workflow_event(
            workflow_run_id, event_id, status, error, metadata
        )
    except Exception:
        logger.exception("Failed to complete workflow event")
        return False


async def get_workflow_event(
    workflow_run_id: str,
    event_id: str,
) -> dict[str, Any] | None:
    doc = await workflow_repository.get_workflow_event(workflow_run_id, event_id)
    return _to_event(doc) if doc else None


async def list_workflow_events(
    *,
    workflow_run_id: str,
    user_id: int | None = None,
    page: int = 1,
    per_page: int = 50,
) -> dict[str, Any]:
    data = await workflow_repository.list_workflow_events(
        workflow_run_id=workflow_run_id,
        user_id=user_id,
        page=page,
        per_page=per_page,
    )
    return {
        "items": [_to_event(doc) for doc in data["items"]],
        "page": data["page"],
        "per_page": data["per_page"],
        "total": data["total"],
        "total_pages": data["total_pages"],
    }


async def list_workflow_events_by_user(
    *,
    user_id: int,
    page: int = 1,
    per_page: int = 50,
    event_type: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    data = await workflow_repository.list_workflow_events_by_user(
        user_id=user_id,
        page=page,
        per_page=per_page,
        event_type=event_type,
        status=status,
    )
    return {
        "items": [_to_event(doc) for doc in data["items"]],
        "page": data["page"],
        "per_page": data["per_page"],
        "total": data["total"],
        "total_pages": data["total_pages"],
    }


# ---------------------------------------------------------------------------
# CI/CD Runs
# ---------------------------------------------------------------------------


async def create_cicd_run(
    *,
    owner: str,
    repository: str,
    provider: CICDProvider | str,
    workflow_name: str | None,
    branch: str,
    commit_sha: str,
    status: str = "pending",
    url: str | None = None,
    jobs: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Record a CI/CD run from an external provider."""
    try:
        doc = await workflow_repository.create_cicd_run(
            owner=owner,
            repository=repository,
            provider=str(provider),
            workflow_name=workflow_name,
            branch=branch,
            commit_sha=commit_sha,
            status=status,
            url=url,
            jobs=jobs,
        )
        return _to_cicd_run(doc) if doc else None
    except Exception:
        logger.exception("Failed to create CI/CD run")
        return None


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
    try:
        return await workflow_repository.update_cicd_run(
            run_id, status, conclusion, started_at, completed_at, jobs, url
        )
    except Exception:
        logger.exception("Failed to update CI/CD run")
        return False


async def get_cicd_run(run_id: str) -> dict[str, Any] | None:
    doc = await workflow_repository.get_cicd_run(run_id)
    return _to_cicd_run(doc) if doc else None


async def list_cicd_runs(
    *,
    owner: str,
    repository: str,
    page: int = 1,
    per_page: int = 20,
    status: str | None = None,
) -> dict[str, Any]:
    data = await workflow_repository.list_cicd_runs(
        owner=owner,
        repository=repository,
        page=page,
        per_page=per_page,
        status=status,
    )
    return {
        "items": [_to_cicd_run(doc) for doc in data["items"]],
        "page": data["page"],
        "per_page": data["per_page"],
        "total": data["total"],
        "total_pages": data["total_pages"],
    }


# ---------------------------------------------------------------------------
# CI/CD Provider Configs
# ---------------------------------------------------------------------------


async def upsert_cicd_provider_config(
    *,
    user_id: int,
    provider: CICDProvider | str,
    enabled: bool = True,
    external_url: str | None = None,
    api_token: str | None = None,
    webhook_secret: str | None = None,
    repository_patterns: list[str] | None = None,
    branch_patterns: list[str] | None = None,
) -> dict[str, Any] | None:
    try:
        doc = await workflow_repository.upsert_cicd_provider_config(
            user_id=user_id,
            provider=str(provider),
            enabled=enabled,
            external_url=external_url,
            api_token=api_token,
            webhook_secret=webhook_secret,
            repository_patterns=repository_patterns,
            branch_patterns=branch_patterns,
        )
        return doc
    except Exception:
        logger.exception("Failed to upsert CI/CD provider config")
        return None


async def get_cicd_provider_config(
    user_id: int,
    provider: CICDProvider | str,
) -> dict[str, Any] | None:
    return await workflow_repository.get_cicd_provider_config(user_id, str(provider))


async def list_cicd_provider_configs(user_id: int) -> list[dict[str, Any]]:
    return await workflow_repository.list_cicd_provider_configs(user_id)


async def delete_cicd_provider_config(user_id: int, provider: CICDProvider | str) -> bool:
    return await workflow_repository.delete_cicd_provider_config(user_id, str(provider))


# ---------------------------------------------------------------------------
# Workflow Summary
# ---------------------------------------------------------------------------


async def get_workflow_summary(
    *,
    user_id: int,
    owner: str,
    repository: str | None = None,
) -> dict[str, Any]:
    """Get aggregate workflow statistics."""
    # Get all workflows for this user/repo
    data = await workflow_repository.list_workflows(
        user_id=user_id,
        page=1,
        per_page=1000,
        repository=repository,
    )
    workflows = data["items"]

    total = len(workflows)
    successful = sum(1 for w in workflows if w.get("status") == "completed")
    failed = sum(1 for w in workflows if w.get("status") == "failed")
    running = sum(1 for w in workflows if w.get("status") in ("running", "pending"))

    durations = [w.get("duration_ms") for w in workflows if w.get("duration_ms")]
    avg_duration = int(sum(durations) / len(durations)) if durations else None

    # Stage summaries
    stage_counts: dict[str, dict[str, int]] = {}
    for w in workflows:
        for event in w.get("events", []):
            stage = event.get("stage")
            if stage:
                if stage not in stage_counts:
                    stage_counts[stage] = {"total": 0, "completed": 0, "failed": 0}
                stage_counts[stage]["total"] += 1
                if event.get("status") == "completed":
                    stage_counts[stage]["completed"] += 1
                elif event.get("status") == "failed":
                    stage_counts[stage]["failed"] += 1

    stage_summaries = []
    for stage, counts in stage_counts.items():
        total_runs = counts["total"]
        completed = counts["completed"]
        failed = counts["failed"]
        success_rate = completed / total_runs if total_runs > 0 else 0.0
        stage_summaries.append(
            {
                "stage": stage,
                "total_runs": total_runs,
                "completed_runs": completed,
                "failed_runs": failed,
                "success_rate": round(success_rate, 4),
            }
        )

    return {
        "owner": owner,
        "repository": repository,
        "total_runs": total,
        "successful_runs": successful,
        "failed_runs": failed,
        "running_runs": running,
        "average_duration_ms": avg_duration,
        "stage_summaries": stage_summaries,
        "recent_runs": workflows[:10],
    }
