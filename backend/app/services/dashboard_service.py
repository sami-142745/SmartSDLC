from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException

from app.services import review_repository

SEVERITY_KEYS = ("critical", "high", "medium", "low", "info")
CATEGORY_KEYS = ("security", "bug", "performance", "complexity", "maintainability", "style")
FEEDBACK_ACTIONS = ("accepted", "dismissed")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _period_starts(now: datetime | None = None) -> tuple[datetime, datetime, datetime]:
    now = now or _utcnow()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = day_start - timedelta(days=day_start.weekday())
    month_start = day_start.replace(day=1)
    return day_start, week_start, month_start


def _total_pages(total: int, per_page: int) -> int:
    if not total or per_page <= 0:
        return 0
    return math.ceil(total / per_page)


def _zero_distribution(keys: tuple[str, ...]) -> dict[str, int]:
    return {key: 0 for key in keys}


def _fill_distribution(keys: tuple[str, ...], rows: list[dict[str, Any]]) -> dict[str, int]:
    distribution = _zero_distribution(keys)
    for row in rows:
        key = row.get("_id")
        if key in distribution:
            distribution[key] += row.get("count", 0)
    return distribution


def _to_history_item(review: dict[str, Any]) -> dict[str, Any]:
    return {
        "owner": review.get("owner"),
        "repository": review.get("repository"),
        "pull_request_number": review.get("pull_request_number"),
        "pull_request_title": review.get("pull_request_title"),
        "status": review.get("status", "unknown"),
        "commit_sha": review.get("commit_sha"),
        "total_finding_count": review.get("total_finding_count") or 0,
        "critical_count": review.get("critical_count") or 0,
        "high_count": review.get("high_count") or 0,
        "medium_count": review.get("medium_count") or 0,
        "low_count": review.get("low_count") or 0,
        "info_count": review.get("info_count") or 0,
        "review_score": review.get("review_score"),
        "review_severity": review.get("review_severity"),
        "created_at": review.get("created_at"),
        "updated_at": review.get("updated_at"),
    }


def _to_repo_metric(metric: dict[str, Any]) -> dict[str, Any]:
    group_id = metric.get("_id") or {}
    review_count = metric.get("review_count") or 0
    finding_count = metric.get("finding_count") or 0
    return {
        "owner": group_id.get("owner"),
        "repository": group_id.get("repository"),
        "review_count": review_count,
        "finding_count": finding_count,
        "critical_count": metric.get("critical_count") or 0,
        "high_count": metric.get("high_count") or 0,
        "medium_count": metric.get("medium_count") or 0,
        "low_count": metric.get("low_count") or 0,
        "info_count": metric.get("info_count") or 0,
        "average_findings_per_review": round(finding_count / review_count, 2) if review_count else 0.0,
        "last_review_at": metric.get("last_review_at"),
    }


def _to_feedback_item(feedback: dict[str, Any]) -> dict[str, Any]:
    return {
        "review_id": str(feedback.get("review_id") or ""),
        "finding_id": feedback.get("finding_id"),
        "owner": feedback.get("owner"),
        "repository": feedback.get("repository"),
        "pull_request_number": feedback.get("pull_request_number"),
        "action": feedback.get("action"),
        "category": feedback.get("category"),
        "severity": feedback.get("severity"),
        "created_at": feedback.get("created_at"),
        "updated_at": feedback.get("updated_at"),
    }


async def get_dashboard(user_id: int, now: datetime | None = None) -> dict[str, Any]:
    day_start, week_start, month_start = _period_starts(now)
    total_reviews = await review_repository.count_reviews(user_id)
    severity_rows = await review_repository.aggregate_findings_by_severity(user_id)
    category_rows = await review_repository.aggregate_findings_by_category(user_id)
    reviews_today = await review_repository.count_reviews_since(user_id, day_start)
    reviews_this_week = await review_repository.count_reviews_since(user_id, week_start)
    reviews_this_month = await review_repository.count_reviews_since(user_id, month_start)
    recent_reviews = await review_repository.list_recent_reviews(user_id, limit=10)

    severity_distribution = _fill_distribution(SEVERITY_KEYS, severity_rows)
    category_distribution = _fill_distribution(CATEGORY_KEYS, category_rows)
    total_findings = sum(severity_distribution.values())

    return {
        "total_reviews": total_reviews,
        "total_findings": total_findings,
        "critical_findings": severity_distribution["critical"],
        "high_findings": severity_distribution["high"],
        "medium_findings": severity_distribution["medium"],
        "low_findings": severity_distribution["low"],
        "info_findings": severity_distribution["info"],
        "reviews_today": reviews_today,
        "reviews_this_week": reviews_this_week,
        "reviews_this_month": reviews_this_month,
        "average_findings_per_review": round(total_findings / total_reviews, 2) if total_reviews else 0.0,
        "recent_reviews": [_to_history_item(review) for review in recent_reviews],
        "severity_distribution": severity_distribution,
        "category_distribution": category_distribution,
    }


