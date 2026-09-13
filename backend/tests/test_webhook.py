import hashlib
import hmac
import json

import pytest

from app.services import webhook_repository
from app.services.config import settings
from app.services.webhook_security import payload_hash, verify_webhook_signature


def _signature(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _pr_payload(action: str = "opened", number: int = 12) -> bytes:
    payload = {
        "action": action,
        "pull_request": {"number": number, "title": "Fix bug", "state": "open"},
        "repository": {"full_name": "octocat/Hello-World"},
        "sender": {"login": "octocat"},
        "installation": {"id": 99},
    }
    return json.dumps(payload).encode()


@pytest.fixture
def webhook_secret(monkeypatch):
    monkeypatch.setattr(settings, "GITHUB_WEBHOOK_SECRET", "webhook-test-secret")
    return "webhook-test-secret"


def test_verify_webhook_signature_valid(webhook_secret):
    body = b"hello"
    assert verify_webhook_signature(body, _signature(body, webhook_secret), webhook_secret) is True


def test_verify_webhook_signature_invalid(webhook_secret):
    body = b"hello"
    assert verify_webhook_signature(body, "sha256=deadbeef", webhook_secret) is False


def test_verify_webhook_signature_missing(webhook_secret):
    assert verify_webhook_signature(b"hello", None, webhook_secret) is False
    assert verify_webhook_signature(b"hello", "", webhook_secret) is False


def test_webhook_missing_signature_401(client, webhook_secret):
    resp = client.post("/webhook", content=_pr_payload())
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid webhook signature"


def test_webhook_invalid_signature_401(client, webhook_secret):
    resp = client.post(
        "/webhook",
        content=_pr_payload(),
        headers={"X-GitHub-Event": "pull_request", "X-Hub-Signature-256": "sha256=deadbeef"},
    )
    assert resp.status_code == 401


def test_webhook_ping(client, webhook_secret):
    body = b'{"zen": "keep it simple"}'
    resp = client.post(
        "/webhook",
        content=body,
        headers={"X-GitHub-Event": "ping", "X-Hub-Signature-256": _signature(body, webhook_secret)},
    )
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "event": "ping"}


