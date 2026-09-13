import json

import pytest
from bson import ObjectId

from app.services.document_repository import (
    get_document,
    is_valid_document_id,
    list_documents,
    save_document,
)
from app.services.documentation_service import (
    DocumentGenerationError,
    _fetch_file_contents,
    _select_source_paths,
    to_documentation_response,
)
from app.services.gemini_service import (
    GeminiDocumentation,
    GeminiUnavailable,
    build_documentation_prompt,
    generate_code_documentation,
)
from app.services.github_client import GitHubAPIError


def stored_document(**overrides):
    doc = {
        "_id": "666666666666666666666666",
        "owner": "octocat",
        "repository": "Hello-World",
        "pull_request_number": 12,
        "pull_request_title": "Fix bug",
        "commit_sha": "abc123",
        "default_branch": "main",
        "title": "Hello-World docs",
        "summary": "A test repository.",
        "architecture": "Client-server.",
        "modules": ["module-a"],
        "api": ["GET /health (health check)"],
        "changes": ["Added authentication"],
        "configuration": ["PORT (server port)"],
        "security": ["Secrets are redacted before analysis"],
        "setup": ["pip install -r requirements.txt"],
        "model": "gemini-2.5-flash",
        "status": "complete",
        "error": None,
        "duration_ms": 300,
        "created_at": None,
    }
    doc.update(overrides)
    return doc


DOC_RESPONSE = to_documentation_response(stored_document())


class _InsertResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id


class _Cursor:
    def __init__(self, docs):
        self._docs = list(docs or [])
        self._idx = 0

    def sort(self, key, direction=-1):
        self._docs = sorted(self._docs, key=lambda d: d.get(key), reverse=(direction == -1))
        return self

    def skip(self, n):
        self._docs = self._docs[int(n):]
        return self

    def limit(self, n):
        self._docs = self._docs[: int(n)]
        return self

    def __aiter__(self):
        self._idx = 0
        return self

    async def __anext__(self):
        if self._idx >= len(self._docs):
            raise StopAsyncIteration
        doc = self._docs[self._idx]
        self._idx += 1
        return doc


def _match(doc, query):
    return all(doc.get(key) == value for key, value in query.items())


class _Collection:
    def __init__(self):
        self.docs = []

    async def insert_one(self, document):
        doc = dict(document)
        doc.setdefault("_id", ObjectId(f"{len(self.docs) + 1:024d}"))
        self.docs.append(doc)
        return _InsertResult(doc["_id"])

    def find(self, query=None):
        return _Cursor([d for d in self.docs if _match(d, query or {})])

    async def find_one(self, query=None):
        for d in self.docs:
            if _match(d, query or {}):
                return dict(d)
        return None

    async def count_documents(self, query=None):
        return sum(1 for d in self.docs if _match(d, query or {}))

    async def create_index(self, *args, **kwargs):
        return None


class _Db:
    def __init__(self):
        self.collections = {"documents": _Collection()}

    def __getitem__(self, name):
        return self.collections[name]


# --------------------------------------------------------------------------- #
# Authentication guards
# --------------------------------------------------------------------------- #


def test_generate_requires_auth(client):
    resp = client.post("/documents/generate", json={"owner": "octocat", "repository": "Hello-World"})
    assert resp.status_code == 401


def test_list_documents_requires_auth(client):
    resp = client.get("/documents")
    assert resp.status_code == 401


def test_repository_documentation_requires_auth(client):
    resp = client.get("/documents/repository/octocat/Hello-World")
    assert resp.status_code == 401


def test_get_document_requires_auth(client):
    resp = client.get("/documents/666666666666666666666666")
    assert resp.status_code == 401


# --------------------------------------------------------------------------- #
# POST /documents/generate
# --------------------------------------------------------------------------- #