async def get_history(
    user_id: int,
    *,
    page: int = 1,
    per_page: int = 20,
    repository: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    data = await review_repository.list_reviews_by_user(
        user_id=user_id,
        page=page,
        per_page=per_page,
        repository=repository,
        status=status,
    )
    return {
        "items": [_to_history_item(review) for review in data["reviews"]],
        "page": data["page"],
        "per_page": data["per_page"],
        "total": data["total"],
        "total_pages": _total_pages(data["total"], data["per_page"]),
    }


async def get_repository_metrics(
    user_id: int,
    *,
    page: int = 1,
    per_page: int = 20,
) -> dict[str, Any]:
    data = await review_repository.aggregate_repository_metrics(
        user_id=user_id,
        page=page,
        per_page=per_page,
    )
    return {
        "repositories": [_to_repo_metric(metric) for metric in data["repositories"]],
        "page": data["page"],
        "per_page": data["per_page"],
        "total": data["total"],
        "total_pages": _total_pages(data["total"], data["per_page"]),
    }


async def submit_feedback(
    user_id: int,
    owner: str,
    repository: str,
    pull_request_number: int,
    finding_id: str,
    action: str,
) -> dict[str, Any]:
    if action not in FEEDBACK_ACTIONS:
        raise HTTPException(status_code=422, detail="Invalid feedback action")
    review = await review_repository.find_review_for_user(
        user_id, owner, repository, pull_request_number
    )
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    review_id = str(review["_id"])
    finding = await review_repository.find_finding(review_id, finding_id)
    if finding is None:
        raise HTTPException(status_code=404, detail="Finding not found")
    feedback = await review_repository.save_feedback(
        review_id=review_id,
        finding_id=finding_id,
        user_id=user_id,
        action=action,
        category=finding.get("category"),
        severity=finding.get("severity"),
        owner=owner,
        repository=repository,
        pull_request_number=pull_request_number,
    )
    return _to_feedback_item(feedback)


async def get_feedback_history(
    user_id: int,
    *,
    page: int = 1,
    per_page: int = 20,
) -> dict[str, Any]:
    data = await review_repository.list_feedback_for_user(
        user_id=user_id,
        page=page,
        per_page=per_page,
    )
    return {
        "items": [_to_feedback_item(item) for item in data["items"]],
        "page": data["page"],
        "per_page": data["per_page"],
        "total": data["total"],
        "total_pages": _total_pages(data["total"], data["per_page"]),
    }


async def get_feedback_summary(user_id: int) -> dict[str, Any]:
    total_accepted = await review_repository.count_feedback(user_id, "accepted")
    total_dismissed = await review_repository.count_feedback(user_id, "dismissed")
    total_feedback = total_accepted + total_dismissed

    category_rows = await review_repository.aggregate_feedback_by_category(user_id)
    severity_rows = await review_repository.aggregate_feedback_by_severity(user_id)

    category_feedback: dict[str, dict[str, int]] = {
        key: {"accepted": 0, "dismissed": 0, "total": 0} for key in CATEGORY_KEYS
    }
    for row in category_rows:
        group_id = row.get("_id") or {}
        key = group_id.get("category")
        action = group_id.get("action")
        if key in category_feedback and action in FEEDBACK_ACTIONS:
            category_feedback[key][action] += row.get("count", 0)
            category_feedback[key]["total"] += row.get("count", 0)

    severity_feedback: dict[str, dict[str, int]] = {
        key: {"accepted": 0, "dismissed": 0, "total": 0} for key in SEVERITY_KEYS
    }
    for row in severity_rows:
        group_id = row.get("_id") or {}
        key = group_id.get("severity")
        action = group_id.get("action")
        if key in severity_feedback and action in FEEDBACK_ACTIONS:
            severity_feedback[key][action] += row.get("count", 0)
            severity_feedback[key]["total"] += row.get("count", 0)

    return {
        "total_accepted": total_accepted,
        "total_dismissed": total_dismissed,
        "total_feedback": total_feedback,
        "acceptance_rate": round(total_accepted / total_feedback, 2) if total_feedback else 0.0,
        "category_feedback": category_feedback,
        "severity_feedback": severity_feedback,
    }