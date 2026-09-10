from datetime import datetime, timedelta, timezone

import pytest

EMPTY_SEVERITY = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
EMPTY_CATEGORY = {
    "security": 0,
    "bug": 0,
    "performance": 0,
    "complexity": 0,
    "maintainability": 0,
    "style": 0,
}


def _now():
    return datetime.now(timezone.utc)


FIXED_NOW = datetime(2026, 9, 9, 14, 0, 0, tzinfo=timezone.utc)  # Wednesday 2026-09-09


def _review_doc(
    _id,
    repository,
    pr_number,
    *,
    user_id=42,
    status="complete",
    title="PR title",
    commit_sha="sha-1",
    created_at=None,
    total=0,
):
    created_at = created_at or _now()
    return {
        "_id": _id,
        "user_id": user_id,
        "owner": "octocat",
        "repository": repository,
        "pull_request_number": pr_number,
        "pull_request_title": title,
        "status": status,
        "commit_sha": commit_sha,
        "review_score": 0.5,
        "review_severity": "medium",
        "total_finding_count": total,
        "critical_count": 0,
        "high_count": 0,
        "medium_count": 0,
        "low_count": total,
        "info_count": 0,
        "heuristic_finding_count": total,
        "gemini_finding_count": 0,
        "error": None,
        "created_at": created_at,
        "updated_at": created_at,
    }


def test_dashboard_requires_auth(client):
    resp = client.get("/dashboard")
    assert resp.status_code == 401


def test_history_requires_auth(client):
    resp = client.get("/history")
    assert resp.status_code == 401


def test_repository_metrics_requires_auth(client):
    resp = client.get("/dashboard/repositories")
    assert resp.status_code == 401


def test_feedback_summary_requires_auth(client):
    resp = client.get("/dashboard/feedback-summary")
    assert resp.status_code == 401


