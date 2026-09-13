"""Deterministic insight report generation over real, stored review data.

Scope
-----
Insights are computed exclusively from records already stored by the review
engine for the requesting user:

* ``reviews``  (owner/repository/pull_request_number, per-severity counts,
  ``created_at``)
* ``review_findings`` (severity, category, source, ``review_id``)
* ``review_feedback`` (action accepted/dismissed, category, severity)

No live GitHub data and no model inference is required for the deterministic
sections; the Gemini narrative is optional, additive decoration that only
interprets the metrics computed here. A report is rejected (422) rather than
fabricated when the repository (or pull request) has no review history.

Trend methodology
-----------------
A trend is the comparison of the first half versus the second half of the
chronological record sequence:

* ``findings_trend``      - per-review total finding counts
* ``critical_trend``      - per-review critical finding counts
* ``review_activity_trend`` - distinct calendar-day review counts
* ``feedback_activity_trend`` - distinct calendar-day feedback counts

For a sequence of length N the "earlier" half is indices [0, N // 2) and the
"later" half is [N // 2, N). Status is ``increasing`` when the later half sums
larger, ``decreasing`` when smaller, ``stable`` when equal, and
``insufficient`` when fewer than two comparable buckets exist (e.g. only one
review, or all activity on a single day) making a change over time meaningless.
No trend is ever extrapolated beyond observed data.

Risk methodology
----------------
Each risk is a deterministic boolean derived from the metrics and trends above
(see thresholds at module bottom). When a risk is not triggered its detail
states so; no probabilistic scoring is invented.

Recommendation methodology
--------------------------
Recommendations are produced by rule-based evaluation of the metrics and
triggered risks, ordered by priority (high, medium, low). They are deterministic
and reference only observed numbers.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from time import monotonic
from typing import Any

from app.schemas.insight import (
    InsightActivity,
    InsightFeedback,
    InsightMetrics,
    InsightRecommendation,
    InsightReport,
    InsightRisk,
    InsightTrend,
    InsightNarrative,
)
from app.services import gemini_service, insight_repository, review_repository
from app.services.config import settings
from app.services.gemini_service import GeminiUnavailable

logger = logging.getLogger(__name__)

SEVERITY_KEYS = ("critical", "high", "medium", "low", "info")
CATEGORY_KEYS = ("security", "bug", "performance", "complexity", "maintainability", "style")
FEEDBACK_ACTIONS = ("accepted", "dismissed")

CONCENTRATION_THRESHOLD = 0.5
MEDIUM_CONCENTRATION_THRESHOLD = 0.4
COMPLEXITY_MIN_FINDINGS = 5
FEEDBACK_MIN_VOLUME = 3
LOW_ACCEPTANCE_THRESHOLD = 0.5

RISK_DEFINITIONS = (
    {
        "key": "critical_findings_present",
        "label": "Critical findings present",
        "severity": "critical",
        "detail": "One or more critical-severity findings exist; these represent the highest-risk items and should be remediated first.",
        "untriggered_detail": "No critical-severity findings have been recorded.",
    },
    {
        "key": "high_critical_concentration",
        "label": "High/critical concentration",
        "severity": "critical",
        "detail": "High and critical findings dominate the finding mix and should drive the next remediation session.",
        "untriggered_detail": "High and critical findings are a minority of the recorded finding mix.",
    },
    {
        "key": "recurrent_security",
        "label": "Recurring security findings",
        "severity": "high",
        "detail": "Security findings appear in more than one review session, indicating a systemic risk area.",
        "untriggered_detail": "No security findings recur across review sessions.",
    },
    {
        "key": "critical_recurrence",
        "label": "Critical findings recur",
        "severity": "high",
        "detail": "Critical findings were observed across multiple review sessions; each should be tracked until resolved.",
        "untriggered_detail": "Critical findings were not observed across multiple review sessions.",
    },
    {
        "key": "recent_risk_deterioration",
        "label": "Recent risk deterioration",
        "severity": "medium",
        "detail": "The later half of the review history shows more findings than the earlier half, or more critical findings.",
        "untriggered_detail": "The later half of the review history shows no increase in findings or critical findings.",
    },
    {
        "key": "elevated_medium_concentration",
        "label": "Elevated medium-severity share",
        "severity": "low",
        "detail": "Medium-severity findings make up a large share of the finding mix; review them for systemic issues.",
        "untriggered_detail": "Medium-severity findings are not an outsized share of the finding mix.",
    },
    {
        "key": "complexity_burden",
        "label": "Complexity burden",
        "severity": "medium",
        "detail": "Complexity findings are frequent or recurring and may impede maintainability.",
        "untriggered_detail": "Complexity findings are neither frequent nor recurring.",
    },
    {
        "key": "low_feedback_acceptance",
        "label": "Low feedback acceptance",
        "severity": "low",
        "detail": "A large share of reviewed findings is dismissed; thresholds may need calibration to reduce noise.",
        "untriggered_detail": "Feedback acceptance is healthy or feedback volume is too low to evaluate.",
    },
)

TREND_ORDER = ("findings", "critical_findings", "review_activity", "feedback_activity")


class InsightGenerationError(Exception):
    """Raised when a report cannot be generated from real data (empty scope)."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_utc(value: datetime) -> datetime:
    """Normalize naive UTC timestamps (as PyMongo returns by default) to aware UTC.

    Stored records carry naive UTC ``created_at`` values, while the report code
    works with timezone-aware boundary timestamps. Coercing on read keeps every
    comparison, min/max and sort timezone-safe regardless of what the store
    produced.
    """
    if value is None:
        return _utcnow()
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _day_key(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def _month_key(dt: datetime) -> str:
    return dt.strftime("%Y-%m")


def _review_created_at(review: dict[str, Any]) -> datetime:
    return _coerce_utc(review.get("created_at"))


def _split_halves(sequence: list[int]) -> tuple[int, int]:
    mid = len(sequence) // 2
    return sum(sequence[:mid]), sum(sequence[mid:])


def _trend_status(earlier: int, later: int) -> str:
    if later > earlier:
        return "increasing"
    if later < earlier:
        return "decreasing"
    return "stable"


def _compute_trend(metric: str, sequence: list[int], note_insufficient: str) -> dict[str, Any]:
    if len(sequence) < 2:
        return {
            "metric": metric,
            "status": "insufficient",
            "earlier": 0,
            "later": 0,
            "note": note_insufficient,
        }
    earlier, later = _split_halves(sequence)
    return {
        "metric": metric,
        "status": _trend_status(earlier, later),
        "earlier": earlier,
        "later": later,
        "note": None,
    }


async def _load_scope(
    user_id: int,
    owner: str,
    repository: str,
    pull_request: int | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    reviews = await review_repository.list_reviews_for_scope(
        user_id,
        owner,
        repository,
        pull_request,
    )
    if not reviews:
        raise InsightGenerationError(_no_data_message(owner, repository, pull_request))
    review_ids = [str(review["_id"]) for review in reviews]
    findings = await review_repository.list_findings_for_reviews(review_ids)
    feedback = await review_repository.list_feedback_for_scope(user_id, owner, repository, pull_request)
    return reviews, findings, feedback


def _no_data_message(owner: str, repository: str, pull_request: int | None) -> str:
    if pull_request is not None:
        return f"No review history available for pull request #{pull_request} in {owner}/{repository} yet."
    return f"No review history available for repository {owner}/{repository} yet."


def compute_metrics(reviews: list[dict[str, Any]], findings: list[dict[str, Any]]) -> dict[str, Any]:
    severity = {key: 0 for key in SEVERITY_KEYS}
    categories = {key: 0 for key in CATEGORY_KEYS}
    sources: dict[str, int] = {}
    category_reviews: dict[str, set[str]] = {key: set() for key in CATEGORY_KEYS}

    for finding in findings:
        severity_value = finding.get("severity")
        if severity_value in severity:
            severity[severity_value] += 1
        category_value = finding.get("category")
        if category_value in categories:
            categories[category_value] += 1
        source_value = finding.get("source")
        if source_value:
            sources[source_value] = sources.get(source_value, 0) + 1
        review_id = str(finding.get("review_id") or "")
        if category_value in category_reviews and review_id:
            category_reviews[category_value].add(review_id)

    total_findings = len(findings)
    review_count = len(reviews)
    average_findings = round(total_findings / review_count, 2) if review_count else 0.0

    active_days = len({_day_key(_review_created_at(review)) for review in reviews})
    finding_frequency = round(total_findings / active_days, 2) if active_days else 0.0

    recurring = sorted(
        [
            key
            for key, review_ids in category_reviews.items()
            if len(review_ids) >= 2
        ],
        key=lambda key: (-len(category_reviews[key]), key),
    )

    return {
        "severity_distribution": severity,
        "category_distribution": categories,
        "finding_source_distribution": sources,
        "total_findings": total_findings,
        "critical_findings": severity["critical"],
        "high_findings": severity["high"],
        "medium_findings": severity["medium"],
        "low_findings": severity["low"],
        "info_findings": severity["info"],
        "security_findings": categories["security"],
        "complexity_findings": categories["complexity"],
        "average_findings_per_review": average_findings,
        "finding_frequency": finding_frequency,
        "recurring_categories": recurring,
    }


def compute_activity(
    reviews: list[dict[str, Any]],
    total_findings: int,
) -> dict[str, Any]:
    created_ats = [_review_created_at(review) for review in reviews]
    first_review_at = min(created_ats)
    latest_review_at = max(created_ats)
    review_count = len(reviews)

    week_start = _utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = week_start - timedelta(days=week_start.weekday())
    reviews_this_week = sum(1 for created_at in created_ats if created_at >= week_start)

    active_days = len({_day_key(created_at) for created_at in created_ats})
    findings_per_active_day = round(total_findings / active_days, 2) if active_days else 0.0

    distinct_prs = {
        review.get("pull_request_number")
        for review in reviews
        if isinstance(review.get("pull_request_number"), int) and review.get("pull_request_number") > 0
    }

    review_totals_by_review = {str(review["_id"]): (review.get("total_finding_count") or 0) for review in reviews}

    period_map: dict[str, dict[str, int]] = {}
    for created_at in created_ats:
        key = _month_key(created_at)
        period = period_map.setdefault(key, {"reviews": 0, "findings": 0})
        period["reviews"] += 1
    for review in reviews:
        key = _month_key(_review_created_at(review))
        period_map[key]["findings"] += review_totals_by_review.get(str(review["_id"]), 0)

    reviews_over_time = [
        {"period": key, "reviews": period["reviews"], "findings": period["findings"]}
        for key, period in sorted(period_map.items())
    ]

    return {
        "review_count": review_count,
        "pull_request_count": len(distinct_prs),
        "reviews_this_week": reviews_this_week,
        "first_review_at": first_review_at,
        "latest_review_at": latest_review_at,
        "average_findings_per_review": round(total_findings / review_count, 2) if review_count else 0.0,
        "findings_per_active_day": findings_per_active_day,
        "reviews_over_time": reviews_over_time,
    }


def compute_feedback(feedback: list[dict[str, Any]]) -> dict[str, Any]:
    total_accepted = sum(1 for item in feedback if item.get("action") == "accepted")
    total_dismissed = sum(1 for item in feedback if item.get("action") == "dismissed")
    total_feedback = total_accepted + total_dismissed

    category_feedback = {
        key: {"accepted": 0, "dismissed": 0, "total": 0} for key in CATEGORY_KEYS
    }
    severity_feedback = {key: {"accepted": 0, "dismissed": 0, "total": 0} for key in SEVERITY_KEYS}
    for item in feedback:
        action = item.get("action")
        if action not in FEEDBACK_ACTIONS:
            continue
        category = item.get("category")
        if category in category_feedback:
            category_feedback[category][action] += 1
            category_feedback[category]["total"] += 1
        severity = item.get("severity")
        if severity in severity_feedback:
            severity_feedback[severity][action] += 1
            severity_feedback[severity]["total"] += 1

    return {
        "total_accepted": total_accepted,
        "total_dismissed": total_dismissed,
        "total_feedback": total_feedback,
        "acceptance_rate": round(total_accepted / total_feedback, 2) if total_feedback else 0.0,
        "category_feedback": category_feedback,
        "severity_feedback": severity_feedback,
    }


def compute_trends(
    reviews: list[dict[str, Any]],
    feedback: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    findings_sequence = [review.get("total_finding_count") or 0 for review in reviews]
    critical_sequence = [review.get("critical_count") or 0 for review in reviews]

    review_days: dict[str, int] = {}
    for review in reviews:
        key = _day_key(_review_created_at(review))
        review_days[key] = review_days.get(key, 0) + 1

    feedback_days: dict[str, int] = {}
    for item in feedback:
        created_at = _coerce_utc(item.get("created_at"))
        key = _day_key(created_at)
        feedback_days[key] = feedback_days.get(key, 0) + 1

    return [
        _compute_trend(
            "findings",
            findings_sequence,
            "Insufficient review history to compare findings over time.",
        ),
        _compute_trend(
            "critical_findings",
            critical_sequence,
            "Insufficient review history to compare critical findings over time.",
        ),
        _compute_trend(
            "review_activity",
            [review_days[key] for key in sorted(review_days)],
            "Reviews occurred on a single day; not enough activity history to compare.",
        ),
        _compute_trend(
            "feedback_activity",
            [feedback_days[key] for key in sorted(feedback_days)],
            "Feedback is absent or occurred on a single day; not enough history to compare.",
        ),
    ]


def compute_risks(
    metrics: dict[str, Any],
    trends: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    feedback_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    total = metrics["total_findings"]
    high_critical = metrics["high_findings"] + metrics["critical_findings"]
    medium = metrics["medium_findings"]
    recurs = set(metrics["recurring_categories"])

    findings_trend = next((trend for trend in trends if trend["metric"] == "findings"), {})
    critical_trend = next((trend for trend in trends if trend["metric"] == "critical_findings"), {})
    recent_deterioration = (
        findings_trend.get("status") == "increasing"
        or critical_trend.get("status") == "increasing"
    )

    critical_reviews = {
        finding.get("review_id")
        for finding in findings
        if finding.get("severity") == "critical" and finding.get("review_id")
    }

    triggered = {
        "critical_findings_present": metrics["critical_findings"] > 0,
        "high_critical_concentration": total > 0 and (high_critical / total) >= CONCENTRATION_THRESHOLD,
        "recurrent_security": "security" in recurs,
        "critical_recurrence": len(critical_reviews) >= 2,
        "recent_risk_deterioration": recent_deterioration,
        "elevated_medium_concentration": total > 0 and (medium / total) >= MEDIUM_CONCENTRATION_THRESHOLD,
        "complexity_burden": metrics["complexity_findings"] >= COMPLEXITY_MIN_FINDINGS or "complexity" in recurs,
        "low_feedback_acceptance": (
            feedback_summary["total_feedback"] >= FEEDBACK_MIN_VOLUME
            and feedback_summary["acceptance_rate"] < LOW_ACCEPTANCE_THRESHOLD
        ),
    }

    risks: list[dict[str, Any]] = []
    for definition in RISK_DEFINITIONS:
        key = definition["key"]
        risks.append(
            {
                "key": key,
                "label": definition["label"],
                "severity": definition["severity"],
                "triggered": triggered.get(key, False),
                "detail": (
                    definition["detail"]
                    if triggered.get(key)
                    else definition["untriggered_detail"]
                ),
            }
        )
    return risks


def compute_recommendations(
    metrics: dict[str, Any],
    risks: list[dict[str, Any]],
    trends: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    risk_map = {risk["key"]: risk for risk in risks}
    total = metrics["total_findings"]
    high_critical = metrics["high_findings"] + metrics["critical_findings"]
    concentration_pct = round(high_critical / total * 100, 1) if total else 0.0
    findings_trend = next((trend for trend in trends if trend["metric"] == "findings"), {})

    recommendations: list[dict[str, Any]] = []

    if metrics["critical_findings"]:
        recommendations.append(
            {
                "priority": "high",
                "message": f"Investigate and remediate the {metrics['critical_findings']} critical finding(s) first; they carry the highest risk.",
                "basis": f"critical_findings={metrics['critical_findings']}",
            }
        )
    if risk_map["high_critical_concentration"]["triggered"]:
        recommendations.append(
            {
                "priority": "high",
                "message": f"High/critical findings dominate this repository ({concentration_pct}% of recorded findings); schedule a focused remediation session.",
                "basis": f"high_plus_critical={high_critical} of total={total}",
            }
        )
    if risk_map["recurrent_security"]["triggered"]:
        recommendations.append(
            {
                "priority": "high",
                "message": "Security findings recur across review sessions; add regression checks and dependency scanning.",
                "basis": "recurrent_categories includes security",
            }
        )
    if risk_map["critical_recurrence"]["triggered"]:
        recommendations.append(
            {
                "priority": "high",
                "message": "Critical findings were observed in more than one review session; track each to closure.",
                "basis": "critical findings across multiple reviews",
            }
        )
    if risk_map["recent_risk_deterioration"]["triggered"]:
        recommendations.append(
            {
                "priority": "medium",
                "message": "The later half of the review history shows more findings than the earlier half; investigate what changed to reverse the trend.",
                "basis": "findings_trend or critical_trend = increasing",
            }
        )
    if risk_map["complexity_burden"]["triggered"]:
        recommendations.append(
            {
                "priority": "medium",
                "message": "Complexity findings are frequent or recurring; prioritize refactoring the affected modules.",
                "basis": f"complexity_findings={metrics['complexity_findings']}",
            }
        )
    if risk_map["elevated_medium_concentration"]["triggered"]:
        recommendations.append(
            {
                "priority": "medium",
                "message": "Medium-severity findings make up a large share of the mix; review them for systemic issues.",
                "basis": f"medium={metrics['medium_findings']} of total={total}",
            }
        )
    if risk_map["low_feedback_acceptance"]["triggered"]:
        recommendations.append(
            {
                "priority": "low",
                "message": "A large share of reviewed findings is dismissed; calibrate thresholds to reduce noise.",
                "basis": "acceptance rate below 50% with sufficient feedback volume",
            }
        )
    if findings_trend.get("status") == "insufficient":
        recommendations.append(
            {
                "priority": "low",
                "message": "Establish a regular review cadence to build the historical baseline needed for trend analysis.",
                "basis": "findings_trend = insufficient",
            }
        )
    if not recommendations:
        if total == 0:
            recommendations.append(
                {
                    "priority": "low",
                    "message": "No findings recorded yet; run your first review to establish a baseline.",
                    "basis": "total_findings=0",
                }
            )
        else:
            recommendations.append(
                {
                    "priority": "low",
                    "message": "No immediate high-risk signals; keep the current review cadence to maintain this posture.",
                    "basis": "no triggered high/medium risks",
                }
            )

    order = {"high": 0, "medium": 1, "low": 2}
    recommendations.sort(key=lambda rec: order[rec["priority"]])
    return recommendations


def _narrative_context(
    repository: str,
    metrics: dict[str, Any],
    activity: dict[str, Any],
    feedback: dict[str, Any],
    trends: list[dict[str, Any]],
    risks: list[dict[str, Any]],
) -> dict[str, Any]:
    def _iso(value: datetime | None) -> str | None:
        return value.isoformat() if value else None

    return {
        "repository": repository,
        "metrics": {
            "total_findings": metrics["total_findings"],
            "critical_findings": metrics["critical_findings"],
            "high_findings": metrics["high_findings"],
            "medium_findings": metrics["medium_findings"],
            "low_findings": metrics["low_findings"],
            "info_findings": metrics["info_findings"],
            "severity_distribution": metrics["severity_distribution"],
            "category_distribution": metrics["category_distribution"],
            "recurring_categories": metrics["recurring_categories"],
            "average_findings_per_review": metrics["average_findings_per_review"],
            "finding_frequency": metrics["finding_frequency"],
        },
        "activity": {
            "review_count": activity["review_count"],
            "pull_request_count": activity["pull_request_count"],
            "reviews_this_week": activity["reviews_this_week"],
            "first_review_at": _iso(activity["first_review_at"]),
            "latest_review_at": _iso(activity["latest_review_at"]),
        },
        "feedback": {
            "total_accepted": feedback["total_accepted"],
            "total_dismissed": feedback["total_dismissed"],
            "total_feedback": feedback["total_feedback"],
            "acceptance_rate": feedback["acceptance_rate"],
        },
        "trends": [
            {
                "metric": trend["metric"],
                "status": trend["status"],
                "earlier": trend["earlier"],
                "later": trend["later"],
            }
            for trend in trends
        ],
        "risks": [
            {
                "key": risk["key"],
                "label": risk["label"],
                "severity": risk["severity"],
                "triggered": risk["triggered"],
            }
            for risk in risks
        ],
    }


def _to_insight_response(doc: dict[str, Any]) -> InsightReport:
    return InsightReport(
        id=str(doc.get("_id")),
        report_type=doc.get("report_type") or "repository",
        owner=doc.get("owner") or "",
        repository=doc.get("repository") or "",
        pull_request=doc.get("pull_request"),
        source_review_ids=doc.get("source_review_ids") or [],
        metrics=InsightMetrics(**doc.get("metrics") or {}),
        activity=InsightActivity(**doc.get("activity") or {}),
        feedback=InsightFeedback(**doc.get("feedback") or {}),
        trends=[InsightTrend(**trend) for trend in (doc.get("trends") or [])],
        risks=[InsightRisk(**risk) for risk in (doc.get("risks") or [])],
        recommendations=[
            InsightRecommendation(**rec) for rec in (doc.get("recommendations") or [])
        ],
        narrative=(
            InsightNarrative(**(doc.get("narrative") or {}))
            if doc.get("narrative")
            else None
        ),
        model=doc.get("model"),
        status=doc.get("status") or "complete",
        error=doc.get("error"),
        duration_ms=doc.get("duration_ms") or 0,
        generated_at=doc.get("created_at"),
    )


async def generate_insight(
    *,
    user_id: int,
    owner: str,
    repository: str,
    pull_request: int | None = None,
    generate_narrative: bool = True,
) -> InsightReport:
    started = monotonic()

    reviews, findings, feedback = await _load_scope(user_id, owner, repository, pull_request)
    review_ids = [str(review["_id"]) for review in reviews]

    metrics = compute_metrics(reviews, findings)
    activity = compute_activity(reviews, metrics["total_findings"])
    feedback_summary = compute_feedback(feedback)
    trends = compute_trends(reviews, feedback)
    risks = compute_risks(metrics, trends, findings, feedback_summary)
    recommendations = compute_recommendations(metrics, risks, trends)

    narrative = None
    model = None
    if generate_narrative:
        try:
            narrative_model = await gemini_service.generate_insights_narrative(
                _narrative_context(
                    repository,
                    metrics,
                    activity,
                    feedback_summary,
                    trends,
                    risks,
                )
            )
            narrative = narrative_model.model_dump()
            model = settings.GEMINI_MODEL
        except GeminiUnavailable:
            logger.warning(
                "Gemini narrative unavailable for insight on %s/%s; returning rules-based report",
                owner,
                repository,
            )
            narrative = None
            model = None

    doc = {
        "user_id": user_id,
        "report_type": "pull_request" if pull_request is not None else "repository",
        "owner": owner,
        "repository": repository,
        "pull_request": pull_request,
        "source_review_ids": review_ids,
        "metrics": metrics,
        "activity": activity,
        "feedback": feedback_summary,
        "trends": trends,
        "risks": risks,
        "recommendations": recommendations,
        "narrative": narrative,
        "model": model,
        "status": "complete",
        "error": None,
        "duration_ms": int((monotonic() - started) * 1000),
        "created_at": _utcnow(),
        "updated_at": _utcnow(),
    }
    insight_id = await insight_repository.save_insight(doc)
    doc["_id"] = insight_id
    return _to_insight_response(doc)


async def get_insight_report(insight_id: str, user_id: int) -> InsightReport | None:
    doc = await insight_repository.get_insight(insight_id, user_id)
    return _to_insight_response(doc) if doc else None


async def get_latest_report(
    user_id: int,
    owner: str,
    repository: str,
    pull_request: int | None = None,
    report_type: str | None = None,
) -> InsightReport | None:
    doc = await insight_repository.get_latest_insight(
        user_id,
        owner,
        repository,
        pull_request=pull_request,
        report_type=report_type,
    )
    return _to_insight_response(doc) if doc else None


async def list_reports(
    user_id: int,
    *,
    page: int = 1,
    per_page: int = 20,
    repository: str | None = None,
    report_type: str | None = None,
) -> dict[str, Any]:
    data = await insight_repository.list_insights(
        user_id,
        page=page,
        per_page=per_page,
        repository=repository,
        report_type=report_type,
    )
    total_pages = (data["total"] + per_page - 1) // per_page if data["total"] else 0
    return {
        "items": [_to_insight_response(doc) for doc in data["items"]],
        "page": data["page"],
        "per_page": data["per_page"],
        "total": data["total"],
        "total_pages": total_pages,
    }


to_insight_response = _to_insight_response