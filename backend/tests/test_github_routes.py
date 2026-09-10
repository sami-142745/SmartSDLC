import pytest

from app.services.github_client import GitHubAPIError
from app.services.jwt_service import create_access_token

REPO = {
    "id": 1,
    "name": "Hello-World",
    "full_name": "octocat/Hello-World",
    "private": False,
    "html_url": "https://github.com/octocat/Hello-World",
    "default_branch": "main",
    "owner": "octocat",
}

PR = {
    "number": 12,
    "title": "Fix bug",
    "state": "open",
    "user": "octocat",
    "html_url": "https://github.com/octocat/Hello-World/pull/12",
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-02T00:00:00Z",
    "head": "feature/fix",
    "base": "main",
}


class FakeGitHubClient:
    errors: dict = {}

    def __init__(self, token):
        self.token = token

    async def list_repositories(self, page=1, per_page=30):
        self._raise("list_repositories")
        return {"repositories": [REPO], "page": page, "per_page": per_page, "has_more": False}

    async def list_pull_requests(self, owner, repo, state="open", page=1, per_page=30):
        self._raise("list_pull_requests")
        return {"pull_requests": [PR], "page": page, "per_page": per_page, "has_more": False}

    async def get_pull_request(self, owner, repo, number):
        self._raise("get_pull_request")
        return PR

    async def get_pull_request_files(self, owner, repo, number):
        self._raise("get_pull_request_files")
        return [{"filename": "app/main.py", "status": "modified", "additions": 3, "deletions": 1, "changes": 4, "patch": "@@ -1 +1,3 @@"}]

    async def get_pull_request_diff(self, owner, repo, number):
        self._raise("get_pull_request_diff")
        return "diff --git a/app/main.py b/app/main.py\n"

    def _raise(self, key):
        err = FakeGitHubClient.errors.get(key)
        if err:
            raise err


@pytest.fixture(autouse=True)
def _reset_fake(monkeypatch):
    FakeGitHubClient.errors = {}
    monkeypatch.setattr("app.routers.github.GitHubClient", FakeGitHubClient)


@pytest.fixture
def auth_headers(monkeypatch):
    async def known_user(github_id):
        return {"github_id": github_id, "login": "octocat", "github_access_token": "gho_test"}

    monkeypatch.setattr("app.services.security.get_user_by_github_id", known_user)
    return {"Authorization": f"Bearer {create_access_token({'sub': '7', 'login': 'octocat'})}"}


def test_list_repositories_returns_repos(client, auth_headers):
    resp = client.get("/repositories", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["repositories"][0]["full_name"] == "octocat/Hello-World"
    assert "gho_test" not in str(body)


def test_list_repositories_requires_connected_github(client, monkeypatch):
    async def known_user_without_token(github_id):
        return {"github_id": github_id, "login": "octocat"}

    monkeypatch.setattr("app.services.security.get_user_by_github_id", known_user_without_token)
    headers = {"Authorization": f"Bearer {create_access_token({'sub': '7', 'login': 'octocat'})}"}
    resp = client.get("/repositories", headers=headers)
    assert resp.status_code == 401
    assert resp.json()["detail"] == "GitHub account is not connected"


def test_list_pullrequests_requires_owner_and_repo(client, auth_headers):
    resp = client.get("/pullrequests", headers=auth_headers)
    assert resp.status_code == 422

    resp = client.get("/pullrequests", headers=auth_headers, params={"owner": "octocat", "repo": "Hello-World"})
    assert resp.status_code == 200
    assert resp.json()["pull_requests"][0]["head"] == "feature/fix"


def test_get_pull_request(client, auth_headers):
    resp = client.get("/pullrequests/octocat/Hello-World/12", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["number"] == 12


def test_get_pull_request_files(client, auth_headers):
    resp = client.get("/pullrequests/octocat/Hello-World/12/files", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()[0]["filename"] == "app/main.py"


def test_get_pull_request_diff(client, auth_headers):
    resp = client.get("/pullrequests/octocat/Hello-World/12/diff", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    assert resp.text.startswith("diff --git")


def test_repositories_maps_not_found(client, auth_headers):
    FakeGitHubClient.errors["list_repositories"] = GitHubAPIError(404, "Not Found", "not_found")
    resp = client.get("/repositories", headers=auth_headers)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Not Found"


def test_repositories_maps_rate_limit(client, auth_headers):
    FakeGitHubClient.errors["list_repositories"] = GitHubAPIError(403, "API rate limit exceeded", "rate_limit")
    resp = client.get("/repositories", headers=auth_headers)
    assert resp.status_code == 429


def test_pullrequests_maps_auth_error(client, auth_headers):
    FakeGitHubClient.errors["list_pull_requests"] = GitHubAPIError(401, "Bad credentials", "authentication")
    resp = client.get("/pullrequests", headers=auth_headers, params={"owner": "octocat", "repo": "Hello-World"})
    assert resp.status_code == 401


def test_endpoints_still_require_auth(client):
    assert client.get("/repositories").status_code == 401
    assert client.get("/pullrequests?owner=a&repo=b").status_code == 401
    assert client.get("/pullrequests/a/b/1").status_code == 401