def test_dashboard_empty_returns_zero_structures(client, auth_headers, fake_db):
    resp = client.get("/dashboard", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_reviews"] == 0
    assert data["total_findings"] == 0
    assert data["critical_findings"] == 0
    assert data["high_findings"] == 0
    assert data["medium_findings"] == 0
    assert data["low_findings"] == 0
    assert data["info_findings"] == 0
    assert data["reviews_today"] == 0
    assert data["reviews_this_week"] == 0
    assert data["reviews_this_month"] == 0
    assert data["average_findings_per_review"] == 0.0
    assert data["recent_reviews"] == []
    assert data["severity_distribution"] == EMPTY_SEVERITY
    assert data["category_distribution"] == EMPTY_CATEGORY


def test_dashboard_populated_aggregates(client, auth_headers, fake_db, monkeypatch):
    monkeypatch.setattr("app.services.dashboard_service._utcnow", lambda: FIXED_NOW)
    fake_db["reviews"].docs = [
        _review_doc("1" * 24, "repo-a", 1, created_at=FIXED_NOW - timedelta(hours=1), total=3),
        _review_doc("2" * 24, "repo-a", 2, created_at=FIXED_NOW - timedelta(hours=2), total=5),
        _review_doc("3" * 24, "repo-b", 3, created_at=FIXED_NOW - timedelta(days=3), total=0),
        _review_doc("4" * 24, "repo-b", 4, created_at=FIXED_NOW - timedelta(days=40), total=0),
    ]
    fake_db["review_findings"].aggregate_results["$severity"] = [
        {"_id": "critical", "count": 2},
        {"_id": "high", "count": 1},
        {"_id": "low", "count": 5},
    ]
    fake_db["review_findings"].aggregate_results["$category"] = [
        {"_id": "security", "count": 3},
        {"_id": "bug", "count": 5},
    ]

    resp = client.get("/dashboard", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_reviews"] == 4
    assert data["total_findings"] == 8
    assert data["critical_findings"] == 2
    assert data["high_findings"] == 1
    assert data["medium_findings"] == 0
    assert data["low_findings"] == 5
    assert data["info_findings"] == 0
    # FIXED_NOW = Wed 2026-09-09; week starts Mon 09-07, month starts 09-01.
    assert data["reviews_today"] == 2
    assert data["reviews_this_week"] == 2
    assert data["reviews_this_month"] == 3
    assert data["average_findings_per_review"] == 2.0
    assert data["severity_distribution"] == {
        "critical": 2,
        "high": 1,
        "medium": 0,
        "low": 5,
        "info": 0,
    }
    assert data["category_distribution"] == {
        "security": 3,
        "bug": 5,
        "performance": 0,
        "complexity": 0,
        "maintainability": 0,
        "style": 0,
    }
    assert len(data["recent_reviews"]) == 4
    assert data["recent_reviews"][0]["repository"] == "repo-a"
    assert data["recent_reviews"][0]["pull_request_title"] == "PR title"


def test_dashboard_response_does_not_leak_tokens(client, auth_headers, fake_db):
    fake_db["reviews"].docs = [_review_doc("1" * 24, "repo-a", 1, total=1)]
    resp = client.get("/dashboard", headers=auth_headers)
    assert resp.status_code == 200
    assert "gho_" not in resp.text
    assert "github_access_token" not in resp.text
    assert "authorization" not in resp.text.lower()


def test_dashboard_only_counts_own_user(client, auth_headers, fake_db):
    now = _now()
    fake_db["reviews"].docs = [
        _review_doc("1" * 24, "repo-a", 1, user_id=42, created_at=now, total=1),
        _review_doc("2" * 24, "repo-a", 2, user_id=99, created_at=now, total=9),
    ]
    resp = client.get("/dashboard", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total_reviews"] == 1
    assert resp.json()["recent_reviews"][0]["pull_request_number"] == 1


def test_history_empty(client, auth_headers, fake_db):
    resp = client.get("/history", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["total_pages"] == 0
    assert data["page"] == 1
    assert data["per_page"] == 20


def test_history_pagination_and_ordering(client, auth_headers, fake_db):
    now = _now()
    docs = [
        _review_doc(f"{i + 1:024d}", "repo-a", i + 1, created_at=now - timedelta(days=i), total=i)
        for i in range(5)
    ]
    fake_db["reviews"].docs = docs

    resp = client.get("/history?page=2&per_page=2", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    assert data["total_pages"] == 3
    assert data["page"] == 2
    assert data["per_page"] == 2
    assert len(data["items"]) == 2
    assert data["items"][0]["pull_request_number"] == 3


def test_history_defaults_newest_first(client, auth_headers, fake_db):
    now = _now()
    fake_db["reviews"].docs = [
        _review_doc("1" * 24, "repo-a", 1, created_at=now - timedelta(days=5)),
        _review_doc("2" * 24, "repo-b", 2, created_at=now),
    ]
    resp = client.get("/history", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert items[0]["pull_request_number"] == 2


def test_history_filters_by_repository(client, auth_headers, fake_db):
    now = _now()
    fake_db["reviews"].docs = [
        _review_doc("1" * 24, "repo-a", 1, created_at=now),
        _review_doc("2" * 24, "repo-b", 2, created_at=now),
    ]
    resp = client.get("/history?repository=repo-b", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["repository"] == "repo-b"


def test_history_filters_by_status(client, auth_headers, fake_db):
    now = _now()
    fake_db["reviews"].docs = [
        _review_doc("1" * 24, "repo-a", 1, status="complete", created_at=now),
        _review_doc("2" * 24, "repo-a", 2, status="gemini_unavailable", created_at=now),
    ]
    resp = client.get("/history?status=complete", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["status"] == "complete"


def test_history_is_isolated_per_user(client, auth_headers, fake_db):
    now = _now()
    fake_db["reviews"].docs = [
        _review_doc("1" * 24, "repo-a", 1, user_id=99, created_at=now),
    ]
    resp = client.get("/history", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["items"] == []


def test_repository_metrics_empty(client, auth_headers, fake_db):
    resp = client.get("/dashboard/repositories", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["repositories"] == []
    assert data["total"] == 0


def test_repository_metrics_populated(client, auth_headers, fake_db):
    now = _now()
    fake_db["reviews"]._default_aggregate = [
        {
            "metadata": [{"total": 2}],
            "data": [
                {
                    "_id": {"owner": "octocat", "repository": "repo-a"},
                    "review_count": 2,
                    "finding_count": 5,
                    "critical_count": 1,
                    "high_count": 1,
                    "medium_count": 1,
                    "low_count": 2,
                    "info_count": 0,
                    "last_review_at": now,
                },
                {
                    "_id": {"owner": "octocat", "repository": "repo-b"},
                    "review_count": 1,
                    "finding_count": 0,
                    "critical_count": 0,
                    "high_count": 0,
                    "medium_count": 0,
                    "low_count": 0,
                    "info_count": 0,
                    "last_review_at": now - timedelta(days=2),
                },
            ],
        }
    ]

    resp = client.get("/dashboard/repositories", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert data["total_pages"] == 1
    repos = data["repositories"]
    assert len(repos) == 2
    assert repos[0]["repository"] == "repo-a"
    assert repos[0]["review_count"] == 2
    assert repos[0]["finding_count"] == 5
    assert repos[0]["average_findings_per_review"] == 2.5
    assert repos[1]["average_findings_per_review"] == 0.0


def test_feedback_summary_empty(client, auth_headers, fake_db):
    resp = client.get("/dashboard/feedback-summary", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_accepted"] == 0
    assert data["total_dismissed"] == 0
    assert data["total_feedback"] == 0
    assert data["acceptance_rate"] == 0.0
    for key, stats in data["category_feedback"].items():
        assert stats == {"accepted": 0, "dismissed": 0, "total": 0}
    for key, stats in data["severity_feedback"].items():
        assert stats == {"accepted": 0, "dismissed": 0, "total": 0}


def test_feedback_summary_populated(client, auth_headers, fake_db):
    fake_db["review_feedback"].docs = [
        {"user_id": 42, "action": "accepted", "category": "security", "severity": "high"},
        {"user_id": 42, "action": "accepted", "category": "security", "severity": "high"},
        {"user_id": 42, "action": "accepted", "category": "bug", "severity": "medium"},
        {"user_id": 42, "action": "dismissed", "category": "security", "severity": "low"},
    ]
    fake_db["review_feedback"].aggregate_results["$category"] = [
        {"_id": {"category": "security", "action": "accepted"}, "count": 2},
        {"_id": {"category": "security", "action": "dismissed"}, "count": 1},
        {"_id": {"category": "bug", "action": "accepted"}, "count": 1},
    ]
    fake_db["review_feedback"].aggregate_results["$severity"] = [
        {"_id": {"severity": "high", "action": "accepted"}, "count": 2},
        {"_id": {"severity": "medium", "action": "accepted"}, "count": 1},
        {"_id": {"severity": "low", "action": "dismissed"}, "count": 1},
    ]

    resp = client.get("/dashboard/feedback-summary", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_accepted"] == 3
    assert data["total_dismissed"] == 1
    assert data["total_feedback"] == 4
    assert data["acceptance_rate"] == 0.75
    assert data["category_feedback"]["security"] == {"accepted": 2, "dismissed": 1, "total": 3}
    assert data["category_feedback"]["bug"] == {"accepted": 1, "dismissed": 0, "total": 1}
    assert data["category_feedback"]["style"] == {"accepted": 0, "dismissed": 0, "total": 0}
    assert data["severity_feedback"]["high"] == {"accepted": 2, "dismissed": 0, "total": 2}
    assert data["severity_feedback"]["low"] == {"accepted": 0, "dismissed": 1, "total": 1}