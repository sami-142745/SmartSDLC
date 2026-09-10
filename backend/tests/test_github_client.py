import httpx
import pytest

from app.services.github_client import GITHUB_DIFF_ACCEPT, GitHubAPIError, GitHubClient

REPO_RAW = {
    "id": 1,
    "name": "Hello-World",
    "full_name": "octocat/Hello-World",
    "private": False,
    "html_url": "https://github.com/octocat/Hello-World",
    "default_branch": "main",
    "owner": {"login": "octocat"},
}

PR_RAW = {
    "number": 12,
    "title": "Fix bug",
    "state": "open",
    "user": {"login": "octocat"},
    "html_url": "https://github.com/octocat/Hello-World/pull/12",
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-02T00:00:00Z",
    "head": {"ref": "feature/fix"},
    "base": {"ref": "main"},
}

FILE_RAW = {
    "filename": "app/main.py",
    "status": "modified",
    "additions": 3,
    "deletions": 1,
    "changes": 4,
    "patch": "@@ -1 +1,3 @@",
}


def _make_client(monkeypatch, handler, token="gho_test"):
    monkeypatch.setattr(
        "app.services.github_client._new_http_client",
        lambda **kw: httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=kw.get("timeout")),
    )
    return GitHubClient(token)


@pytest.mark.asyncio
async def test_get_user(monkeypatch):
    def handler(request):
        assert request.url == "https://api.github.com/user"
        return httpx.Response(200, json={"id": 42, "login": "octocat"})

    client = _make_client(monkeypatch, handler)
    assert (await client.get_user())["login"] == "octocat"


@pytest.mark.asyncio
async def test_list_repositories_parses_and_forwards_pagination(monkeypatch):
    def handler(request):
        assert request.url.path == "/user/repos"
        assert request.url.params["page"] == "2"
        assert request.url.params["per_page"] == "50"
        expected = {"Link": '<https://api.github.com/user/repos?page=3&per_page=50>; rel="next"'}
        return httpx.Response(200, headers=expected, json=[REPO_RAW, {**REPO_RAW, "id": 2, "name": "Repo2"}])

    client = _make_client(monkeypatch, handler)
    result = await client.list_repositories(page=2, per_page=50)
    assert result["page"] == 2
    assert result["per_page"] == 50
    assert result["has_more"] is True
    assert result["repositories"][0]["full_name"] == "octocat/Hello-World"
    assert result["repositories"][0]["owner"] == "octocat"


@pytest.mark.asyncio
async def test_list_repositories_has_more_false_without_link(monkeypatch):
    def handler(request):
        return httpx.Response(200, json=[REPO_RAW])

    client = _make_client(monkeypatch, handler)
    result = await client.list_repositories()
    assert result["has_more"] is False


@pytest.mark.asyncio
async def test_get_repository(monkeypatch):
    def handler(request):
        assert request.url.path == "/repos/octocat/Hello-World"
        return httpx.Response(200, json=REPO_RAW)

    client = _make_client(monkeypatch, handler)
    repo = await client.get_repository("octocat", "Hello-World")
    assert repo["name"] == "Hello-World"
    assert repo["default_branch"] == "main"


@pytest.mark.asyncio
async def test_get_repository_404(monkeypatch):
    def handler(request):
        return httpx.Response(404, json={"message": "Not Found"})

    client = _make_client(monkeypatch, handler)
    with pytest.raises(GitHubAPIError) as exc:
        await client.get_repository("octocat", "nope")
    assert exc.value.category == "not_found"
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_list_pull_requests_parses_fields(monkeypatch):
    def handler(request):
        assert request.url.path == "/repos/octocat/Hello-World/pulls"
        assert request.url.params["state"] == "open"
        return httpx.Response(200, json=[PR_RAW])

    client = _make_client(monkeypatch, handler)
    result = await client.list_pull_requests("octocat", "Hello-World")
    pr = result["pull_requests"][0]
    assert pr["number"] == 12
    assert pr["user"] == "octocat"
    assert pr["head"] == "feature/fix"
    assert pr["base"] == "main"
    assert pr["html_url"].endswith("/pull/12")


@pytest.mark.asyncio
async def test_get_pull_request_files(monkeypatch):
    def handler(request):
        assert request.url.path == "/repos/octocat/Hello-World/pulls/12/files"
        return httpx.Response(200, json=[FILE_RAW])

    client = _make_client(monkeypatch, handler)
    files = await client.get_pull_request_files("octocat", "Hello-World", 12)
    assert files[0]["filename"] == "app/main.py"
    assert files[0]["deletions"] == 1
    assert files[0]["patch"].startswith("@@")


@pytest.mark.asyncio
async def test_get_pull_request_diff_requests_diff_accept(monkeypatch):
    def handler(request):
        assert request.headers["accept"] == GITHUB_DIFF_ACCEPT
        return httpx.Response(200, text="diff --git a/app/main.py b/app/main.py\n")

    client = _make_client(monkeypatch, handler)
    diff = await client.get_pull_request_diff("octocat", "Hello-World", 12)
    assert diff.startswith("diff --git")


@pytest.mark.asyncio
async def test_unauthorized_error(monkeypatch):
    def handler(request):
        return httpx.Response(401, json={"message": "Bad credentials"})

    client = _make_client(monkeypatch, handler)
    with pytest.raises(GitHubAPIError) as exc:
        await client.get_user()
    assert exc.value.category == "authentication"


@pytest.mark.asyncio
async def test_rate_limit_via_429(monkeypatch):
    def handler(request):
        return httpx.Response(429, json={"message": "API rate limit exceeded"})

    client = _make_client(monkeypatch, handler)
    with pytest.raises(GitHubAPIError) as exc:
        await client.get_user()
    assert exc.value.category == "rate_limit"


@pytest.mark.asyncio
async def test_rate_limit_via_403_header(monkeypatch):
    def handler(request):
        headers = {"X-RateLimit-Remaining": "0"}
        return httpx.Response(403, headers=headers, json={"message": "API rate limit exceeded"})

    client = _make_client(monkeypatch, handler)
    with pytest.raises(GitHubAPIError) as exc:
        await client.get_user()
    assert exc.value.category == "rate_limit"


@pytest.mark.asyncio
async def test_server_error(monkeypatch):
    def handler(request):
        return httpx.Response(500, json={"message": "Server Error"})

    client = _make_client(monkeypatch, handler)
    with pytest.raises(GitHubAPIError) as exc:
        await client.get_user()
    assert exc.value.category == "server"


@pytest.mark.asyncio
async def test_network_error_is_mapped(monkeypatch):
    def handler(request):
        raise httpx.ConnectError("boom")

    client = _make_client(monkeypatch, handler)
    with pytest.raises(GitHubAPIError) as exc:
        await client.get_user()
    assert exc.value.category == "network"
    assert "token" not in exc.value.message.lower()