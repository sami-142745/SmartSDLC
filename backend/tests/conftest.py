import datetime

import pytest
from bson import ObjectId as _ObjectId
from fastapi.testclient import TestClient

from app.services.jwt_service import create_access_token


async def _noop_indexes() -> None:
    return None


def _match_query(doc: dict, query: dict) -> bool:
    for key, cond in query.items():
        val = doc.get(key)
        if isinstance(cond, _ObjectId):
            if str(val) != str(cond):
                return False
            continue
        if isinstance(cond, dict) and any(k in cond for k in ("$gte", "$lte", "$gt", "$lt")):
            if "$gte" in cond and (val is None or val < cond["$gte"]):
                return False
            if "$lte" in cond and (val is None or val > cond["$lte"]):
                return False
            if "$gt" in cond and (val is None or val <= cond["$gt"]):
                return False
            if "$lt" in cond and (val is None or val >= cond["$lt"]):
                return False
            return True
        if isinstance(cond, dict) and "$in" in cond:
            if val not in cond["$in"]:
                return False
            continue
        if isinstance(cond, dict) and "$ne" in cond:
            if val == cond["$ne"]:
                return False
            continue
        if val != cond:
            return False
    return True


class FakeCursor:
    def __init__(self, docs, sort_keys=None):
        self._docs = list(docs or [])
        self._sort = None
        self._skip = 0
        self._limit = None
        self._idx = 0
        # Optional Python callables a collection can supply for a given field, so
        # a service's ``sort([("severity", 1), ...])`` is ordered by the same rule
        # production Mongo would use, rather than by raw string order.
        self._sort_keys = sort_keys or {}

    def sort(self, key, direction=-1):
        # Accepts both a single (key, direction) pair and a list of them, so
        # compound sort keys are exercised faithfully.
        if isinstance(key, (list, tuple)) and key and isinstance(key[0], (list, tuple)):
            self._sort = [(k, d) for k, d in key]
        else:
            self._sort = [(key, direction)]
        return self

    def skip(self, n):
        self._skip = int(n)
        return self

    def limit(self, n):
        self._limit = int(n)
        return self

    def _materialize(self):
        docs = self._docs
        if self._sort:
            for key, direction in reversed(self._sort):
                accessor = self._sort_keys.get(key)
                if accessor is not None:
                    docs = sorted(
                        docs,
                        key=lambda d: accessor(d.get(key)),
                        reverse=(direction == -1),
                    )
                else:
                    docs = sorted(
                        docs, key=lambda d: d.get(key), reverse=(direction == -1)
                    )
        docs = docs[self._skip:]
        if self._limit is not None:
            docs = docs[: self._limit]
        return docs

    def __aiter__(self):
        self._idx = 0
        return self

    async def __anext__(self):
        docs = self._materialize()
        if self._idx >= len(docs):
            raise StopAsyncIteration
        doc = docs[self._idx]
        self._idx += 1
        return doc


class _InsertResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id
        self.acknowledged = True

    def __getattr__(self, name):
        return None


def _group_markers(pipeline) -> set:
    markers = set()
    for stage in pipeline or []:
        if not isinstance(stage, dict):
            continue
        if "$group" in stage:
            gid = stage["$group"].get("_id")
            if isinstance(gid, str):
                markers.add(gid)
            elif isinstance(gid, dict):
                markers.update(str(v) for v in gid.values())
        if "$match" in stage:
            markers.update(str(v) for v in stage["$match"].values() if isinstance(v, str))
    return markers


class FakeCollection:
    def __init__(self, sort_keys=None):
        self.docs = []
        self.aggregate_results = {}
        self._default_aggregate = []
        self.findOne_result = None
        self.records = []
        self.sort_keys = sort_keys or {}

    async def insert_one(self, document):
        doc = dict(document)
        doc.setdefault("_id", self._next_id())
        self.docs.append(doc)
        return _InsertResult(doc["_id"])

    async def insert_many(self, documents):
        docs = [dict(d) for d in documents]
        for d in docs:
            d.setdefault("_id", self._next_id())
        self.docs.extend(docs)

    def _next_id(self) -> str:
        return f"{len(self.docs) + 1:024d}"

    def find(self, query=None, projection=None, **kwargs):
        filtered = [d for d in self.docs if _match_query(d, query or {})]
        return FakeCursor(filtered, sort_keys=self.sort_keys)

    async def find_one(self, query=None, sort=None, **kwargs):
        matches = [d for d in self.docs if _match_query(d, query or {})]
        if sort is not None and matches:
            # pymongo's ``find_one(sort=...)`` returns the first document in the
            # sort order, which is how "latest scan for this repository" is
            # expressed. Reproduce that rather than the insertion order.
            accessor = None
            if isinstance(sort, (list, tuple)) and sort:
                accessor = self.sort_keys.get(sort[0][0])
            if accessor is not None:
                first, direction = sort[0]
                matches = sorted(
                    matches, key=lambda d: accessor(d.get(first)), reverse=(direction == -1)
                )
            else:
                for key, direction in reversed(list(sort)):
                    matches = sorted(
                        matches, key=lambda d: d.get(key), reverse=(direction == -1)
                    )
            return dict(matches[0])
        for d in matches:
            return dict(d)
        return self.findOne_result

    async def count_documents(self, query=None):
        return sum(1 for d in self.docs if _match_query(d, query or {}))

    def aggregate(self, pipeline):
        markers = _group_markers(pipeline)
        for marker in ("$severity", "$category", "$action"):
            if marker in markers and marker in self.aggregate_results:
                return FakeCursor(self.aggregate_results[marker])
        return FakeCursor(self._default_aggregate)

    async def update_one(self, query, update=None, upsert=False):
        doc = None
        for d in self.docs:
            if _match_query(d, query or {}):
                doc = d
                break
        if doc is None and upsert:
            merged = dict(query)
            merged.update((update or {}).get("$set", {}))
            merged.setdefault("_id", self._next_id())
            for k, v in (update or {}).get("$setOnInsert", {}).items():
                merged.setdefault(k, v)
            self.docs.append(merged)
            return _InsertResult(merged["_id"])
        if doc is not None:
            for k, v in (update or {}).get("$set", {}).items():
                doc[k] = v
            for k, v in (update or {}).get("$setOnInsert", {}).items():
                doc.setdefault(k, v)
        return _InsertResult((doc or {}).get("_id"))

    async def create_index(self, *args, **kwargs):
        return None

    async def delete_many(self, query=None):
        self.docs = [d for d in self.docs if not _match_query(d, query or {})]

        class _DeleteResult:
            deleted_count = 0
            acknowledged = True

        return _DeleteResult()


