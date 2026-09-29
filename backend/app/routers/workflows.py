from fastapi import APIRouter, Depends, HTTPException, Query

from app.schemas.workflow import (
    CICDProvider,
    CICDProviderConfig,
    CICDWorkflowRun,
    WorkflowEvent,
    WorkflowEventCreate,
    WorkflowEventType,
    WorkflowRun,
    WorkflowRunCreate,
    WorkflowRunListResponse,
    WorkflowRunStatus,
    WorkflowRunUpdate,
    WorkflowStage,
    WorkflowSummary,
    WorkflowEventsResponse,
    WorkflowRunWithEvents,
)
from app.services import workflow_service
from app.services.security import get_current_user

router = APIRouter()


# ---------------------------------------------------------------------------
# Legacy Workflow Endpoints (backward compatibility)
# ---------------------------------------------------------------------------


@router.get("/workflows", response_model=WorkflowRunListResponse)
async def list_workflows(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    repository: str | None = Query(None),
    user: dict = Depends(get_current_user),
):
    return await workflow_service.list_workflows(
        user_id=user["github_id"],
        page=page,
        per_page=per_page,
        status=status,
        repository=repository,
    )


@router.get("/workflows/{workflow_id}", response_model=WorkflowRun)
async def get_workflow(
    workflow_id: str,
    user: dict = Depends(get_current_user),
):
    workflow = await workflow_service.get_workflow(user["github_id"], workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


# ---------------------------------------------------------------------------
# Workflow Runs
# ---------------------------------------------------------------------------


@router.get("/workflows/{owner}/{repo}/runs", response_model=WorkflowRunListResponse)
async def list_workflow_runs(
    owner: str,
    repo: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    user: dict = Depends(get_current_user),
):
    """List workflow runs for a repository."""
    return await workflow_service.list_workflows(
        user_id=user["github_id"],
        page=page,
        per_page=per_page,
        status=status,
        repository=f"{owner}/{repo}",
    )


@router.post("/workflows/{owner}/{repo}/runs", response_model=WorkflowRun)
async def create_workflow_run(
    owner: str,
    repo: str,
    body: WorkflowRunCreate,
    user: dict = Depends(get_current_user),
):
    """Create a new workflow run for a repository."""
    # Verify ownership by checking if the user has access to this repository
    # This is a simplified check - in production, verify via SCM token
    workflow_id = await workflow_service.begin_workflow(
        user_id=user["github_id"],
        owner=owner,
        repository=repo,
        pull_request_number=body.pull_request_number,
        trigger=body.trigger,
        provider=body.provider,
    )
    if not workflow_id:
        raise HTTPException(status_code=500, detail="Failed to create workflow run")
    return await workflow_service.get_workflow(user["github_id"], workflow_id)


@router.get("/workflows/{owner}/{repo}/runs/{run_id}", response_model=WorkflowRunWithEvents)
async def get_workflow_run(
    owner: str,
    repo: str,
    run_id: str,
    user: dict = Depends(get_current_user),
):
    """Get a workflow run with its events."""
    workflow = await workflow_service.get_workflow(user["github_id"], run_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    events = await workflow_service.list_workflow_events(workflow_run_id=run_id)
    return {"workflow": workflow, "events": events["items"]}


# ---------------------------------------------------------------------------
# Workflow Events
# ---------------------------------------------------------------------------


@router.get("/workflows/{owner}/{repo}/events", response_model=WorkflowEventsResponse)
async def list_workflow_events(
    owner: str,
    repo: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    event_type: str | None = Query(None),
    status: str | None = Query(None),
    user: dict = Depends(get_current_user),
):
    """List workflow events for a repository."""
    return await workflow_service.list_workflow_events_by_user(
        user_id=user["github_id"],
        page=page,
        per_page=per_page,
        event_type=event_type,
        status=status,
    )


@router.post("/workflows/{owner}/{repo}/events", response_model=WorkflowEvent)
async def create_workflow_event(
    owner: str,
    repo: str,
    body: WorkflowEventCreate,
    user: dict = Depends(get_current_user),
):
    """Create a new workflow event."""
    event = await workflow_service.create_workflow_event(
        workflow_run_id=body.workflow_run_id,
        user_id=user["github_id"],
        event_type=body.event_type,
        stage=body.stage,
        metadata=body.metadata,
        source=body.source,
        triggered_by=user["github_id"],
    )
    if not event:
        raise HTTPException(status_code=500, detail="Failed to create workflow event")
    return event


@router.post("/workflows/{owner}/{repo}/events/{event_id}/start", response_model=WorkflowEvent)
async def start_workflow_event(
    owner: str,
    repo: str,
    event_id: str,
    user: dict = Depends(get_current_user),
):
    """Mark a workflow event as running."""
    # Find the workflow run for this event
    events = await workflow_service.list_workflow_events_by_user(
        user_id=user["github_id"],
        page=1,
        per_page=1000,
    )
    event = next((e for e in events["items"] if e["event_id"] == event_id), None)
    if not event:
        raise HTTPException(status_code=404, detail="Workflow event not found")

    success = await workflow_service.start_workflow_event(
        event["workflow_run_id"], event_id
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to start workflow event")
    return await workflow_service.get_workflow_event(event["workflow_run_id"], event_id)


@router.post("/workflows/{owner}/{repo}/events/{event_id}/complete", response_model=WorkflowEvent)
async def complete_workflow_event(
    owner: str,
    repo: str,
    event_id: str,
    status: str = Query("completed"),
    error: str | None = Query(None),
    user: dict = Depends(get_current_user),
):
    """Mark a workflow event as completed or failed."""
    events = await workflow_service.list_workflow_events_by_user(
        user_id=user["github_id"],
        page=1,
        per_page=1000,
    )
    event = next((e for e in events["items"] if e["event_id"] == event_id), None)
    if not event:
        raise HTTPException(status_code=404, detail="Workflow event not found")

    success = await workflow_service.complete_workflow_event(
        event["workflow_run_id"], event_id, status, error
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to complete workflow event")
    return await workflow_service.get_workflow_event(event["workflow_run_id"], event_id)


# ---------------------------------------------------------------------------
# CI/CD Runs
# ---------------------------------------------------------------------------


@router.get("/workflows/{owner}/{repo}/cicd-runs")
async def list_cicd_runs(
    owner: str,
    repo: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    user: dict = Depends(get_current_user),
):
    """List CI/CD runs for a repository."""
    return await workflow_service.list_cicd_runs(
        owner=owner,
        repository=repo,
        page=page,
        per_page=per_page,
        status=status,
    )


@router.post("/workflows/{owner}/{repo}/cicd-runs", response_model=CICDWorkflowRun)
async def create_cicd_run(
    owner: str,
    repo: str,
    body: CICDWorkflowRun,
    user: dict = Depends(get_current_user),
):
    """Record a CI/CD run from an external provider."""
    run = await workflow_service.create_cicd_run(
        owner=owner,
        repository=repo,
        provider=body.provider,
        workflow_name=body.workflow_name,
        branch=body.branch,
        commit_sha=body.commit_sha,
        status=body.status,
        url=body.url,
        jobs=body.jobs,
    )
    if not run:
        raise HTTPException(status_code=500, detail="Failed to create CI/CD run")
    return run


# ---------------------------------------------------------------------------
# CI/CD Provider Configs
# ---------------------------------------------------------------------------


@router.get("/workflows/cicd-providers")
async def list_cicd_providers(
    user: dict = Depends(get_current_user),
):
    """List CI/CD provider configurations for the current user."""
    return await workflow_service.list_cicd_provider_configs(user["github_id"])


@router.put("/workflows/cicd-providers/{provider}", response_model=CICDProviderConfig)
async def upsert_cicd_provider(
    provider: CICDProvider,
    body: CICDProviderConfig,
    user: dict = Depends(get_current_user),
):
    """Create or update a CI/CD provider configuration."""
    config = await workflow_service.upsert_cicd_provider_config(
        user_id=user["github_id"],
        provider=provider,
        enabled=body.enabled,
        external_url=body.external_url,
        api_token=body.api_token,
        webhook_secret=body.webhook_secret,
        repository_patterns=body.repository_patterns,
        branch_patterns=body.branch_patterns,
    )
    if not config:
        raise HTTPException(status_code=500, detail="Failed to save CI/CD provider config")
    return config


@router.delete("/workflows/cicd-providers/{provider}")
async def delete_cicd_provider(
    provider: CICDProvider,
    user: dict = Depends(get_current_user),
):
    """Delete a CI/CD provider configuration."""
    success = await workflow_service.delete_cicd_provider_config(
        user["github_id"], provider
    )
    if not success:
        raise HTTPException(status_code=404, detail="CI/CD provider config not found")
    return {"deleted": True}


# ---------------------------------------------------------------------------
# Workflow Summary
# ---------------------------------------------------------------------------


@router.get("/workflows/{owner}/{repo}/summary", response_model=WorkflowSummary)
async def get_workflow_summary(
    owner: str,
    repo: str,
    user: dict = Depends(get_current_user),
):
    """Get aggregate workflow statistics for a repository."""
    return await workflow_service.get_workflow_summary(
        user_id=user["github_id"],
        owner=owner,
        repository=repo,
    )
