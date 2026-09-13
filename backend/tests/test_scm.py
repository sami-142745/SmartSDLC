from __future__ import annotations

import asyncio

import httpx
import pytest

from app.services.gitlab_client import GitLabClient
from app.services.github_client import GitHubClient, GitHubAPIError
from app.services.scm import (
    ScmAPIError,
    ScmProvider,
    get_scm_client,
    merge_request_term,
)


def asyncio_run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def test_scm_provider_values():
    assert ScmProvider.github.value == "github"
    assert ScmProvider.gitlab.value == "gitlab"


def test_scm_api_error_is_github_api_error():
    err = ScmAPIError(404, "Not Found", "not_found")
    assert isinstance(err, GitHubAPIError)
    assert err.status_code == 404
    assert err.category == "not_found"


def test_merge_request_term_maps_provider():
    assert merge_request_term("github") == "pull request"
    assert merge_request_term("gitlab") == "merge request"
    assert merge_request_term(ScmProvider.gitlab) == "merge request"
    assert merge_request_term(ScmProvider.github) == "pull request"


def test_get_scm_client_returns_github_by_default():
    client = get_scm_client("github", "token")
    assert isinstance(client, GitHubClient)


def test_get_scm_client_returns_gitlab():
    client = get_scm_client("gitlab", "token")
    assert isinstance(client, GitLabClient)


def test_get_scm_client_returns_github_for_enum_value():
    client = get_scm_client(ScmProvider.github.value, "token")
    assert isinstance(client, GitHubClient)


def test_gitlab_error_is_catchable_as_github_api_error(monkeypatch):
    from app.services import gitlab_client as glc

    def handler(_request):
        return httpx.Response(401, json={"message": "401 Unauthorized"})

    monkeypatch.setattr(
        "app.services.gitlab_client._new_http_client",
        lambda **kw: httpx.AsyncClient(
            transport=httpx.MockTransport(handler), timeout=kw.get("timeout")
        ),
    )
    client = GitLabClient("token")
    with pytest.raises(GitHubAPIError):
        asyncio_run(client.get_user())