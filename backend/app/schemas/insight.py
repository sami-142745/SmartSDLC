from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

InsightReportType = Literal["repository", "pull_request"]
TrendStatus = Literal["increasing", "decreasing", "stable", "insufficient"]
RiskSeverity = Literal["critical", "high", "medium", "low"]


class TrendPoint(BaseModel):
    period: str
    reviews: int = 0
    findings: int = 0


class InsightTrend(BaseModel):
    metric: str
    status: TrendStatus = "insufficient"
    earlier: int = 0
    later: int = 0
    note: str | None = None


class InsightRisk(BaseModel):
    key: str
    label: str
    severity: RiskSeverity
    triggered: bool = False
    detail: str


class InsightRecommendation(BaseModel):
    priority: Literal["high", "medium", "low"]
    message: str
    basis: str


class InsightNarrative(BaseModel):
    executive_summary: str | None = None
    trend_interpretation: str | None = None
    risk_explanation: str | None = None
    recommendations: list[str] = Field(default_factory=list)
    model: str | None = None


class InsightMetrics(BaseModel):
    severity_distribution: dict[str, int] = Field(default_factory=dict)
    category_distribution: dict[str, int] = Field(default_factory=dict)
    finding_source_distribution: dict[str, int] = Field(default_factory=dict)
    total_findings: int = 0
    critical_findings: int = 0
    high_findings: int = 0
    medium_findings: int = 0
    low_findings: int = 0
    info_findings: int = 0
    security_findings: int = 0
    complexity_findings: int = 0
    average_findings_per_review: float = 0.0
    finding_frequency: float = 0.0
    recurring_categories: list[str] = Field(default_factory=list)


class InsightActivity(BaseModel):
    review_count: int = 0
    pull_request_count: int = 0
    reviews_this_week: int = 0
    first_review_at: datetime | None = None
    latest_review_at: datetime | None = None
    average_findings_per_review: float = 0.0
    findings_per_active_day: float = 0.0
    reviews_over_time: list[TrendPoint] = Field(default_factory=list)


class FeedbackActionStats(BaseModel):
    accepted: int = 0
    dismissed: int = 0
    total: int = 0


class InsightFeedback(BaseModel):
    total_accepted: int = 0
    total_dismissed: int = 0
    total_feedback: int = 0
    acceptance_rate: float = 0.0
    category_feedback: dict[str, FeedbackActionStats] = Field(default_factory=dict)
    severity_feedback: dict[str, FeedbackActionStats] = Field(default_factory=dict)


class InsightReport(BaseModel):
    id: str
    report_type: InsightReportType = "repository"
    owner: str
    repository: str
    pull_request: int | None = None
    source_review_ids: list[str] = Field(default_factory=list)
    metrics: InsightMetrics
    activity: InsightActivity
    feedback: InsightFeedback
    trends: list[InsightTrend] = Field(default_factory=list)
    risks: list[InsightRisk] = Field(default_factory=list)
    recommendations: list[InsightRecommendation] = Field(default_factory=list)
    narrative: InsightNarrative | None = None
    model: str | None = None
    status: str = "complete"
    error: str | None = None
    duration_ms: int = 0
    generated_at: datetime | None = None


class InsightListResponse(BaseModel):
    items: list[InsightReport] = Field(default_factory=list)
    page: int = 1
    per_page: int = 20
    total: int = 0
    total_pages: int = 0


class GenerateInsightRequest(BaseModel):
    owner: str = Field(min_length=1)
    repository: str = Field(min_length=1)
    pull_request: int | None = Field(default=None, ge=1)
    generate_narrative: bool = True