def test_webhook_unsupported_event_ignored(client, webhook_secret):
    body = b'{"ref": "refs/heads/main"}'
    resp = client.post(
        "/webhook",
        content=body,
        headers={"X-GitHub-Event": "push", "X-Hub-Signature-256": _signature(body, webhook_secret)},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"


def test_webhook_supported_pull_request_event_records_data(client, webhook_secret, monkeypatch):
    recorded = {}

    async def fake_record(**kwargs):
        recorded.update(kwargs)

    monkeypatch.setattr("app.routers.webhook.record_webhook_event", fake_record)
    body = _pr_payload(action="opened", number=12)
    resp = client.post(
        "/webhook",
        content=body,
        headers={"X-GitHub-Event": "pull_request", "X-Hub-Signature-256": _signature(body, webhook_secret)},
    )
    assert resp.status_code == 200
    assert resp.json()["action"] == "opened"
    assert recorded["action"] == "opened"
    assert recorded["repository"] == "octocat/Hello-World"
    assert recorded["pull_number"] == 12
    assert recorded["sender"] == "octocat"
    assert recorded["installation_id"] == 99


@pytest.mark.parametrize("action", ["synchronize", "reopened", "closed"])
def test_webhook_all_supported_actions_accepted(client, webhook_secret, monkeypatch, action):
    async def fake_record(**kwargs):
        return None

    monkeypatch.setattr("app.routers.webhook.record_webhook_event", fake_record)
    body = _pr_payload(action=action)
    resp = client.post(
        "/webhook",
        content=body,
        headers={"X-GitHub-Event": "pull_request", "X-Hub-Signature-256": _signature(body, webhook_secret)},
    )
    assert resp.status_code == 200
    assert resp.json()["action"] == action


def test_webhook_unsupported_pr_action_ignored(client, webhook_secret, monkeypatch):
    called = {"count": 0}

    async def fake_record(**kwargs):
        called["count"] += 1

    monkeypatch.setattr("app.routers.webhook.record_webhook_event", fake_record)
    body = _pr_payload(action="labeled")
    resp = client.post(
        "/webhook",
        content=body,
        headers={"X-GitHub-Event": "pull_request", "X-Hub-Signature-256": _signature(body, webhook_secret)},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"
    assert called["count"] == 0


def test_webhook_invalid_json_400(client, webhook_secret):
    body = b"this is not json"
    resp = client.post(
        "/webhook",
        content=body,
        headers={"X-GitHub-Event": "pull_request", "X-Hub-Signature-256": _signature(body, webhook_secret)},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Invalid JSON payload"


def _webhook_headers(body: bytes, webhook_secret: str, delivery: str | None = None) -> dict:
    headers = {"X-GitHub-Event": "pull_request", "X-Hub-Signature-256": _signature(body, webhook_secret)}
    if delivery:
        headers["X-GitHub-Delivery"] = delivery
    return headers


def test_webhook_replay_by_delivery_id_skipped(client, webhook_secret, monkeypatch):
    calls = {"review": 0}

    async def fake_review(owner, repo, number, sender):
        calls["review"] += 1

    monkeypatch.setattr("app.routers.webhook.run_review_for_webhook", fake_review)
    body = _pr_payload(action="opened", number=42)
    headers = _webhook_headers(body, webhook_secret, delivery="deliv-42")

    first = client.post("/webhook", content=body, headers=headers)
    assert first.status_code == 200
    assert first.json()["action"] == "opened"

    replay = client.post("/webhook", content=body, headers=headers)
    assert replay.status_code == 200
    assert replay.json()["status"] == "replayed"
    assert replay.json()["delivery"] == "deliv-42"
    assert calls["review"] == 1


def test_webhook_replay_by_payload_hash_skipped(client, webhook_secret, monkeypatch):
    calls = {"review": 0}

    async def fake_review(owner, repo, number, sender):
        calls["review"] += 1

    monkeypatch.setattr("app.routers.webhook.run_review_for_webhook", fake_review)
    body = _pr_payload(action="synchronize", number=7)
    headers = _webhook_headers(body, webhook_secret)

    first = client.post("/webhook", content=body, headers=headers)
    assert first.status_code == 200
    assert first.json()["action"] == "synchronize"

    replay = client.post("/webhook", content=body, headers=headers)
    assert replay.status_code == 200
    assert replay.json()["status"] == "replayed"
    assert calls["review"] == 1

    stored = webhook_repository.find_webhook_event_by_payload_hash(payload_hash(body))
    assert stored is not None


def test_webhook_distinct_deliveries_not_replayed(client, webhook_secret, monkeypatch):
    calls = {"record": 0}

    async def fake_record(**kwargs):
        calls["record"] += 1

    monkeypatch.setattr("app.routers.webhook.record_webhook_event", fake_record)
    body_sync = _pr_payload(action="synchronize", number=11)
    body_reopened = _pr_payload(action="reopened", number=11)
    headers_sync = _webhook_headers(body_sync, webhook_secret, delivery="delivery-a")
    headers_reopened = _webhook_headers(body_reopened, webhook_secret, delivery="delivery-b")

    first = client.post("/webhook", content=body_sync, headers=headers_sync)
    assert first.json()["action"] == "synchronize"
    second = client.post("/webhook", content=body_reopened, headers=headers_reopened)
    assert second.json()["action"] == "reopened"
    assert second.json()["status"] == "ok"
    assert calls["record"] == 2


def test_webhook_record_stores_delivery_and_hash(client, webhook_secret, monkeypatch, fake_webhook_db):
    body = _pr_payload(action="opened", number=33)
    headers = _webhook_headers(body, webhook_secret, delivery="deliv-33")
    resp = client.post("/webhook", content=body, headers=headers)
    assert resp.status_code == 200
    assert len(fake_webhook_db.webhook_events.docs) == 1
    doc = fake_webhook_db.webhook_events.docs[0]
    assert doc["delivery_id"] == "deliv-33"
    assert doc["payload_hash"] is not None
    assert len(doc["payload_hash"]) == 64


def test_webhook_events_requires_auth(client):
    resp = client.get("/webhook/events")
    assert resp.status_code == 401


def test_webhook_events_empty(client, auth_headers, fake_webhook_db):
    resp = client.get("/webhook/events", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["items"] == []
    assert resp.json()["total"] == 0


def test_webhook_events_lists_recent_deliveries(client, auth_headers, fake_webhook_db, webhook_secret):
    body = _pr_payload(action="opened", number=58)
    headers = _webhook_headers(body, webhook_secret, delivery="deliv-58")
    deliver = client.post("/webhook", content=body, headers=headers)
    assert deliver.status_code == 200

    resp = client.get("/webhook/events", headers=auth_headers)
    assert resp.status_code == 200
    body_out = resp.json()
    assert body_out["total"] == 1
    item = body_out["items"][0]
    assert item["event"] == "pull_request"
    assert item["action"] == "opened"
    assert item["repository"] == "octocat/Hello-World"
    assert item["pull_number"] == 58
    assert item["delivery_id"] == "deliv-58"
    assert item["payload_hash_prefix"].endswith("\u2026")
    assert item["received_at"] is not None


class _FakeCursor:
    def __init__(self, docs):
        self._docs = list(docs)

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
        self._i = 0
        return self

    async def __anext__(self):
        if self._i >= len(self._docs):
            raise StopAsyncIteration
        doc = self._docs[self._i]
        self._i += 1
        return doc


class FakeEvents:
    def __init__(self):
        self.docs = []

    async def insert_one(self, document):
        self.docs.append(document)
        return None

    async def find_one(self, query=None):
        for d in self.docs:
            if all(d.get(key) == value for key, value in (query or {}).items()):
                return dict(d)
        return None

    async def count_documents(self, query=None):
        return len(self.docs)

    def find(self, query=None, **kwargs):
        return _FakeCursor(self.docs)


class FakeDb:
    def __init__(self):
        self.webhook_events = FakeEvents()

    def __getitem__(self, name):
        return getattr(self, name)


@pytest.fixture
def fake_webhook_db(monkeypatch):
    db = FakeDb()
    monkeypatch.setattr("app.services.webhook_repository.get_db", lambda: db)
    return db


@pytest.mark.asyncio
async def test_record_webhook_event_inserts_document(monkeypatch, fake_webhook_db):
    db = fake_webhook_db

    await webhook_repository.record_webhook_event(
        event="pull_request",
        action="opened",
        repository="octocat/Hello-World",
        pull_number=12,
        sender="octocat",
        installation_id=99,
    )

    doc = db.webhook_events.docs[0]
    assert doc["event"] == "pull_request"
    assert doc["action"] == "opened"
    assert doc["repository"] == "octocat/Hello-World"
    assert doc["pull_number"] == 12
    assert doc["sender"] == "octocat"
    assert doc["installation_id"] == 99
    assert doc["processed"] is True
    assert doc["received_at"] is not None


@pytest.mark.parametrize("action", ["opened", "synchronize", "reopened"])
def test_webhook_triggers_review_for_reviewable_actions(client, webhook_secret, monkeypatch, action):
    called = {"review_args": None}

    async def fake_record(**kwargs):
        pass

    async def fake_review(owner, repo, number, sender):
        called["review_args"] = (owner, repo, number, sender)

    monkeypatch.setattr("app.routers.webhook.record_webhook_event", fake_record)
    monkeypatch.setattr("app.routers.webhook.run_review_for_webhook", fake_review)
    body = _pr_payload(action=action, number=42)
    resp = client.post(
        "/webhook",
        content=body,
        headers={"X-GitHub-Event": "pull_request", "X-Hub-Signature-256": _signature(body, webhook_secret)},
    )
    assert resp.status_code == 200
    assert resp.json()["action"] == action
    assert called["review_args"] == ("octocat", "Hello-World", 42, "octocat")


def test_webhook_closed_does_not_trigger_review(client, webhook_secret, monkeypatch):
    called = {"review_args": None}

    async def fake_record(**kwargs):
        pass

    async def fake_review(owner, repo, number, sender):
        called["review_args"] = (owner, repo, number, sender)

    monkeypatch.setattr("app.routers.webhook.record_webhook_event", fake_record)
    monkeypatch.setattr("app.routers.webhook.run_review_for_webhook", fake_review)
    body = _pr_payload(action="closed", number=99)
    resp = client.post(
        "/webhook",
        content=body,
        headers={"X-GitHub-Event": "pull_request", "X-Hub-Signature-256": _signature(body, webhook_secret)},
    )
    assert resp.status_code == 200
    assert called["review_args"] is None


def test_webhook_labeled_does_not_trigger_review(client, webhook_secret, monkeypatch):
    called = {"review_args": None}

    async def fake_record(**kwargs):
        pass

    async def fake_review(owner, repo, number, sender):
        called["review_args"] = (owner, repo, number, sender)

    monkeypatch.setattr("app.routers.webhook.record_webhook_event", fake_record)
    monkeypatch.setattr("app.routers.webhook.run_review_for_webhook", fake_review)
    body = _pr_payload(action="labeled", number=55)
    resp = client.post(
        "/webhook",
        content=body,
        headers={"X-GitHub-Event": "pull_request", "X-Hub-Signature-256": _signature(body, webhook_secret)},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"
    assert called["review_args"] is None