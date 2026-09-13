from fastapi import APIRouter, Depends, HTTPException, Query

from app.schemas.workflow import Workflow, WorkflowListResponse
from app.services import workflow_service
from app.services.security import get_current_user

router = APIRouter()


@router.get("/workflows", response_model=WorkflowListResponse)
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


@router.get("/workflows/{workflow_id}", response_model=Workflow)
async def get_workflow(
    workflow_id: str,
    user: dict = Depends(get_current_user),
):
    workflow = await workflow_service.get_workflow(user["github_id"], workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow