import pytest
from bson import ObjectId

from app.services.github_client import GitHubAPIError
from app.services.jwt_service import create_access_token


REVIEW_RESULT = {
    "status": "complete",
    "repository": "Hello-World",
    "owner": "octocat",
    "pull_request_number": 12,
    "pull_request_title": "Fix bug",
    "commit_sha": "abc123",
    "findings": [
        {
            "id": "h-1",
            "title": "Hardcoded credential",
            "description": "Password found",
            "severity": "low",
            "category": "security",
            "file": "config.py",
            "line": 5,
            "code": "password = 'hunter2'",
            "recommendation": "Use env var",
            "confidence": 0.8,
            "source": "heuristic",
        }
    ],
    "heuristic_finding_count": 1,
    "gemini_finding_count": 0,
    "total_finding_count": 1,
    "review_score": 0.6,
    "review_severity": "medium",
    "duration_ms": 120,
    "created_at": None,
    "updated_at": None,
}


class FakeGitHubClient:
    def __init__(self, token=None):
        self.token = token

    async def get_pull_request(self, owner, repo, number):
        return {"number": 12, "title": "Fix bug", "head_sha": "abc123", "head": {"sha": "abc123"}}

    async def get_pull_request_files(self, owner, repo, number):
        return [
            {
                "filename": "config.py",
                "status": "modified",
                "additions": 1,
                "deletions": 0,
                "changes": 1,
                "patch": "@@ -1 +1,2 @@\n old\n+password = 'hunter2'",
            }
        ]


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

    def find(self, query=None, projection=None, **kw):
        docs = self._find_result
        if projection and projection.get("_id") == 0:
            docs = [{k: v for k, v in doc.items() if k != "_id"} for doc in docs]
        return FakeCursor(docs)

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
def auth_headers(monkeypatch):
    async def known_user(github_id):
        return {"github_id": github_id, "login": "octocat", "github_access_token": "gho_test"}

    monkeypatch.setattr("app.services.security.get_user_by_github_id", known_user)
    return {"Authorization": f"Bearer {create_access_token({'sub': '7', 'login': 'octocat'})}"}


def test_post_review_requires_auth(client):
    resp = client.post("/reviews/octocat/Hello-World/12")
    assert resp.status_code == 401


def test_get_reviews_requires_auth(client):
    resp = client.get("/reviews/octocat/Hello-World/12")
    assert resp.status_code == 401


def test_get_findings_requires_auth(client):
    resp = client.get("/reviews/octocat/Hello-World/12/findings")
    assert resp.status_code == 401


def test_post_review_returns_complete(client, auth_headers, monkeypatch):
    async def _fake_run_review(gh, o, r, n, user_id=None, **kwargs):
        return REVIEW_RESULT

    monkeypatch.setattr("app.routers.reviews.run_review", _fake_run_review)
    resp = client.post("/reviews/octocat/Hello-World/12", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "complete"
    assert resp.json()["pull_request_number"] == 12


def test_post_review_maps_github_not_found(client, auth_headers, monkeypatch):
    async def _error_review(gh, o, r, n, user_id=None, **kwargs):
        raise GitHubAPIError(404, "Not Found", "not_found")

    monkeypatch.setattr("app.routers.reviews.run_review", _error_review)
    resp = client.post("/reviews/octocat/Hello-World/12", headers=auth_headers)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Not Found"


def test_post_review_maps_github_rate_limit(client, auth_headers, monkeypatch):
    async def _rate_limit_review(gh, o, r, n, user_id=None, **kwargs):
        raise GitHubAPIError(403, "rate limit", "rate_limit")

    monkeypatch.setattr("app.routers.reviews.run_review", _rate_limit_review)
    resp = client.post("/reviews/octocat/Hello-World/12", headers=auth_headers)
    assert resp.status_code == 429


def test_post_review_maps_github_server_error(client, auth_headers, monkeypatch):
    async def _server_error(gh, o, r, n, user_id=None, **kwargs):
        raise GitHubAPIError(500, "Server error", "server")

    monkeypatch.setattr("app.routers.reviews.run_review", _server_error)
    resp = client.post("/reviews/octocat/Hello-World/12", headers=auth_headers)
    assert resp.status_code == 502


def test_get_reviews_empty(client, auth_headers, monkeypatch):
    db = FakeDb()
    db.reviews._find_result = []
    monkeypatch.setattr("app.services.review_repository.get_db", lambda: db)
    resp = client.get("/reviews/octocat/Hello-World/12", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_reviews_returns_list(client, auth_headers, monkeypatch):
    stored_review = {
        "_id": "666666666666666666666666",
        "status": "complete",
        "repository": "Hello-World",
        "owner": "octocat",
        "pull_request_number": 12,
        "pull_request_title": "Fix bug",
        "commit_sha": "abc123",
        "review_score": 0.6,
        "review_severity": "medium",
        "duration_ms": 120,
        "heuristic_finding_count": 1,
        "gemini_finding_count": 0,
        "created_at": None,
        "updated_at": None,
        "error": None,
    }
    db = FakeDb()
    db.reviews._find_result = [stored_review]
    db.review_findings._find_result = [
        {
            "_id": ObjectId("666666666666666666666666"),
            "id": "h-1",
            "title": "test",
            "description": "A test finding",
            "severity": "low",
            "category": "security",
            "source": "heuristic",
            "review_id": "666666666666666666666666",
        }
    ]
    monkeypatch.setattr("app.services.review_repository.get_db", lambda: db)
    resp = client.get("/reviews/octocat/Hello-World/12", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["status"] == "complete"


def test_get_findings_returns_404_when_no_reviews(client, auth_headers, monkeypatch):
    db = FakeDb()
    db.reviews._find_result = []
    monkeypatch.setattr("app.services.review_repository.get_db", lambda: db)
    resp = client.get("/reviews/octocat/Hello-World/12/findings", headers=auth_headers)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "No reviews found for this pull request"


def test_get_findings_returns_findings(client, auth_headers, monkeypatch):
    stored_review = {"_id": "666666666666666666666666"}
    db = FakeDb()
    db.reviews._find_result = [stored_review]
    db.review_findings._find_result = [
        {
            "_id": ObjectId("666666666666666666666666"),
            "id": "h-1",
            "title": "Hardcoded credential",
            "review_id": "666666666666666666666666",
        }
    ]
    monkeypatch.setattr("app.services.review_repository.get_db", lambda: db)
    resp = client.get("/reviews/octocat/Hello-World/12/findings", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["review_id"] == "666666666666666666666666"
    assert len(data["findings"]) == 1
    assert "_id" not in data["findings"][0]