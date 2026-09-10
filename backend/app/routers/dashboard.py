from fastapi import APIRouter, Depends, Query

from app.schemas.dashboard import (
    DashboardSummary,
    HistoryResponse,
    RepoMetricsResponse,
    FeedbackSummary,
)
from app.services import dashboard_service
from app.services.security import get_current_user

router = APIRouter()


@router.get("/dashboard", response_model=DashboardSummary)
async def dashboard(user: dict = Depends(get_current_user)):
    return await dashboard_service.get_dashboard(user["github_id"])


@router.get("/history", response_model=HistoryResponse)
async def history(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    repository: str | None = Query(None),
    status: str | None = Query(None),
    user: dict = Depends(get_current_user),
):
    return await dashboard_service.get_history(
        user_id=user["github_id"],
        page=page,
        per_page=per_page,
        repository=repository,
        status=status,
    )


@router.get("/dashboard/repositories", response_model=RepoMetricsResponse)
async def repository_metrics(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    return await dashboard_service.get_repository_metrics(
        user_id=user["github_id"],
        page=page,
        per_page=per_page,
    )


@router.get("/dashboard/feedback-summary", response_model=FeedbackSummary)
async def feedback_summary(user: dict = Depends(get_current_user)):
    return await dashboard_service.get_feedback_summary(user["github_id"])