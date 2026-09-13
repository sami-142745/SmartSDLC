from datetime import datetime, timedelta, timezone

import pytest

from app.services import feedback_learning_service

REVIEW_ID = "1" * 24
FINDING_ID = "g-abc123"
USER_ID = 42


def _now():
    return datetime.now(timezone.utc)


def _seed_review_and_finding(fake_db, *, user_id=USER_ID):
    fake_db["reviews"].docs = [
        {
            "_id": REVIEW_ID,
            "user_id": user_id,
            "owner": "octocat",
            "repository": "Hello-World",
            "pull_request_number": 12,
        }
    ]
    fake_db["review_findings"].docs = [
        {
            "_id": "2" * 24,
            "review_id": REVIEW_ID,
            "id": FINDING_ID,
            "title": "Hardcoded credential",
            "category": "security",
            "severity": "high",
        }
    ]


def _seed_profile(fake_db, *, user_id=USER_ID, owner="octocat", repository="Hello-World", category="security", accepted=0, dismissed=0):
    fake_db["feedback_learning"].docs.append(
        {
            "user_id": user_id,
            "owner": owner,
            "repository": repository,
            "category": category,
            "accepted_count": accepted,
            "dismissed_count": dismissed,
            "created_at": _now(),
            "updated_at": _now(),
        }
    )


def test_learning_list_requires_auth(client, fake_db):
    resp = client.get("/feedback/learning")
    assert resp.status_code == 401


def test_learning_repo_requires_auth(client, fake_db):
    resp = client.get("/feedback/learning/octocat/Hello-World")
    assert resp.status_code == 401


def test_learning_recalculate_requires_auth(client, fake_db):
    resp = client.post("/feedback/learning/recalculate")
    assert resp.status_code == 401


