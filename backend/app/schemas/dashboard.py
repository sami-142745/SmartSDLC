from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class RecentReview(BaseModel):
    owner: str
    repository: str
    pull_request_number: int
    pull_request_title: str | None = None
    status: str
    total_finding_count: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    info_count: int = 0
    review_score: float | None = None
    review_severity: str | None = None
    created_at: datetime | None = None


class DashboardSummary(BaseModel):
    total_reviews: int = 0
    total_findings: int = 0
    critical_findings: int = 0
    high_findings: int = 0
    medium_findings: int = 0
    low_findings: int = 0
    info_findings: int = 0
    reviews_today: int = 0
    reviews_this_week: int = 0
    reviews_this_month: int = 0
    average_findings_per_review: float = 0.0
    recent_reviews: list[RecentReview] = Field(default_factory=list)
    severity_distribution: dict[str, int] = Field(default_factory=dict)
    category_distribution: dict[str, int] = Field(default_factory=dict)


class HistoryItem(BaseModel):
    owner: str
    repository: str
    pull_request_number: int
    pull_request_title: str | None = None
    status: str
    commit_sha: str | None = None
    total_finding_count: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    info_count: int = 0
    review_score: float | None = None
    review_severity: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class HistoryResponse(BaseModel):
    items: list[HistoryItem] = Field(default_factory=list)
    page: int = 1
    per_page: int = 20
    total: int = 0
    total_pages: int = 0


class RepositoryMetric(BaseModel):
    owner: str
    repository: str
    review_count: int = 0
    finding_count: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    info_count: int = 0
    average_findings_per_review: float = 0.0
    last_review_at: datetime | None = None


class RepoMetricsResponse(BaseModel):
    repositories: list[RepositoryMetric] = Field(default_factory=list)
    page: int = 1
    per_page: int = 20
    total: int = 0
    total_pages: int = 0


class FeedbackRequest(BaseModel):
    action: Literal["accepted", "dismissed"]


class FeedbackItem(BaseModel):
    review_id: str
    finding_id: str
    owner: str
    repository: str
    pull_request_number: int
    action: str
    category: str | None = None
    severity: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class FeedbackHistoryResponse(BaseModel):
    items: list[FeedbackItem] = Field(default_factory=list)
    page: int = 1
    per_page: int = 20
    total: int = 0
    total_pages: int = 0


class FeedbackActionStats(BaseModel):
    accepted: int = 0
    dismissed: int = 0
    total: int = 0


class FeedbackSummary(BaseModel):
    total_accepted: int = 0
    total_dismissed: int = 0
    total_feedback: int = 0
    acceptance_rate: float = 0.0
    category_feedback: dict[str, FeedbackActionStats] = Field(default_factory=dict)
    severity_feedback: dict[str, FeedbackActionStats] = Field(default_factory=dict)