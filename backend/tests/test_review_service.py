import json
import pytest

from app.services.github_client import GitHubAPIError
from app.services.gemini_service import GeminiUnavailable
from app.services.review_repository import save_review
from app.services.review_service import run_review, run_review_for_webhook


class FakeGitHubClient:
    def __init__(self, token=None):
        self.token = token

    async def get_pull_request(self, owner, repo, number):
        return {"number": 12, "title": "Fix bug", "head_sha": "abc123", "head": {"sha": "abc123"}}

    async def get_pull_request_files(self, owner, repo, number):
        return [
            {
                "filename": "app/main.py",
                "status": "modified",
                "additions": 3,
                "deletions": 1,
                "changes": 4,
                "patch": "@@ -1 +1,3 @@\n+password = 'hunter2'\n old_code\n+new_line",
            }
        ]


class FakeGitHubClientEmptyFiles:
    async def get_pull_request(self, owner, repo, number):
        return {"number": 1, "title": "Empty PR", "head_sha": "def456", "head": {"sha": "def456"}}

    async def get_pull_request_files(self, owner, repo, number):
        return []


class FakeGitHubClientError:
    async def get_pull_request(self, owner, repo, number):
        raise GitHubAPIError(404, "Not Found", "not_found")


class FakeCursor:
    def __init__(self, docs=None):
        self._docs = list(docs or [])
        self._idx = 0

    def sort(self, *a, **kw):
        return self

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._idx >= len(self._docs):
            raise StopAsyncIteration
        doc = self._docs[self._idx]
        self._idx += 1
        return doc


class FakeCollection:
    def __init__(self):
        self.docs = []
        self._find_result = []

    async def insert_one(self, doc):
        self.docs.append(doc)
        class R:
            inserted_id = "666666666666666666666666"
        return R()

    async def insert_many(self, docs):
        self.docs.extend(docs)

    def find(self, query=None, **kw):
        return FakeCursor(self._find_result)

    async def find_one(self, query=None):
        if self._find_result:
            return self._find_result[0]
        return None

    async def create_index(self, *a, **kw):
        return None


class FakeDb:
    def __init__(self):
        self.reviews = FakeCollection()
        self.review_findings = FakeCollection()

    def __getitem__(self, name):
        return getattr(self, name)


@pytest.fixture
def fake_db(monkeypatch):
    db = FakeDb()
    monkeypatch.setattr("app.services.review_repository.get_db", lambda: db)
    return db


async def _gemini_empty(context):
    return []


@pytest.mark.asyncio
async def test_run_review_returns_complete_status(monkeypatch, fake_db):
    monkeypatch.setattr("app.services.review_service.review_code", _gemini_empty)
    result = await run_review(FakeGitHubClient(), "octocat", "Hello-World", 12)
    assert result["status"] == "complete"
    assert result["pull_request_number"] == 12
    assert result["repository"] == "Hello-World"
    assert isinstance(result["findings"], list)


@pytest.mark.asyncio
async def test_run_review_heuristic_finding_persists(monkeypatch, fake_db):
    async def _gemini_unavailable(context):
        raise GeminiUnavailable("no key")

    monkeypatch.setattr("app.services.review_service.review_code", _gemini_unavailable)
    result = await run_review(FakeGitHubClient(), "octocat", "Hello-World", 12)
    assert result["status"] == "gemini_unavailable"
    assert any("credential" in f["title"].lower() or "secret" in f["title"].lower() for f in result["findings"])


@pytest.mark.asyncio
async def test_run_review_handles_github_api_error():
    with pytest.raises(GitHubAPIError):
        await run_review(FakeGitHubClientError(), "octocat", "Hello-World", 12)


@pytest.mark.asyncio
async def test_run_review_gemini_timeout_yields_gemini_unavailable_status(monkeypatch, fake_db):
    async def _gemini_timeout(context):
        raise GeminiUnavailable("timeout")

    monkeypatch.setattr("app.services.review_service.review_code", _gemini_timeout)
    result = await run_review(FakeGitHubClient(), "octocat", "Hello-World", 12)
    assert result["status"] == "gemini_unavailable"
    assert isinstance(result["findings"], list)


@pytest.mark.asyncio
async def test_run_review_empty_files_skips_gemini(monkeypatch, fake_db):
    monkeypatch.setattr("app.services.review_service.review_code", _gemini_empty)
    result = await run_review(FakeGitHubClientEmptyFiles(), "octocat", "Hello-World", 1)
    assert result["status"] == "complete"
    assert result["findings"] == []


@pytest.mark.asyncio
async def test_run_review_for_webhook_skips_without_sender():
    await run_review_for_webhook("octocat", "Hello-World", 12, None)


@pytest.mark.asyncio
async def test_run_review_for_webhook_skips_without_user(monkeypatch):
    async def _noop(*a, **kw):
        return None

    monkeypatch.setattr("app.services.review_service.get_user_by_login", _noop)
    await run_review_for_webhook("octocat", "Hello-World", 12, "unknown_user")


@pytest.mark.asyncio
async def test_run_review_for_webhook_never_raises(monkeypatch):
    async def _boom(*a, **kw):
        raise RuntimeError("fatal")

    monkeypatch.setattr("app.services.review_service.get_user_by_login", _boom)
    await run_review_for_webhook("octocat", "Hello-World", 12, "octocat")


@pytest.mark.asyncio
async def test_run_review_for_webhook_skips_without_token(monkeypatch):
    async def _no_token(login):
        return {"github_id": 1, "login": login}

    monkeypatch.setattr("app.services.review_service.get_user_by_login", _no_token)
    await run_review_for_webhook("octocat", "Hello-World", 12, "octocat")


@pytest.mark.asyncio
async def test_save_review_inserts_document(monkeypatch):
    fake_db = FakeDb()
    monkeypatch.setattr("app.services.review_repository.get_db", lambda: fake_db)
    await save_review(
        status="complete",
        owner="octocat",
        repository="Hello-World",
        pull_request_number=12,
        pull_request_title="Fix bug",
        commit_sha="abc123",
        findings=[{"id": "h-1", "title": "test", "source": "heuristic", "severity": "low", "category": "security"}],
        review_score=0.5,
        review_severity="medium",
        duration_ms=100,
    )
    assert len(fake_db.reviews.docs) == 1
    doc = fake_db.reviews.docs[0]
    assert doc["status"] == "complete"
    assert doc["review_score"] == 0.5
    assert doc["heuristic_finding_count"] == 1
    assert doc["gemini_finding_count"] == 0