def test_learning_empty(client, auth_headers, fake_db):
    resp = client.get("/feedback/learning", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["profiles"] == []
    assert data["data_available"] is False
    assert data["total_feedback"] == 0
    assert data["repositories"] == []
    assert data["categories"] == []


def test_learning_lists_profiles(client, auth_headers, fake_db):
    _seed_profile(fake_db, accepted=4, dismissed=1)
    resp = client.get("/feedback/learning", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["data_available"] is True
    assert data["repositories"] == ["Hello-World"]
    assert data["categories"] == ["security"]
    assert data["total_feedback"] == 5
    profile = data["profiles"][0]
    assert profile["owner"] == "octocat"
    assert profile["repository"] == "Hello-World"
    assert profile["category"] == "security"
    assert profile["accepted_count"] == 4
    assert profile["dismissed_count"] == 1
    assert profile["total_count"] == 5
    assert profile["acceptance_rate"] == 0.8
    assert profile["learned_weight"] == 1.09
    assert profile["confidence"] == 1.0


def test_learning_repo_scope_filters(client, auth_headers, fake_db):
    _seed_profile(fake_db, owner="octocat", repository="Hello-World", category="security", accepted=1)
    _seed_profile(fake_db, owner="octocat", repository="Other-Repo", category="bug", accepted=2)
    resp = client.get("/feedback/learning/octocat/Hello-World", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["profiles"]) == 1
    assert data["profiles"][0]["repository"] == "Hello-World"
    assert data["repositories"] == ["Hello-World"]


def test_learning_isolated_per_user(client, auth_headers, fake_db):
    _seed_profile(fake_db, user_id=99, accepted=9)
    _seed_profile(fake_db, user_id=42, accepted=1)
    resp = client.get("/feedback/learning", headers=auth_headers)
    data = resp.json()
    assert len(data["profiles"]) == 1
    assert data["profiles"][0]["accepted_count"] == 1


def test_submit_feedback_updates_learning_profile(client, auth_headers, fake_db):
    _seed_review_and_finding(fake_db)
    resp = client.post(
        "/reviews/octocat/Hello-World/12/findings/g-abc123/feedback",
        json={"action": "accepted"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    stored = fake_db["feedback_learning"].docs
    assert len(stored) == 1
    assert stored[0]["owner"] == "octocat"
    assert stored[0]["repository"] == "Hello-World"
    assert stored[0]["category"] == "security"
    assert stored[0]["accepted_count"] == 1

    resp2 = client.post(
        "/reviews/octocat/Hello-World/12/findings/g-abc123/feedback",
        json={"action": "dismissed"},
        headers=auth_headers,
    )
    assert resp2.status_code == 200
    stored = fake_db["feedback_learning"].docs
    assert len(stored) == 1
    assert stored[0]["accepted_count"] == 1
    assert stored[0]["dismissed_count"] == 1


def test_recalculate_rebuilds_from_raw_feedback(client, auth_headers, fake_db):
    now = _now()
    fake_db["review_feedback"].docs = [
        {
            "review_id": REVIEW_ID,
            "finding_id": f"g-{i}",
            "user_id": USER_ID,
            "action": "accepted" if i % 5 else "dismissed",
            "category": "security",
            "severity": "high",
            "owner": "octocat",
            "repository": "Hello-World",
            "pull_request_number": 12,
            "created_at": now - timedelta(minutes=i),
            "updated_at": now - timedelta(minutes=i),
        }
        for i in range(5)
    ]
    _seed_profile(fake_db, category="style", accepted=3)

    resp = client.post("/feedback/learning/recalculate", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_feedback"] == 5
    profiles = {p["category"]: p for p in data["profiles"]}
    assert "security" in profiles
    assert profiles["security"]["accepted_count"] == 4
    assert profiles["security"]["dismissed_count"] == 1
    assert "style" not in profiles
    stored_categories = {doc["category"] for doc in fake_db["feedback_learning"].docs}
    assert stored_categories == {"security"}


@pytest.mark.asyncio
async def test_resolve_weights_repo_precedence(fake_db):
    _seed_profile(fake_db, accepted=4, dismissed=1)
    weights = await feedback_learning_service.resolve_learning_weights(
        USER_ID, "octocat", "Hello-World", {"security"}
    )
    assert weights["security"]["source"] == "repository+category"
    assert weights["security"]["weight"] == 1.09
    assert weights["security"]["pct"] == 9.0


@pytest.mark.asyncio
async def test_resolve_weights_user_scope_fallback(fake_db):
    _seed_profile(fake_db, repository="Other-Repo", category="security", accepted=4, dismissed=1)
    weights = await feedback_learning_service.resolve_learning_weights(
        USER_ID, "octocat", "Hello-World", {"security"}
    )
    assert weights["security"]["source"] == "user+category"
    assert weights["security"]["weight"] == 1.09


@pytest.mark.asyncio
async def test_resolve_weights_defaults_when_insufficient(fake_db):
    _seed_profile(fake_db, accepted=1, dismissed=0)
    weights = await feedback_learning_service.resolve_learning_weights(
        USER_ID, "octocat", "Hello-World", {"security", "bug"}
    )
    assert weights["security"]["source"] == "default"
    assert weights["security"]["weight"] == 1.0
    assert weights["security"]["pct"] == 0.0
    assert weights["bug"] == {"weight": 1.0, "pct": 0.0, "source": "default"}


@pytest.mark.asyncio
async def test_resolve_weights_tolerates_db_failure(fake_db, monkeypatch):
    async def _explode(*args, **kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr("app.services.learning_repository.list_profiles", _explode)
    weights = await feedback_learning_service.resolve_learning_weights(
        USER_ID, "octocat", "Hello-World", {"security"}
    )
    assert weights["security"] == {"weight": 1.0, "pct": 0.0, "source": "default"}


def test_annotate_findings_neutral():
    findings = [{"id": "h-1", "severity": "high", "category": "security", "source": "heuristic"}]
    annotated = feedback_learning_service.annotate_findings(findings, {})
    assert annotated[0]["final_priority"] == 3.0
    assert annotated[0]["feedback_weight"] == 1.0
    assert annotated[0]["feedback_adjustment_pct"] == 0.0
    assert annotated[0]["adjustment_source"] == "default"
    assert annotated[0]["severity"] == "high"


def test_annotate_findings_applies_weight():
    findings = [{"id": "h-1", "severity": "high", "category": "security"}]
    weights = {"security": {"weight": 1.05, "pct": 5.0, "source": "repository+category"}}
    annotated = feedback_learning_service.annotate_findings(findings, weights)
    assert annotated[0]["final_priority"] == 3.15
    assert annotated[0]["feedback_weight"] == 1.05
    assert annotated[0]["feedback_adjustment_pct"] == 5.0
    assert annotated[0]["adjustment_source"] == "repository+category"


class _FakeGitHubClient:
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


@pytest.mark.asyncio
async def test_run_review_annotates_findings_with_learning(monkeypatch, fake_db):
    async def _gemini_empty(context):
        return []

    monkeypatch.setattr("app.services.review_service.review_code", _gemini_empty)

    from app.services.review_service import run_review

    for category in ("security", "bug", "performance", "complexity", "maintainability", "style", "unknown"):
        _seed_profile(fake_db, category=category, accepted=8, dismissed=2)

    result = await run_review(_FakeGitHubClient(), "octocat", "Hello-World", 12, user_id=USER_ID)
    assert result["status"] == "complete"
    assert result["findings"]
    assert all("final_priority" in finding for finding in result["findings"])
    assert all(
        finding["adjustment_source"] == "repository+category"
        for finding in result["findings"]
    )
    assert any(finding["feedback_weight"] == 1.09 for finding in result["findings"])


@pytest.mark.asyncio
async def test_run_review_without_user_skips_learning_lookup(monkeypatch, fake_db):
    async def _gemini_empty(context):
        return []

    monkeypatch.setattr("app.services.review_service.review_code", _gemini_empty)

    from app.services.review_service import run_review

    result = await run_review(_FakeGitHubClient(), "octocat", "Hello-World", 12)
    assert result["status"] == "complete"
    assert result["findings"]
    assert all(finding["adjustment_source"] == "default" for finding in result["findings"])
    assert all(finding["feedback_weight"] == 1.0 for finding in result["findings"])
    assert fake_db["feedback_learning"].docs == []