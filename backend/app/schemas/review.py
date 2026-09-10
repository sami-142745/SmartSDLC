from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, field_validator

Severity = Literal["critical", "high", "medium", "low", "info"]
Category = Literal["security", "bug", "performance", "complexity", "maintainability", "style"]
FindingSource = Literal["heuristic", "gemini", "combined"]

ALLOWED_SEVERITIES = {"critical", "high", "medium", "low", "info"}
ALLOWED_CATEGORIES = {"security", "bug", "performance", "complexity", "maintainability", "style"}
ALLOWED_SOURCES = {"heuristic", "gemini", "combined"}

DEFAULT_SEVERITY = "info"
DEFAULT_CATEGORY = "maintainability"
DEFAULT_SOURCE = "heuristic"


def _normalize(value: str | None, allowed: set[str], default: str) -> str:
    if not value:
        return default
    normalized = value.strip().lower().replace(" ", "_").replace("-", "_")
    return normalized if normalized in allowed else default


class Finding(BaseModel):
    """Canonical review finding returned by the API and stored in MongoDB."""

    id: str
    title: str
    description: str
    severity: str = DEFAULT_SEVERITY
    category: str = DEFAULT_CATEGORY
    file: str | None = None
    line: int | None = None
    code: str | None = None
    recommendation: str | None = None
    confidence: float = 0.5
    source: str = DEFAULT_SOURCE

    @field_validator("severity")
    @classmethod
    def _severity(cls, v: str) -> str:
        return _normalize(v, ALLOWED_SEVERITIES, DEFAULT_SEVERITY)

    @field_validator("category")
    @classmethod
    def _category(cls, v: str) -> str:
        return _normalize(v, ALLOWED_CATEGORIES, DEFAULT_CATEGORY)

    @field_validator("source")
    @classmethod
    def _source(cls, v: str) -> str:
        return _normalize(v, ALLOWED_SOURCES, DEFAULT_SOURCE)

    @field_validator("confidence")
    @classmethod
    def _confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, float(v)))

    def model_dump_for_db(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class GeminiFinding(BaseModel):
    """Permissive model used to validate raw Gemini-provided findings."""

    title: str
    description: str | None = None
    severity: str | None = None
    category: str | None = None
    file: str | None = None
    line: int | None = None
    code: str | None = None
    recommendation: str | None = None
    confidence: float = 0.5


class ReviewResponse(BaseModel):
    status: str
    repository: str
    owner: str
    pull_request_number: int
    pull_request_title: str | None = None
    commit_sha: str | None = None
    findings: list[Finding]
    heuristic_finding_count: int = 0
    gemini_finding_count: int = 0
    total_finding_count: int = 0
    review_score: float | None = None
    review_severity: str | None = None
    duration_ms: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None