from fastapi import APIRouter, Depends, HTTPException, Query

from app.schemas.insight import (
    GenerateInsightRequest,
    InsightListResponse,
    InsightReport,
)
from app.services import insight_service
from app.services.security import get_current_user

router = APIRouter()


def _total_pages(total: int, per_page: int) -> int:
    if total <= 0:
        return 0
    return (total + per_page - 1) // per_page


@router.post("/insights/generate", response_model=InsightReport)
async def generate_insight(
    payload: GenerateInsightRequest,
    user: dict = Depends(get_current_user),
):
    try:
        return await insight_service.generate_insight(
            user_id=user["github_id"],
            owner=payload.owner,
            repository=payload.repository,
            pull_request=payload.pull_request,
            generate_narrative=payload.generate_narrative,
        )
    except insight_service.InsightGenerationError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/insights/repository/{owner}/{repository}", response_model=InsightReport)
async def get_repository_insight(
    owner: str,
    repository: str,
    pull_request: int | None = Query(default=None, ge=1),
    report_type: str | None = Query(default=None),
    user: dict = Depends(get_current_user),
):
    report = await insight_service.get_latest_report(
        user["github_id"],
        owner,
        repository,
        pull_request=pull_request,
        report_type=report_type,
    )
    if report is None:
        raise HTTPException(status_code=404, detail="No insight report found for this repository")
    return report


@router.get("/insights", response_model=InsightListResponse)
async def list_insights(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    repository: str | None = Query(default=None),
    report_type: str | None = Query(default=None),
    user: dict = Depends(get_current_user),
):
    data = await insight_service.list_reports(
        user["github_id"],
        page=page,
        per_page=per_page,
        repository=repository,
        report_type=report_type,
    )
    return {
        "items": data["items"],
        "page": data["page"],
        "per_page": data["per_page"],
        "total": data["total"],
        "total_pages": _total_pages(data["total"], data["per_page"]),
    }


@router.get("/insights/{insight_id}", response_model=InsightReport)
async def get_insight(
    insight_id: str,
    user: dict = Depends(get_current_user),
):
    report = await insight_service.get_insight_report(insight_id, user["github_id"])
    if report is None:
        raise HTTPException(status_code=404, detail="Insight report not found")
    return report