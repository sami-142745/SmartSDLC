from datetime import datetime, timezone

import pytest

from app.services import workflow_repository, workflow_service
from app.services.github_client import GitHubAPIError


REVIEW_RESULT = {
    "status": "complete",
    "repository": "Hello-World",
    "owner": "octocat",
    "pull_request_number": 12,
    "pull_request_title": "Fix the thing",
    "commit_sha": "abc123",
    "review_id": "review_abc123",
    "findings": [],
    "review_score": 95,
    "review_severity": "low",
    "duration_ms": 5,
}


async def _seed_workflow(db, user_id=42, trigger="manual", repository="Hello-World", status="queued"):
    doc = {
        "workflow_id": "wf_seed_01",
        "user_id": user_id,
        "owner": "octocat",
        "repository": repository,
        "pull_request_number": 12,
        "trigger": trigger,
        "provider": "github",
        "initiated_by": "api",
        "status": status,
        "stage": "RECEIVED" if status == "queued" else status.upper(),
        "error": None,
        "review_id": None,
        "history": [{"stage": "RECEIVED", "at": datetime.now(timezone.utc)}],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    await db["workflows"].insert_one(doc)
    return doc


def test_list_workflows_requires_auth(client):
    resp = client.get("/workflows")
    assert resp.status_code == 401


def test_get_workflow_requires_auth(client):
    resp = client.get("/workflows/wf_seed_01")
    assert resp.status_code == 401


def test_list_workflows_empty(client, auth_headers, fake_db):
    resp = client.get("/workflows", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["page"] == 1
    assert body["total_pages"] == 0


def test_list_workflows_returns_items(client, auth_headers, fake_db):
    import asyncio

    async def _seed():
        await _seed_workflow(fake_db, status="completed")
        return None

    asyncio.run(_seed())

    resp = client.get("/workflows", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["total_pages"] == 1
    item = body["items"][0]
    assert item["workflow_id"] == "wf_seed_01"
    assert item["repository"] == "Hello-World"
    assert item["pull_request_number"] == 12
    assert item["status"] == "completed"
    assert item["provider"] == "github"


def test_list_workflows_filters_by_status_and_repository(client, auth_headers, fake_db):
    import asyncio

    async def _seed():
        await _seed_workflow(fake_db, status="failed", repository="Other-Repo")
        await _seed_workflow(fake_db, status="failed")
        return None

    asyncio.run(_seed())

    resp = client.get("/workflows?status=failed&repository=Other-Repo", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["repository"] == "Other-Repo"


def test_list_workflows_scoped_to_user(client, auth_headers, fake_db):
    import asyncio

    async def _seed():
        await _seed_workflow(fake_db, user_id=999)
        await _seed_workflow(fake_db, user_id=42)
        return None

    asyncio.run(_seed())

    resp = client.get("/workflows", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert all(item["workflow_id"] == "wf_seed_01" for item in items)


def test_get_workflow_returns_history(client, auth_headers, fake_db):
    import asyncio

    async def _seed():
        await _seed_workflow(fake_db)
        return None

    asyncio.run(_seed())

    resp = client.get("/workflows/wf_seed_01", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["workflow_id"] == "wf_seed_01"
    assert body["stage"] == "RECEIVED"
    assert body["history"][0]["stage"] == "RECEIVED"
    assert body["history"][0]["at"] is not None


def test_get_workflow_not_found(client, auth_headers, fake_db):
    resp = client.get("/workflows/nope", headers=auth_headers)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Workflow not found"


def test_get_workflow_hides_other_users_workflow(client, auth_headers, fake_db):
    import asyncio

    async def _seed():
        await _seed_workflow(fake_db, user_id=999)
        return None

    asyncio.run(_seed())

    resp = client.get("/workflows/wf_seed_01", headers=auth_headers)
    assert resp.status_code == 404


def test_repository_transitions_history_and_status(fake_db):
    import asyncio

    async def _run():
        wid = await workflow_service.begin_workflow(
            user_id=42,
            owner="octocat",
            repository="Hello-World",
            pull_request_number=12,
            trigger="manual",
            initiated_by="api",
        )
        assert wid is not None
        await workflow_service.advance_workflow(wid, "FETCHING")
        await workflow_service.complete_workflow(wid, review_id="review_1")
        doc = await workflow_repository.get_workflow(wid, user_id=42)
        return doc

    doc = asyncio.run(_run())
    stages = [h["stage"] for h in doc["history"]]
    assert stages == ["RECEIVED", "FETCHING", "COMPLETED"]
    assert doc["status"] == "completed"
    assert doc["stage"] == "COMPLETED"
    assert doc["review_id"] == "review_1"
    assert doc["duration_ms"] >= 0


def test_repository_failed_captures_error(fake_db):
    import asyncio

    async def _run():
        wid = await workflow_service.begin_workflow(
            user_id=42,
            owner="octocat",
            repository="Hello-World",
            pull_request_number=12,
            trigger="manual",
            initiated_by="api",
        )
        await workflow_service.fail_workflow(wid, error="boom")
        return await workflow_repository.get_workflow(wid, user_id=42)

    doc = asyncio.run(_run())
    assert doc["status"] == "failed"
    assert doc["stage"] == "FAILED"
    assert doc["error"] == "boom"


def test_create_review_records_completed_workflow(client, auth_headers, fake_db, monkeypatch):
    async def _fake_run_review(gh, o, r, n, user_id=None, **kwargs):
        return REVIEW_RESULT

    monkeypatch.setattr("app.routers.reviews.run_review", _fake_run_review)
    resp = client.post("/reviews/octocat/Hello-World/12", headers=auth_headers)
    assert resp.status_code == 200
    docs = fake_db["workflows"].docs
    assert len(docs) == 1
    wf = docs[0]
    assert wf["status"] == "completed"
    assert wf["stage"] == "COMPLETED"
    assert wf["review_id"] == "review_abc123"
    stages = [h["stage"] for h in wf["history"]]
    assert "RECEIVED" in stages
    assert "VALIDATED" in stages


def test_create_review_failure_marks_workflow_failed(client, auth_headers, fake_db, monkeypatch):
    async def _error_review(gh, o, r, n, user_id=None, **kwargs):
        raise GitHubAPIError(404, "Not Found", "not_found")

    monkeypatch.setattr("app.routers.reviews.run_review", _error_review)
    resp = client.post("/reviews/octocat/Hello-World/12", headers=auth_headers)
    assert resp.status_code == 404
    docs = fake_db["workflows"].docs
    assert len(docs) == 1
    wf = docs[0]
    assert wf["status"] == "failed"
    assert wf["stage"] == "FAILED"
    assert wf["error"] == "Not Found"


def test_begin_workflow_is_best_effort(monkeypatch):
    async def _boom(*args, **kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr("app.services.workflow_repository.create_workflow", _boom)

    import asyncio

    wid = asyncio.run(
        workflow_service.begin_workflow(
            user_id=42,
            owner="octocat",
            repository="Hello-World",
            pull_request_number=12,
            trigger="manual",
            initiated_by="api",
        )
    )
    assert wid is None