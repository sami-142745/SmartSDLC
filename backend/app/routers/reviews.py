from fastapi import APIRouter, Depends, HTTPException, Query

from app.schemas.dashboard import FeedbackHistoryResponse, FeedbackItem, FeedbackRequest
from app.schemas.review import ReviewResponse
from app.services.github_client import GitHubAPIError, GitHubClient
from app.services.gitlab_client import GitLabClient
from app.services.scm import ScmProvider, scm_error_response
from app.services import dashboard_service, review_repository, workflow_service
from app.services.review_service import run_review
from app.services.security import get_current_user, require_github_token

router = APIRouter()


def _client_for(provider: ScmProvider, token: str) -> GitHubClient | GitLabClient:
    if provider is ScmProvider.gitlab:
        return GitLabClient(token)
    return GitHubClient(token)


@router.post("/reviews/{owner}/{repo}/{number}", response_model=ReviewResponse)
async def create_review(
    owner: str,
    repo: str,
    number: int,
    provider: ScmProvider = Query(ScmProvider.github),
    token: str = Depends(require_github_token),
    user: dict = Depends(get_current_user),
):
    user_id = user["github_id"]
    workflow_id = await workflow_service.begin_workflow(
        user_id=user_id,
        owner=owner,
        repository=repo,
        pull_request_number=number,
        trigger="manual",
        initiated_by="api",
        provider=provider.value,
    )
    if workflow_id:
        await workflow_service.advance_workflow(workflow_id, "VALIDATED")

    async def progress(stage: str) -> None:
        await workflow_service.advance_workflow(workflow_id, stage)

    try:
        result = await run_review(
            _client_for(provider, token),
            owner,
            repo,
            number,
            user_id=user_id,
            progress=progress,
        )
        await workflow_service.complete_workflow(workflow_id, review_id=result.get("review_id"))
        return result
    except GitHubAPIError as e:
        await workflow_service.fail_workflow(workflow_id, error=e.message)
        raise scm_error_response(provider, e)
    except Exception as e:
        await workflow_service.fail_workflow(workflow_id, error=str(e) or "Unexpected review failure")
        raise


@router.get("/reviews/{owner}/{repo}/{number}", response_model=list[ReviewResponse])
async def list_reviews(
    owner: str,
    repo: str,
    number: int,
    token: str = Depends(require_github_token),
):
    reviews = await review_repository.list_reviews(owner, repo, number)
    for review in reviews:
        review["findings"] = await review_repository.list_findings(str(review["_id"]))
    return reviews


@router.get("/reviews/{owner}/{repo}/{number}/findings")
async def list_review_findings(
    owner: str,
    repo: str,
    number: int,
    token: str = Depends(require_github_token),
):
    reviews = await review_repository.list_reviews(owner, repo, number)
    if not reviews:
        raise HTTPException(status_code=404, detail="No reviews found for this pull request")
    findings = await review_repository.list_findings(str(reviews[0]["_id"]))
    return {"review_id": str(reviews[0]["_id"]), "findings": findings}


@router.post(
    "/reviews/{owner}/{repo}/{number}/findings/{finding_id}/feedback",
    response_model=FeedbackItem,
)
async def submit_finding_feedback(
    owner: str,
    repo: str,
    number: int,
    finding_id: str,
    payload: FeedbackRequest,
    user: dict = Depends(get_current_user),
):
    return await dashboard_service.submit_feedback(
        user_id=user["github_id"],
        owner=owner,
        repository=repo,
        pull_request_number=number,
        finding_id=finding_id,
        action=payload.action,
    )


@router.get("/reviews/feedback", response_model=FeedbackHistoryResponse)
async def list_feedback_history(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    return await dashboard_service.get_feedback_history(
        user_id=user["github_id"],
        page=page,
        per_page=per_page,
    )