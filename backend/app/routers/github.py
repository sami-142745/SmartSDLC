from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from app.services.github_client import GitHubAPIError, GitHubClient
from app.services.github_oauth import OAuthError, github_oauth
from app.services.security import get_current_user, require_github_token
from app.services.user_repository import upsert_github_user

router = APIRouter()

_ERROR_STATUS_BY_CATEGORY = {
    "authentication": 401,
    "not_found": 404,
    "rate_limit": 429,
    "server": 502,
    "network": 503,
    "unknown": 502,
}


class Repository(BaseModel):
    id: int
    name: str
    full_name: str
    private: bool
    html_url: str
    default_branch: str | None = None
    owner: str | None = None


class RepositoryListResponse(BaseModel):
    repositories: list[Repository]
    page: int
    per_page: int
    has_more: bool


class PullRequestSummary(BaseModel):
    number: int
    title: str
    state: str
    user: str | None = None
    html_url: str
    created_at: str | None = None
    updated_at: str | None = None
    head: str | None = None
    base: str | None = None


class PullRequestListResponse(BaseModel):
    pull_requests: list[PullRequestSummary]
    page: int
    per_page: int
    has_more: bool


class PullRequestFile(BaseModel):
    filename: str
    status: str
    additions: int
    deletions: int
    changes: int
    patch: str | None = None


def _error_from_github(e: GitHubAPIError) -> HTTPException:
    status_code = _ERROR_STATUS_BY_CATEGORY.get(e.category, 502)
    return HTTPException(status_code=status_code, detail=e.message)


class GitHubConnectRequest(BaseModel):
    token: str = Field(..., min_length=1)


class GitHubConnectResponse(BaseModel):
    connected: bool
    login: str


@router.post("/github/connect", response_model=GitHubConnectResponse)
async def github_connect(
    payload: GitHubConnectRequest,
    user: dict[str, Any] = Depends(get_current_user),
):
    try:
        profile = await github_oauth.fetch_user_profile(payload.token)
    except OAuthError as e:
        raise HTTPException(status_code=401, detail=str(e))

    if int(profile.get("id")) != int(user["github_id"]):
        raise HTTPException(
            status_code=400,
            detail="GitHub token belongs to a different account",
        )

    await upsert_github_user(profile, payload.token)
    return {"connected": True, "login": profile.get("login")}


@router.get("/repositories", response_model=RepositoryListResponse)
async def list_repositories(
    page: int = Query(1, ge=1),
    per_page: int = Query(30, ge=1, le=100),
    token: str = Depends(require_github_token),
):
    try:
        result = await GitHubClient(token).list_repositories(page=page, per_page=per_page)
    except GitHubAPIError as e:
        raise _error_from_github(e)
    return result


@router.get("/pullrequests", response_model=PullRequestListResponse)
async def list_pullrequests(
    owner: str = Query(..., min_length=1),
    repo: str = Query(..., min_length=1),
    state: str = Query("open", pattern="^(open|closed|all)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(30, ge=1, le=100),
    token: str = Depends(require_github_token),
):
    try:
        result = await GitHubClient(token).list_pull_requests(
            owner=owner,
            repo=repo,
            state=state,
            page=page,
            per_page=per_page,
        )
    except GitHubAPIError as e:
        raise _error_from_github(e)
    return result


@router.get("/pullrequests/{owner}/{repo}/{number}", response_model=PullRequestSummary)
async def get_pull_request(
    owner: str,
    repo: str,
    number: int,
    token: str = Depends(require_github_token),
):
    try:
        result = await GitHubClient(token).get_pull_request(owner, repo, number)
    except GitHubAPIError as e:
        raise _error_from_github(e)
    return result


@router.get("/pullrequests/{owner}/{repo}/{number}/files", response_model=list[PullRequestFile])
async def get_pull_request_files(
    owner: str,
    repo: str,
    number: int,
    token: str = Depends(require_github_token),
):
    try:
        result = await GitHubClient(token).get_pull_request_files(owner, repo, number)
    except GitHubAPIError as e:
        raise _error_from_github(e)
    return result


@router.get("/pullrequests/{owner}/{repo}/{number}/diff")
async def get_pull_request_diff(
    owner: str,
    repo: str,
    number: int,
    token: str = Depends(require_github_token),
):
    try:
        diff = await GitHubClient(token).get_pull_request_diff(owner, repo, number)
    except GitHubAPIError as e:
        raise _error_from_github(e)
    return PlainTextResponse(diff, media_type="text/plain")