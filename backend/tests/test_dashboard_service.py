from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from app.services import dashboard_service
from app.services.dashboard_service import (
    _period_starts,
    _total_pages,
    _to_history_item,
    _to_repo_metric,
)

NOW = datetime(2026, 9, 9, 14, 30, 0, tzinfo=timezone.utc)  # Wednesday


def test_total_pages_zero_when_no_rows():
    assert _total_pages(0, 20) == 0


def test_total_pages_rounds_up():
    assert _total_pages(5, 2) == 3
    assert _total_pages(20, 20) == 1
    assert _total_pages(21, 20) == 2


def test_period_starts_mid_week():
    day, week, month = _period_starts(NOW)
    assert day == datetime(2026, 9, 9, 0, 0, 0, tzinfo=timezone.utc)
    assert week == datetime(2026, 9, 7, 0, 0, 0, tzinfo=timezone.utc)  # Monday
    assert month == datetime(2026, 9, 1, 0, 0, 0, tzinfo=timezone.utc)


def test_period_starts_sunday_starts_on_monday():
    sunday = datetime(2026, 9, 13, 9, 0, 0, tzinfo=timezone.utc)
    day, week, month = _period_starts(sunday)
    assert week == datetime(2026, 9, 7, 0, 0, 0, tzinfo=timezone.utc)


def test_to_history_item_fills_missing_fields():
    item = _to_history_item({"owner": "o", "repository": "r", "pull_request_number": 1})
    assert item["status"] == "unknown"
    assert item["total_finding_count"] == 0
    assert item["critical_count"] == 0
    assert item["commit_sha"] is None


def test_to_repo_metric_average_handles_zero_reviews():
    metric = _to_repo_metric(
        {
            "_id": {"owner": "o", "repository": "r"},
            "review_count": 0,
            "finding_count": 0,
        }
    )
    assert metric["average_findings_per_review"] == 0.0


def test_to_repo_metric_average_rounds():
    metric = _to_repo_metric(
        {
            "_id": {"owner": "o", "repository": "r"},
            "review_count": 3,
            "finding_count": 10,
        }
    )
    assert metric["average_findings_per_review"] == 3.33


@pytest.mark.asyncio
async def test_get_dashboard_uses_fixed_now_periods(monkeypatch):
    captured = []

    async def fake_count(user_id):
        return 0

    async def fake_count_since(user_id, since):
        captured.append(since)
        return 0

    async def fake_aggregate(user_id):
        return []

    async def fake_recent(user_id, limit=10):
        return []

    monkeypatch.setattr("app.services.review_repository.count_reviews", fake_count)
    monkeypatch.setattr("app.services.review_repository.count_reviews_since", fake_count_since)
    monkeypatch.setattr("app.services.review_repository.aggregate_findings_by_severity", fake_aggregate)
    monkeypatch.setattr("app.services.review_repository.aggregate_findings_by_category", fake_aggregate)
    monkeypatch.setattr("app.services.review_repository.list_recent_reviews", fake_recent)

    result = await dashboard_service.get_dashboard(42, now=NOW)
    day, week, month = _period_starts(NOW)
    assert captured == [day, week, month]
    assert result["reviews_this_week"] == 0
    assert result["total_reviews"] == 0


@pytest.mark.asyncio
async def test_submit_feedback_rejects_invalid_action():
    with pytest.raises(HTTPException) as excinfo:
        await dashboard_service.submit_feedback(42, "o", "r", 1, "g-1", "maybe")
    assert excinfo.value.status_code == 422


@pytest.mark.asyncio
async def test_submit_feedback_review_not_found(monkeypatch):
    async def no_review(user_id, owner, repository, number):
        return None

    monkeypatch.setattr("app.services.review_repository.find_review_for_user", no_review)
    with pytest.raises(HTTPException) as excinfo:
        await dashboard_service.submit_feedback(42, "o", "r", 1, "g-1", "accepted")
    assert excinfo.value.status_code == 404


@pytest.mark.asyncio
async def test_get_history_total_pages(monkeypatch):
    rows = [{"owner": "o", "repository": "r", "pull_request_number": i} for i in range(3)]

    async def fake_list(user_id, page=1, per_page=20, repository=None, status=None):
        start = (page - 1) * per_page
        return {
            "reviews": rows[start : start + per_page],
            "total": 3,
            "page": page,
            "per_page": per_page,
        }

    monkeypatch.setattr("app.services.review_repository.list_reviews_by_user", fake_list)
    result = await dashboard_service.get_history(42, page=2, per_page=2)
    assert result["total"] == 3
    assert result["total_pages"] == 2
    assert len(result["items"]) == 1


@pytest.mark.asyncio
async def test_get_repository_metrics_returns_shape(monkeypatch):
    async def fake_metrics(user_id, page=1, per_page=20):
        return {
            "repositories": [],
            "total": 0,
            "page": 1,
            "per_page": 20,
        }

    monkeypatch.setattr("app.services.review_repository.aggregate_repository_metrics", fake_metrics)
    result = await dashboard_service.get_repository_metrics(42)
    assert result["repositories"] == []
    assert result["total"] == 0