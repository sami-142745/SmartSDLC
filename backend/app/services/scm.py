from __future__ import annotations

from enum import Enum

from fastapi import HTTPException


class ScmProvider(str, Enum):
    github = "github"
    gitlab = "gitlab"


class ScmAPIError(Exception):
    def __init__(self, status_code: int, message: str, category: str = "unknown"):
        self.status_code = status_code
        self.message = message
        self.category = category
        super().__init__(message)


ERROR_STATUS_BY_CATEGORY = {
    "authentication": 401,
    "not_found": 404,
    "rate_limit": 429,
    "server": 502,
    "network": 503,
    "unknown": 502,
}


def scm_error_response(provider: ScmProvider, error: ScmAPIError) -> HTTPException:
    """Map a provider error to an HTTP error without killing the session.

    A 401 from the SCM provider must only surface as a real authentication
    failure for the GitHub provider. GitLab sync reuses the connected GitHub
    token, so a GitLab authentication rejection is a configuration problem,
    not a session problem: returning 401 would have the frontend clear the
    JWT and log the user out.
    """
    if provider is ScmProvider.gitlab and error.category == "authentication":
        return HTTPException(
            status_code=400,
            detail=(
                "GitLab sync could not authenticate. The connected GitHub token "
                "is not a valid GitLab access token; connect a GitLab Personal "
                "Access Token to sync GitLab repositories."
            ),
        )
    status_code = ERROR_STATUS_BY_CATEGORY.get(error.category, 502)
    return HTTPException(status_code=status_code, detail=error.message)


def merge_request_term(provider: str | ScmProvider) -> str:
    value = provider.value if isinstance(provider, ScmProvider) else provider
    return "merge request" if value == "gitlab" else "pull request"


def get_scm_client(provider: str, access_token: str, **kwargs):
    """Return the SCM client adapter for the given provider.

    Both adapters expose the same immutable interface so that review and
    documentation pipelines never need to know which provider they talk to.
    """
    if provider == ScmProvider.gitlab.value:
        from app.services.gitlab_client import GitLabClient

        return GitLabClient(access_token, **kwargs)
    from app.services.github_client import GitHubClient

    return GitHubClient(access_token, **kwargs)