class FakeDb:
    def __init__(self):
        self.collections = {
            "reviews": FakeCollection(),
            "review_findings": FakeCollection(),
            "review_feedback": FakeCollection(),
            "ai_reviews": FakeCollection(),
            "ai_review_findings": FakeCollection(),
            "users": FakeCollection(),
            "webhook_events": FakeCollection(),
            "documents": FakeCollection(),
            "insights": FakeCollection(),
            "feedback_learning": FakeCollection(),
            "workflows": FakeCollection(),
            "repository_analysis": FakeCollection(),
            # Severity sorts by canonical rank, not alphabetically: "critical"
            # must come before "high", which a raw string sort would get right by
            # luck but "info" before "low" would not.
            "security_scans": FakeCollection(),
            "security_findings": FakeCollection(
                sort_keys={"severity": _severity_rank}
            ),
        }

    def __getitem__(self, name):
        return self.collections[name]


def _severity_rank(value):
    """Sort key giving the canonical severity order.

    Defined here rather than imported from the app so the fake database has no
    dependency on application code; the value must stay in step with
    ``app.schemas.security.SEVERITIES``.
    """
    order = ("critical", "high", "medium", "low", "info")
    try:
        return order.index(value)
    except ValueError:
        return len(order)


def _utcnow():
    return datetime.datetime.now(datetime.timezone.utc)


@pytest.fixture
def client(monkeypatch):
    from app.main import app

    monkeypatch.setattr("app.services.user_repository.ensure_indexes", _noop_indexes)
    monkeypatch.setattr("app.services.review_repository.ensure_indexes", _noop_indexes)
    monkeypatch.setattr("app.services.ai_review_repository.ensure_indexes", _noop_indexes)
    monkeypatch.setattr("app.services.document_repository.ensure_indexes", _noop_indexes)
    monkeypatch.setattr("app.services.insight_repository.ensure_indexes", _noop_indexes)
    monkeypatch.setattr("app.services.learning_repository.ensure_indexes", _noop_indexes)
    monkeypatch.setattr("app.services.workflow_repository.ensure_indexes", _noop_indexes)
    monkeypatch.setattr("app.services.webhook_repository.ensure_indexes", _noop_indexes)
    monkeypatch.setattr("app.services.repository_analysis_repository.ensure_indexes", _noop_indexes)
    monkeypatch.setattr("app.services.security_repository.ensure_indexes", _noop_indexes)
    monkeypatch.setattr("app.services.workflow_repository.get_db", lambda: FakeDb())
    webhook_db = FakeDb()
    monkeypatch.setattr("app.services.webhook_repository.get_db", lambda: webhook_db)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def fake_db(monkeypatch):
    db = FakeDb()
    monkeypatch.setattr("app.services.review_repository.get_db", lambda: db)
    monkeypatch.setattr("app.services.ai_review_repository.get_db", lambda: db)
    monkeypatch.setattr("app.services.learning_repository.get_db", lambda: db)
    monkeypatch.setattr("app.services.workflow_repository.get_db", lambda: db)
    return db


@pytest.fixture
def insight_db(monkeypatch):
    db = FakeDb()
    monkeypatch.setattr("app.services.review_repository.get_db", lambda: db)
    monkeypatch.setattr("app.services.insight_repository.get_db", lambda: db)
    return db


@pytest.fixture
def repository_analysis_db(monkeypatch):
    db = FakeDb()
    monkeypatch.setattr(
        "app.services.repository_analysis_repository.get_db", lambda: db
    )
    return db


@pytest.fixture
def security_db(monkeypatch):
    """Fake database for the security collections."""
    db = FakeDb()
    monkeypatch.setattr("app.services.security_repository.get_db", lambda: db)
    return db


@pytest.fixture
def auth_headers(monkeypatch):
    async def known_user(github_id):
        return {
            "_id": "1" * 24,
            "github_id": 42,
            "login": "octocat",
            "name": "Octo Cat",
            "github_access_token": "gho_super_secret_token",
        }

    monkeypatch.setattr("app.services.security.get_user_by_github_id", known_user)
    token = create_access_token({"sub": "42", "login": "octocat"})
    return {"Authorization": f"Bearer {token}"}