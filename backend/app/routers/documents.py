from fastapi import APIRouter, Depends, HTTPException, Query

from app.schemas.documentation import (
    DocumentationListResponse,
    DocumentationResponse,
    GenerateDocumentationRequest,
)
from app.services import document_repository, documentation_service
from app.services.github_client import GitHubAPIError, GitHubClient
from app.services.gitlab_client import GitLabClient
from app.services.scm import ScmProvider, scm_error_response
from app.services.security import get_current_user, require_github_token

router = APIRouter()


def _total_pages(total: int, per_page: int) -> int:
    if total <= 0:
        return 0
    return (total + per_page - 1) // per_page


@router.post("/documents/generate", response_model=DocumentationResponse)
async def generate_documentation(
    payload: GenerateDocumentationRequest,
    provider: ScmProvider = Query(ScmProvider.github),
    token: str = Depends(require_github_token),
    user: dict = Depends(get_current_user),
):
    client = (
        GitLabClient(token)
        if provider is ScmProvider.gitlab
        else GitHubClient(token)
    )
    try:
        return await documentation_service.generate_documentation(
            client,
            payload.owner,
            payload.repository,
            pull_request=payload.pull_request,
            user_id=user["github_id"],
        )
    except GitHubAPIError as e:
        raise scm_error_response(provider, e)
    except documentation_service.DocumentGenerationError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/documents/repository/{owner}/{repository}", response_model=DocumentationResponse)
async def get_repository_documentation(
    owner: str,
    repository: str,
    pull_request: int | None = Query(default=None, ge=1),
    user: dict = Depends(get_current_user),
):
    doc = await document_repository.get_latest_document(
        user["github_id"],
        owner,
        repository,
        pull_request,
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="No documentation found for this repository")
    return documentation_service.to_documentation_response(doc)


@router.get("/documents", response_model=DocumentationListResponse)
async def list_documentation(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    repository: str | None = Query(default=None),
    owner: str | None = Query(default=None),
    user: dict = Depends(get_current_user),
):
    data = await document_repository.list_documents(
        user["github_id"],
        page=page,
        per_page=per_page,
        repository=repository,
        owner=owner,
    )
    return {
        "items": [
            documentation_service.to_documentation_response(doc) for doc in data["items"]
        ],
        "page": data["page"],
        "per_page": data["per_page"],
        "total": data["total"],
        "total_pages": _total_pages(data["total"], data["per_page"]),
    }


@router.get("/documents/{document_id}", response_model=DocumentationResponse)
async def get_document(
    document_id: str,
    user: dict = Depends(get_current_user),
):
    doc = await document_repository.get_document(document_id, user["github_id"])
    if doc is None:
        raise HTTPException(status_code=404, detail="Documentation not found")
    return documentation_service.to_documentation_response(doc)