def test_generate_returns_complete(client, auth_headers, monkeypatch):
    async def _fake_generate(gh, owner, repo, pull_request=None, user_id=None):
        return DOC_RESPONSE

    monkeypatch.setattr("app.routers.documents.documentation_service.generate_documentation", _fake_generate)
    resp = client.post(
        "/documents/generate",
        json={"owner": "octocat", "repository": "Hello-World", "pull_request": 12},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Hello-World docs"
    assert data["source"]["repository"] == "octocat/Hello-World"
    assert data["source"]["commit"] == "abc123"
    assert data["status"] == "complete"


def test_generate_maps_github_not_found(client, auth_headers, monkeypatch):
    async def _error(gh, owner, repo, pull_request=None, user_id=None):
        raise GitHubAPIError(404, "Not Found", "not_found")

    monkeypatch.setattr("app.routers.documents.documentation_service.generate_documentation", _error)
    resp = client.post(
        "/documents/generate",
        json={"owner": "octocat", "repository": "missing"},
        headers=auth_headers,
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Not Found"


def test_generate_maps_gemini_failure(client, auth_headers, monkeypatch):
    async def _error(gh, owner, repo, pull_request=None, user_id=None):
        raise DocumentGenerationError("Documentation generation failed: AI engine unavailable")

    monkeypatch.setattr("app.routers.documents.documentation_service.generate_documentation", _error)
    resp = client.post(
        "/documents/generate",
        json={"owner": "octocat", "repository": "Hello-World"},
        headers=auth_headers,
    )
    assert resp.status_code == 502


# --------------------------------------------------------------------------- #
# GET /documents/repository/{owner}/{repository}
# --------------------------------------------------------------------------- #


def test_repository_documentation_returns_doc(client, auth_headers, monkeypatch):
    async def _latest(user_id, owner, repository, pull_request_number=None):
        return stored_document()

    monkeypatch.setattr("app.services.document_repository.get_latest_document", _latest)
    resp = client.get(
        "/documents/repository/octocat/Hello-World?pull_request=12",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["source"]["pull_request"] == "#12"


def test_repository_documentation_empty_returns_404(client, auth_headers, monkeypatch):
    async def _latest(user_id, owner, repository, pull_request_number=None):
        return None

    monkeypatch.setattr("app.services.document_repository.get_latest_document", _latest)
    resp = client.get("/documents/repository/octocat/Hello-World", headers=auth_headers)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "No documentation found for this repository"


# --------------------------------------------------------------------------- #
# GET /documents
# --------------------------------------------------------------------------- #


def test_list_documents_returns_items(client, auth_headers, monkeypatch):
    async def _list(user_id, page=1, per_page=20, repository=None, owner=None):
        return {"items": [stored_document()], "total": 1, "page": 1, "per_page": 20}

    monkeypatch.setattr("app.services.document_repository.list_documents", _list)
    resp = client.get("/documents", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["total_pages"] == 1
    assert data["items"][0]["id"] == "666666666666666666666666"


def test_list_documents_empty(client, auth_headers, monkeypatch):
    async def _list(user_id, page=1, per_page=20, repository=None, owner=None):
        return {"items": [], "total": 0, "page": 1, "per_page": 20}

    monkeypatch.setattr("app.services.document_repository.list_documents", _list)
    resp = client.get("/documents?repository=Hello-World", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["items"] == []
    assert resp.json()["total_pages"] == 0


# --------------------------------------------------------------------------- #
# GET /documents/{document_id}
# --------------------------------------------------------------------------- #


def test_get_document_returns_doc(client, auth_headers, monkeypatch):
    async def _get(doc_id, user_id):
        return stored_document()

    monkeypatch.setattr("app.services.document_repository.get_document", _get)
    resp = client.get("/documents/666666666666666666666666", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["title"] == "Hello-World docs"


def test_get_document_missing_returns_404(client, auth_headers, monkeypatch):
    async def _get(doc_id, user_id):
        return None

    monkeypatch.setattr("app.services.document_repository.get_document", _get)
    resp = client.get("/documents/ffffffffffffffffffffffff", headers=auth_headers)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Documentation not found"


def test_get_document_invalid_id_returns_404(client, auth_headers, monkeypatch):
    async def _get(doc_id, user_id):
        return None

    monkeypatch.setattr("app.services.document_repository.get_document", _get)
    resp = client.get("/documents/not-a-valid-id", headers=auth_headers)
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# Documentation service
# --------------------------------------------------------------------------- #


class FakeGitHubClient:
    def __init__(self, tree=None):
        self._tree = tree or {
            "tree": [
                {"type": "blob", "path": "README.md"},
                {"type": "blob", "path": "src/app.py"},
                {"type": "tree", "path": "node_modules"},
            ]
        }

    async def get_repository(self, owner, repo):
        return {"description": "A test repo", "default_branch": "main", "name": repo, "owner": owner}

    async def get_pull_request(self, owner, repo, number):
        return {"number": number, "title": "Fix bug", "head_sha": "abc123", "head": {"sha": "abc123"}}

    async def get_repository_tree(self, owner, repo, ref=None):
        return self._tree

    async def get_file_content(self, owner, repo, path, ref=None):
        if "secret" in path:
            return "password = 'supersecretvalue123'"
        return "def main():\n    pass\n"


class FakeGeminiResponse:
    def __init__(self, text):
        self.text = text


def _doc_payload():
    return json.dumps(
        {
            "title": "Hello-World docs",
            "summary": "Summarizes the system.",
            "architecture": "Client-server.",
            "modules": ["module-a", "module-b"],
            "api": ["GET /health"],
            "changes": ["Added auth"],
            "configuration": ["PORT"],
            "security": ["Secrets redacted"],
            "setup": ["pip install"],
        }
    )


def test_service_generates_and_persists(monkeypatch):
    captured = {}

    async def _fake_save(**kwargs):
        captured.update(kwargs)
        return "666666666666666666666666"

    monkeypatch.setattr("app.services.documentation_service.settings.GEMINI_API_KEY", "test-key")
    monkeypatch.setattr("app.services.gemini_service._generate_content_sync", lambda m, p, c: FakeGeminiResponse(_doc_payload()))
    monkeypatch.setattr("app.services.document_repository.save_document", _fake_save)

    from app.services.documentation_service import generate_documentation

    result = asyncio_run(generate_documentation(FakeGitHubClient(), "octocat", "Hello-World", pull_request=12, user_id=7))
    assert result["status"] == "complete"
    assert result["source"]["repository"] == "octocat/Hello-World"
    assert result["source"]["commit"] == "abc123"
    assert result["source"]["branch"] == "main"
    assert captured["user_id"] == 7
    assert captured["pull_request_number"] == 12
    assert captured["commit_sha"] == "abc123"
    assert captured["documentation"]["modules"] == ["module-a", "module-b"]


def test_service_renders_secret_redacted(monkeypatch):
    class RedactedClient(FakeGitHubClient):
        async def get_file_content(self, owner, repo, path, ref=None):
            return "password = 'supersecretvalue123'"

    files = asyncio_run(_fetch_file_contents(RedactedClient(), "o", "r", ["src/app.py"], "main"))
    assert len(files) == 1
    assert "supersecretvalue123" not in files[0]["code"]
    assert "[REDACTED]" in files[0]["code"]


def test_fetch_skips_missing_files_and_limits_chars(monkeypatch):
    requests = []

    class FlakyClient(FakeGitHubClient):
        async def get_file_content(self, owner, repo, path, ref=None):
            requests.append(path)
            if path == "missing.py":
                raise GitHubAPIError(404, "boom", "not_found")
            return "x" * 10000

    files = asyncio_run(_fetch_file_contents(FlakyClient(), "o", "r", ["missing.py", "big.py"], "main"))
    assert requests == ["missing.py", "big.py"]
    assert len(files) == 1
    assert len(files[0]["code"]) <= 6000


def test_select_source_paths_filters_and_prioritizes():
    tree = {
        "tree": [
            {"type": "blob", "path": "package.json"},
            {"type": "blob", "path": "src/app.ts"},
            {"type": "blob", "path": "node_modules/dep/index.js"},
            {"type": "blob", "path": "package-lock.json"},
            {"type": "blob", "path": "dist/bundle.min.js"},
            {"type": "tree", "path": "vendor/"},
        ]
    }
    paths = _select_source_paths(tree, 16)
    assert paths == ["package.json", "src/app.ts"]


def test_service_no_analyzable_files(monkeypatch):
    empty_tree = {"tree": [{"type": "tree", "path": "node_modules"}]}
    monkeypatch.setattr("app.services.documentation_service.settings.GEMINI_API_KEY", "test-key")

    from app.services.documentation_service import generate_documentation

    with pytest.raises(DocumentGenerationError):
        asyncio_run(generate_documentation(FakeGitHubClient(empty_tree), "o", "r", user_id=1))


def test_service_gemini_failure_raises_documentation_error(monkeypatch):
    async def _boom(context):
        raise GeminiUnavailable("no key")

    monkeypatch.setattr("app.services.documentation_service.generate_code_documentation", _boom)
    monkeypatch.setattr("app.services.documentation_service.settings.GEMINI_API_KEY", "test-key")

    from app.services.documentation_service import generate_documentation

    with pytest.raises(DocumentGenerationError):
        asyncio_run(generate_documentation(FakeGitHubClient(), "o", "r", user_id=1))


def test_service_missing_repository_raises_github_error(monkeypatch):
    class MissingClient(FakeGitHubClient):
        async def get_repository(self, owner, repo):
            raise GitHubAPIError(404, "Not Found", "not_found")

    monkeypatch.setattr("app.services.documentation_service.settings.GEMINI_API_KEY", "test-key")

    from app.services.documentation_service import generate_documentation

    with pytest.raises(GitHubAPIError):
        asyncio_run(generate_documentation(MissingClient(), "o", "missing", user_id=1))


# --------------------------------------------------------------------------- #
# Document repository (persistence + ownership isolation)
# --------------------------------------------------------------------------- #


def test_document_repository_saves_and_retrieves_by_owner(monkeypatch):
    db = _Db()
    monkeypatch.setattr("app.services.document_repository.get_db", lambda: db)
    doc_id = asyncio_run(
        save_document(
            user_id=7,
            owner="octocat",
            repository="Hello-World",
            pull_request_number=12,
            pull_request_title="Fix bug",
            commit_sha="abc123",
            default_branch="main",
            documentation={"title": "Docs", "summary": "S", "architecture": "A", "modules": [], "api": [],
                           "changes": [], "configuration": [], "security": [], "setup": []},
            model="gemini-2.5-flash",
            status="complete",
            duration_ms=100,
        )
    )
    found = asyncio_run(get_document(doc_id, 7))
    assert found is not None
    assert found["title"] == "Docs"
    assert found["pull_request_number"] == 12


def test_document_repository_ownership_isolation(monkeypatch):
    db = _Db()
    monkeypatch.setattr("app.services.document_repository.get_db", lambda: db)
    asyncio_run(
        save_document(
            user_id=7,
            owner="octocat",
            repository="Hello-World",
            pull_request_number=None,
            pull_request_title=None,
            commit_sha=None,
            default_branch=None,
            documentation={"title": "Private docs", "summary": "", "architecture": "",
                           "modules": [], "api": [], "changes": [], "configuration": [], "security": [], "setup": []},
            model="gemini-2.5-flash",
            status="complete",
            duration_ms=1,
        )
    )
    assert asyncio_run(get_document("000000000000000000000001", 999)) is None
    assert asyncio_run(get_document("000000000000000000000001", 7)) is not None


def test_document_repository_invalid_id_returns_none(monkeypatch):
    db = _Db()
    monkeypatch.setattr("app.services.document_repository.get_db", lambda: db)
    assert asyncio_run(get_document("not-a-valid-id", 7)) is None
    assert asyncio_run(get_document("", 7)) is None


def test_document_repository_lists_user_docs(monkeypatch):
    db = _Db()
    monkeypatch.setattr("app.services.document_repository.get_db", lambda: db)
    for user in (7, 7, 8):
        asyncio_run(
            save_document(
                user_id=user,
                owner="octocat",
                repository="Hello-World",
                pull_request_number=None,
                pull_request_title=None,
                commit_sha=None,
                default_branch=None,
                documentation={"title": "Docs", "summary": "", "architecture": "",
                               "modules": [], "api": [], "changes": [], "configuration": [], "security": [], "setup": []},
                model="gemini-2.5-flash",
                status="complete",
                duration_ms=1,
            )
        )
    result = asyncio_run(list_documents(7, page=1, per_page=20))
    assert result["total"] == 2
    assert len(result["items"]) == 2
    filtered = asyncio_run(list_documents(7, repository="Hello-World"))
    assert filtered["total"] == 2
    filtered = asyncio_run(list_documents(8))
    assert filtered["total"] == 1


def test_is_valid_document_id():
    assert is_valid_document_id("666666666666666666666666")
    assert is_valid_document_id("abcdef0123456789abcdef01")
    assert not is_valid_document_id("short")
    assert not is_valid_document_id("not a valid value at all")
    assert not is_valid_document_id(None)


# --------------------------------------------------------------------------- #
# Gemini documentation generation
# --------------------------------------------------------------------------- #

DOC_CTX = {
    "repository": "octocat/Hello-World",
    "description": "A test repo",
    "default_branch": "main",
    "pull_request_number": 12,
    "pull_request_title": "Fix bug",
    "files": [{"path": "src/app.py", "code": "def main():\n    pass\n"}],
}


def test_build_documentation_prompt_includes_repository_and_files():
    prompt = build_documentation_prompt(DOC_CTX)
    assert "octocat/Hello-World" in prompt
    assert "SECURITY RULES" in prompt
    assert "src/app.py" in prompt
    assert "def main()" in prompt


@pytest.mark.asyncio
async def test_generate_code_documentation_missing_api_key(monkeypatch):
    monkeypatch.setattr("app.services.gemini_service.settings.GEMINI_API_KEY", "change_me")
    with pytest.raises(GeminiUnavailable):
        await generate_code_documentation(DOC_CTX)


@pytest.mark.asyncio
async def test_generate_code_documentation_returns_normalized(monkeypatch):
    monkeypatch.setattr("app.services.gemini_service.settings.GEMINI_API_KEY", "test-key")
    monkeypatch.setattr("app.services.gemini_service._generate_content_sync", lambda m, p, c: FakeGeminiResponse(_doc_payload()))
    doc = await generate_code_documentation(DOC_CTX)
    assert isinstance(doc, GeminiDocumentation)
    assert doc.title == "Hello-World docs"
    assert doc.modules == ["module-a", "module-b"]
    assert doc.api == ["GET /health"]


@pytest.mark.asyncio
async def test_generate_code_documentation_non_object_raises(monkeypatch):
    monkeypatch.setattr("app.services.gemini_service.settings.GEMINI_API_KEY", "test-key")
    monkeypatch.setattr("app.services.gemini_service._generate_content_sync", lambda m, p, c: FakeGeminiResponse("[1,2,3]"))
    with pytest.raises(GeminiUnavailable):
        await generate_code_documentation(DOC_CTX)


@pytest.mark.asyncio
async def test_generate_code_documentation_returns_empty_string_raises(monkeypatch):
    monkeypatch.setattr("app.services.gemini_service.settings.GEMINI_API_KEY", "test-key")
    monkeypatch.setattr("app.services.gemini_service._generate_content_sync", lambda m, p, c: FakeGeminiResponse(""))
    with pytest.raises(GeminiUnavailable):
        await generate_code_documentation(DOC_CTX)


@pytest.mark.asyncio
async def test_generate_code_documentation_invalid_json_raises(monkeypatch):
    monkeypatch.setattr("app.services.gemini_service.settings.GEMINI_API_KEY", "test-key")
    monkeypatch.setattr("app.services.gemini_service._generate_content_sync", lambda m, p, c: FakeGeminiResponse("NOT JSON"))
    with pytest.raises(GeminiUnavailable):
        await generate_code_documentation(DOC_CTX)


def asyncio_run(coro):
    import asyncio

    return asyncio.run(coro)