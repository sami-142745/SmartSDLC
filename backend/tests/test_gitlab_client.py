import httpx
import pytest

from app.services.gitlab_client import GitLabClient
from app.services.github_client import GitHubAPIError

REPO_RAW = {
    "id": 101,
    "name": "gl-lab",
    "path_with_namespace": "acme/gl-lab",
    "visibility": "private",
    "web_url": "https://gitlab.com/acme/gl-lab",
    "default_branch": "main",
    "description": "GitLab sample",
    "namespace": {"full_path": "acme"},
}

MR_RAW = {
    "iid": 23,
    "title": "Wire up auth",
    "state": "opened",
    "author": {"username": "gluser"},
    "web_url": "https://gitlab.com/acme/gl-lab/-/merge_requests/23",
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-02T00:00:00Z",
    "source_branch": "feature/auth",
    "sha": "abc123",
    "target_branch": "main",
}

CHANGE_RAW = {
    "old_path": "auth.py",
    "new_path": "auth.py",
    "diff": "@@ -1 +1,4 @@\n-import os\n+import hashlib\n+def tokenize(value):\n+    return hashlib.sha256(value.encode()).hexdigest()",
    "new_file": False,
    "deleted_file": False,
    "renamed_file": False,
}


def _make_client(monkeypatch, handler, token="glpat_test"):
    monkeypatch.setattr(
        "app.services.gitlab_client._new_http_client",
        lambda **kw: httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=kw.get("timeout")),
    )
    return GitLabClient(token)


def _params_of(request):
    return {k: v for k, v in request.url.params.items()}


def _project_tail(request):
    marker = "/projects/"
    return request.url.path[request.url.path.index(marker):]


@pytest.mark.asyncio
async def test_list_repositories_uses_membership_and_pagination(monkeypatch):
    def handler(request):
        assert request.url.path == "/api/v4/projects"
        assert request.headers["PRIVATE-TOKEN"] == "glpat_test"
        params = _params_of(request)
        assert params["membership"] == "true"
        assert params["page"] == "2"
        headers = {"X-Next-Page": "3"}
        return httpx.Response(200, headers=headers, json=[REPO_RAW])

    client = _make_client(monkeypatch, handler)
    result = await client.list_repositories(page=2, per_page=50)
    assert result["page"] == 2
    assert result["has_more"] is True
    repo = result["repositories"][0]
    assert repo["full_name"] == "acme/gl-lab"
    assert repo["owner"] == "acme"
    assert repo["private"] is True
    assert repo["html_url"] == "https://gitlab.com/acme/gl-lab"


@pytest.mark.asyncio
async def test_list_repositories_has_more_false_without_next_header(monkeypatch):
    def handler(request):
        return httpx.Response(200, json=[])

    client = _make_client(monkeypatch, handler)
    result = await client.list_repositories()
    assert result["repositories"] == []
    assert result["has_more"] is False


@pytest.mark.asyncio
async def test_get_repository_encodes_project_path(monkeypatch):
    def handler(request):
        assert "%2F" in request.url.raw_path.decode()
        assert request.url.path == "/api/v4/projects/acme/gl-lab"
        return httpx.Response(200, json=REPO_RAW)

    client = _make_client(monkeypatch, handler)
    repo = await client.get_repository("acme", "gl-lab")
    assert repo["name"] == "gl-lab"
    assert repo["default_branch"] == "main"


@pytest.mark.asyncio
async def test_list_merge_requests_maps_open_state(monkeypatch):
    def handler(request):
        assert _project_tail(request) == "/projects/acme/gl-lab/merge_requests"
        assert "%2F" in request.url.raw_path.decode()
        assert _params_of(request)["state"] == "opened"
        return httpx.Response(200, json=[MR_RAW])

    client = _make_client(monkeypatch, handler)
    result = await client.list_pull_requests("acme", "gl-lab", state="open")
    mr = result["pull_requests"][0]
    assert mr["number"] == 23
    assert mr["user"] == "gluser"
    assert mr["head"] == "feature/auth"
    assert mr["head_sha"] == "abc123"
    assert mr["base"] == "main"


@pytest.mark.asyncio
async def test_get_merge_request(monkeypatch):
    def handler(request):
        assert _project_tail(request) == "/projects/acme/gl-lab/merge_requests/23"
        return httpx.Response(200, json=MR_RAW)

    client = _make_client(monkeypatch, handler)
    mr = await client.get_pull_request("acme", "gl-lab", 23)
    assert mr["number"] == 23
    assert mr["title"] == "Wire up auth"


