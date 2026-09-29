"""HTTP surface for the Repository Intelligence module.

All routes require a connected SCM token (``require_github_token``) because every
analysis reads live provider data; results are then cached server-side so
repeated views do not re-query the provider. Provider failures are mapped
through :func:`app.services.scm.scm_error_response`, which keeps a provider
authentication problem from logging the user out of SmartSDLC.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.schemas.repository_intelligence import (
    DependencyReport,
    LanguageBreakdown,
    ReadmeIntelligence,
    RepositoryDashboard,
    RepositoryFileContent,
    RepositoryHealth,
    RepositoryTree,
)
from app.services import repository_intelligence_service
from app.services.repository_intelligence_service import RepositoryIntelligenceError
from app.services.scm import ScmAPIError, ScmProvider, scm_error_response
from app.services.security import get_current_user, require_github_token

router = APIRouter()

BASE = "/repository-intelligence"


def _translate(provider: ScmProvider, error: RepositoryIntelligenceError) -> HTTPException:
    """Map a "this data does not exist" failure onto a 404."""
    return HTTPException(status_code=404, detail=str(error))


@router.get(f"{BASE}/repositories", response_model=list[dict[str, Any]])
async def list_cached_repositories(user: dict[str, Any] = Depends(get_current_user)):
    """Repositories with a live cached analysis, newest first."""
    return await repository_intelligence_service.list_cached_repositories(user["github_id"])


@router.get(f"{BASE}/repositories/{{owner}}/{{repo}}/dashboard", response_model=RepositoryDashboard)
async def get_repository_dashboard(
    owner: str,
    repo: str,
    provider: ScmProvider = Query(ScmProvider.github),
    refresh: bool = Query(False),
    user: dict[str, Any] = Depends(get_current_user),
    token: str = Depends(require_github_token),
):
    try:
        return await repository_intelligence_service.get_dashboard(
            user["github_id"], token, provider, owner, repo, refresh=refresh
        )
    except ScmAPIError as e:
        raise scm_error_response(provider, e)
    except RepositoryIntelligenceError as e:
        raise _translate(provider, e)


@router.get(f"{BASE}/repositories/{{owner}}/{{repo}}/health", response_model=RepositoryHealth)
async def get_repository_health(
    owner: str,
    repo: str,
    provider: ScmProvider = Query(ScmProvider.github),
    refresh: bool = Query(False),
    user: dict[str, Any] = Depends(get_current_user),
    token: str = Depends(require_github_token),
):
    try:
        return await repository_intelligence_service.get_health(
            user["github_id"], token, provider, owner, repo, refresh=refresh
        )
    except ScmAPIError as e:
        raise scm_error_response(provider, e)


@router.get(
    f"{BASE}/repositories/{{owner}}/{{repo}}/languages",
    response_model=LanguageBreakdown,
)
async def get_repository_languages(
    owner: str,
    repo: str,
    provider: ScmProvider = Query(ScmProvider.github),
    refresh: bool = Query(False),
    user: dict[str, Any] = Depends(get_current_user),
    token: str = Depends(require_github_token),
):
    try:
        return await repository_intelligence_service.get_languages(
            user["github_id"], token, provider, owner, repo, refresh=refresh
        )
    except ScmAPIError as e:
        raise scm_error_response(provider, e)


@router.get(
    f"{BASE}/repositories/{{owner}}/{{repo}}/dependencies",
    response_model=DependencyReport,
)
async def get_repository_dependencies(
    owner: str,
    repo: str,
    provider: ScmProvider = Query(ScmProvider.github),
    refresh: bool = Query(False),
    user: dict[str, Any] = Depends(get_current_user),
    token: str = Depends(require_github_token),
):
    try:
        return await repository_intelligence_service.get_dependencies(
            user["github_id"], token, provider, owner, repo, refresh=refresh
        )
    except ScmAPIError as e:
        raise scm_error_response(provider, e)


@router.get(
    f"{BASE}/repositories/{{owner}}/{{repo}}/readme",
    response_model=ReadmeIntelligence,
)
async def get_repository_readme(
    owner: str,
    repo: str,
    provider: ScmProvider = Query(ScmProvider.github),
    refresh: bool = Query(False),
    user: dict[str, Any] = Depends(get_current_user),
    token: str = Depends(require_github_token),
):
    try:
        return await repository_intelligence_service.get_readme(
            user["github_id"], token, provider, owner, repo, refresh=refresh
        )
    except ScmAPIError as e:
        raise scm_error_response(provider, e)


@router.get(f"{BASE}/repositories/{{owner}}/{{repo}}/tree", response_model=RepositoryTree)
async def get_repository_tree(
    owner: str,
    repo: str,
    ref: str | None = Query(default=None, min_length=1),
    provider: ScmProvider = Query(ScmProvider.github),
    refresh: bool = Query(False),
    user: dict[str, Any] = Depends(get_current_user),
    token: str = Depends(require_github_token),
):
    try:
        return await repository_intelligence_service.get_tree(
            user["github_id"], token, provider, owner, repo, ref=ref, refresh=refresh
        )
    except ScmAPIError as e:
        raise scm_error_response(provider, e)


@router.get(
    f"{BASE}/repositories/{{owner}}/{{repo}}/file",
    response_model=RepositoryFileContent,
)
async def get_repository_file(
    owner: str,
    repo: str,
    path: str = Query(..., min_length=1),
    ref: str | None = Query(default=None, min_length=1),
    provider: ScmProvider = Query(ScmProvider.github),
    user: dict[str, Any] = Depends(get_current_user),
    token: str = Depends(require_github_token),
):
    try:
        return await repository_intelligence_service.get_file(
            user["github_id"], token, provider, owner, repo, path, ref=ref
        )
    except ScmAPIError as e:
        raise scm_error_response(provider, e)
    except RepositoryIntelligenceError as e:
        raise _translate(provider, e)


@router.delete(f"{BASE}/repositories/{{owner}}/{{repo}}/cache")
async def invalidate_repository_cache(
    owner: str,
    repo: str,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Drop cached analysis for a repository so the next read recomputes."""
    removed = await repository_intelligence_service.invalidate(
        user["github_id"], owner, repo
    )
    return {"owner": owner, "repository": repo, "invalidated": removed}
