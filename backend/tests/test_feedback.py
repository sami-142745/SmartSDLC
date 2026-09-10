from datetime import datetime, timedelta, timezone

REVIEW_ID = "1" * 24
FINDING_ID = "g-abc123"


def _now():
    return datetime.now(timezone.utc)


def _seed_review_and_finding(fake_db, *, user_id=42):
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


def test_submit_feedback_requires_auth(client, fake_db):
    resp = client.post(
        "/reviews/octocat/Hello-World/12/findings/g-abc123/feedback",
        json={"action": "accepted"},
    )
    assert resp.status_code == 401


def test_feedback_history_requires_auth(client, fake_db):
    resp = client.get("/reviews/feedback")
    assert resp.status_code == 401


def test_submit_feedback_accepted(client, auth_headers, fake_db):
    _seed_review_and_finding(fake_db)
    resp = client.post(
        "/reviews/octocat/Hello-World/12/findings/g-abc123/feedback",
        json={"action": "accepted"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "accepted"
    assert data["finding_id"] == FINDING_ID
    assert data["review_id"] == REVIEW_ID
    assert data["category"] == "security"
    assert data["severity"] == "high"
    assert data["owner"] == "octocat"
    assert data["repository"] == "Hello-World"
    assert data["pull_request_number"] == 12
    assert len(fake_db["review_feedback"].docs) == 1


def test_submit_feedback_dismissed(client, auth_headers, fake_db):
    _seed_review_and_finding(fake_db)
    resp = client.post(
        "/reviews/octocat/Hello-World/12/findings/g-abc123/feedback",
        json={"action": "dismissed"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["action"] == "dismissed"


def test_submit_feedback_invalid_action(client, auth_headers, fake_db):
    _seed_review_and_finding(fake_db)
    resp = client.post(
        "/reviews/octocat/Hello-World/12/findings/g-abc123/feedback",
        json={"action": "maybe"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_submit_feedback_missing_review_returns_404(client, auth_headers, fake_db):
    resp = client.post(
        "/reviews/octocat/Hello-World/12/findings/g-abc123/feedback",
        json={"action": "accepted"},
        headers=auth_headers,
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Review not found"


def test_submit_feedback_missing_finding_returns_404(client, auth_headers, fake_db):
    _seed_review_and_finding(fake_db)
    fake_db["review_findings"].docs = []
    resp = client.post(
        "/reviews/octocat/Hello-World/12/findings/g-unknown/feedback",
        json={"action": "accepted"},
        headers=auth_headers,
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Finding not found"


def test_submit_feedback_other_users_review_returns_404(client, auth_headers, fake_db):
    _seed_review_and_finding(fake_db, user_id=99)
    resp = client.post(
        "/reviews/octocat/Hello-World/12/findings/g-abc123/feedback",
        json={"action": "accepted"},
        headers=auth_headers,
    )
    assert resp.status_code == 404
    assert fake_db["review_feedback"].docs == []


def test_submit_feedback_duplicate_upserts(client, auth_headers, fake_db):
    _seed_review_and_finding(fake_db)
    headers = auth_headers

    resp1 = client.post(
        "/reviews/octocat/Hello-World/12/findings/g-abc123/feedback",
        json={"action": "accepted"},
        headers=headers,
    )
    assert resp1.status_code == 200
    created_at = resp1.json()["created_at"]

    resp2 = client.post(
        "/reviews/octocat/Hello-World/12/findings/g-abc123/feedback",
        json={"action": "dismissed"},
        headers=headers,
    )
    assert resp2.status_code == 200
    assert resp2.json()["action"] == "dismissed"
    assert len(fake_db["review_feedback"].docs) == 1
    stored = fake_db["review_feedback"].docs[0]
    assert stored["created_at"] is not None
    assert stored["updated_at"] is not None


def test_feedback_history_empty(client, auth_headers, fake_db):
    resp = client.get("/reviews/feedback", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["total_pages"] == 0


def test_feedback_history_returns_items(client, auth_headers, fake_db):
    now = _now()
    fake_db["review_feedback"].docs = [
        {
            "review_id": REVIEW_ID,
            "finding_id": FINDING_ID,
            "user_id": 42,
            "action": "accepted",
            "category": "security",
            "severity": "high",
            "owner": "octocat",
            "repository": "Hello-World",
            "pull_request_number": 12,
            "created_at": now,
            "updated_at": now,
        }
    ]
    resp = client.get("/reviews/feedback", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["total_pages"] == 1
    item = data["items"][0]
    assert item["action"] == "accepted"
    assert item["finding_id"] == FINDING_ID
    assert item["category"] == "security"
    assert item["severity"] == "high"


def test_feedback_history_pagination(client, auth_headers, fake_db):
    now = _now()
    fake_db["review_feedback"].docs = [
        {
            "review_id": REVIEW_ID,
            "finding_id": f"g-{i}",
            "user_id": 42,
            "action": "accepted",
            "category": "security",
            "severity": "high",
            "owner": "octocat",
            "repository": "Hello-World",
            "pull_request_number": 12,
            "created_at": now - timedelta(days=i),
            "updated_at": now - timedelta(days=i),
        }
        for i in range(3)
    ]
    resp = client.get("/reviews/feedback?page=2&per_page=1", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert data["total_pages"] == 3
    assert len(data["items"]) == 1
    assert data["items"][0]["finding_id"] == "g-1"


def test_feedback_history_is_isolated_per_user(client, auth_headers, fake_db):
    fake_db["review_feedback"].docs = [
        {
            "review_id": REVIEW_ID,
            "finding_id": FINDING_ID,
            "user_id": 99,
            "action": "dismissed",
            "category": "bug",
            "severity": "medium",
            "owner": "octocat",
            "repository": "Hello-World",
            "pull_request_number": 12,
            "created_at": _now(),
            "updated_at": _now(),
        }
    ]
    resp = client.get("/reviews/feedback", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["items"] == []


def test_feedback_response_does_not_leak_tokens(client, auth_headers, fake_db):
    _seed_review_and_finding(fake_db)
    resp = client.post(
        "/reviews/octocat/Hello-World/12/findings/g-abc123/feedback",
        json={"action": "accepted"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert "gho_" not in resp.text
    assert "github_access_token" not in resp.text