@pytest.mark.asyncio
async def test_get_merge_request_changes_maps_files_and_counts(monkeypatch):
    def handler(request):
        assert _project_tail(request) == "/projects/acme/gl-lab/merge_requests/23/changes"
        return httpx.Response(200, json={"changes": [CHANGE_RAW]})

    client = _make_client(monkeypatch, handler)
    files = await client.get_pull_request_files("acme", "gl-lab", 23)
    assert files[0]["filename"] == "auth.py"
    assert files[0]["status"] == "modified"
    assert files[0]["additions"] == 3
    assert files[0]["deletions"] == 1
    assert files[0]["changes"] == 4
    assert files[0]["patch"].startswith("@@")


@pytest.mark.asyncio
async def test_get_merge_request_files_new_and_deleted_statuses(monkeypatch):
    def handler(request):
        return httpx.Response(
            200,
            json={
                "changes": [
                    {"new_path": "new.py", "diff": "+1\n+2\n", "new_file": True},
                    {"old_path": "old.py", "new_path": "old.py", "diff": "-apple\n", "deleted_file": True},
                ]
            },
        )

    client = _make_client(monkeypatch, handler)
    files = await client.get_pull_request_files("acme", "gl-lab", 23)
    assert files[0]["status"] == "added"
    assert files[0]["filename"] == "new.py"
    assert files[1]["status"] == "removed"
    assert files[1]["additions"] == 0
    assert files[1]["deletions"] == 1


@pytest.mark.asyncio
async def test_get_merge_request_diff_requests_text_payload(monkeypatch):
    def handler(request):
        assert request.url.path.endswith("/merge_requests/23.diff")
        assert request.headers["Accept"] == "text/plain"
        return httpx.Response(200, text="diff --git a/auth.py b/auth.py\n+import hashlib\n")

    client = _make_client(monkeypatch, handler)
    diff = await client.get_pull_request_diff("acme", "gl-lab", 23)
    assert diff.startswith("diff --git")


@pytest.mark.asyncio
async def test_get_file_content_uses_raw_endpoint(monkeypatch):
    def handler(request):
        assert "acme%2Fgl-lab" in request.url.raw_path.decode()
        assert request.url.path.endswith("/repository/files/README.md/raw")
        assert _params_of(request).get("ref") == "main"
        return httpx.Response(200, text="# gl-lab\n")

    client = _make_client(monkeypatch, handler)
    content = await client.get_file_content("acme", "gl-lab", "README.md", ref="main")
    assert content.startswith("# gl-lab")


@pytest.mark.asyncio
async def test_get_repository_tree_reshapes_entries(monkeypatch):
    def handler(request):
        assert _project_tail(request) == "/projects/acme/gl-lab/repository/tree"
        assert _params_of(request)["recursive"] == "true"
        return httpx.Response(
            200,
            json=[
                {"id": "sha1", "name": "src", "type": "tree", "path": "src", "mode": "040000"},
                {"id": "sha2", "name": "app.py", "type": "blob", "path": "src/app.py", "mode": "100644"},
                {"id": "sha3", "name": "sub", "type": "commit", "path": "src/sub", "mode": "160000"},
            ],
        )

    client = _make_client(monkeypatch, handler)
    tree = await client.get_repository_tree("acme", "gl-lab")
    paths = [entry["path"] for entry in tree["tree"]]
    assert "src" in paths
    assert "src/app.py" in paths
    assert "src/sub" not in paths


@pytest.mark.asyncio
async def test_errors_map_to_scm_api_error(monkeypatch):
    def handler(request):
        return httpx.Response(404, json={"message": "404 Project Not Found"})

    client = _make_client(monkeypatch, handler)
    with pytest.raises(GitHubAPIError) as exc:
        await client.get_repository("acme", "nope")
    assert exc.value.status_code == 404
    assert exc.value.category == "not_found"


@pytest.mark.asyncio
async def test_network_error_is_mapped(monkeypatch):
    def handler(request):
        raise httpx.ConnectError("boom")

    client = _make_client(monkeypatch, handler)
    with pytest.raises(GitHubAPIError) as exc:
        await client.get_user()
    assert exc.value.category == "network"