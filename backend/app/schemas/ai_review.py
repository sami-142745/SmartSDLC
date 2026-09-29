"""Sprint 3 AI Pull Request Review contract (schema v2).

This module is deliberately **additive**. The Phase 1-4 review pipeline in
:mod:`app.schemas.review` stores ``Finding`` documents whose fields are
``id`` / ``code`` / ``recommendation`` and whose categories are the legacy set
(``bug``, ``complexity``, ``style``). Those documents back the dashboard,
insights, feedback-learning and adaptive-ranking features, so their shape is
frozen.

Sprint 3 introduces a richer, *self-describing* contract with stable
``finding_id`` keys, explicit code evidence, and a category vocabulary that
matches how reviewers actually talk. Legacy findings are converted into this
shape at the boundary by :func:`from_legacy_finding` instead of being mutated
in place, so both generations can coexist in the database and in the API.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# --------------------------------------------------------------------------
# Vocabularies
# --------------------------------------------------------------------------

AIReviewSeverity = Literal["critical", "high", "medium", "low", "info"]
AIReviewCategory = Literal[
    "bugs",
    "security",
    "performance",
    "code_quality",
    "maintainability",
    "testing",
]
AIReviewFileStatus = Literal["added", "modified", "deleted", "renamed", "binary"]
AIReviewStatus = Literal["queued", "in_progress", "complete", "partial", "failed"]
AIReviewSource = Literal["ai", "heuristic", "combined"]

AI_SEVERITIES: tuple[str, ...] = ("critical", "high", "medium", "low", "info")
AI_CATEGORIES: tuple[str, ...] = (
    "bugs",
    "security",
    "performance",
    "code_quality",
    "maintainability",
    "testing",
)

#: Lifecycle of the review itself.
REVIEW_STATUSES: tuple[str, ...] = ("queued", "in_progress", "complete", "partial", "failed")

#: Outcome of the AI leg specifically, kept separate from the review lifecycle
#: so the UI can say "the model was unreachable" without implying the diff was
#: never analyzed. ``skipped`` means there was nothing reviewable to send.
AI_STATUSES: tuple[str, ...] = ("complete", "unavailable", "malformed", "skipped")
AI_FILE_STATUSES: tuple[str, ...] = ("added", "modified", "deleted", "renamed", "binary")
AI_SOURCES: tuple[str, ...] = ("ai", "heuristic", "combined")

#: Dimensions surfaced by the labelled "AI review assessment" panel.
ASSESSMENT_DIMENSIONS: tuple[str, ...] = (
    "severity",
    "security",
    "quality",
    "performance",
    "maintainability",
    "testing",
)

#: Shown verbatim above the score so it can never be read as an absolute
#: statement about the software.
ASSESSMENT_LABEL = "AI review assessment"

ASSESSMENT_DISCLAIMER = (
    "This score reflects only the findings this automated review surfaced in "
    "this change. It is not a measure of overall software quality and must not "
    "be used on its own to accept or reject a pull request."
)

#: Explicit sentinel for findings that apply to a whole file rather than a
#: specific line (binary files, deleted files, file-level comments).
FILE_LEVEL_LINE = 0

SEVERITY_ORDER: tuple[str, ...] = ("critical", "high", "medium", "low", "info")

#: Maps the legacy Phase 1-4 vocabulary onto the Sprint 3 vocabulary. Applied
#: by :func:`normalize_category` so historical findings stay renderable.
CATEGORY_ALIASES: dict[str, str] = {
    # legacy
    "bug": "bugs",
    "bugs": "bugs",
    "correctness": "bugs",
    "complexity": "code_quality",
    "style": "code_quality",
    "code_quality": "code_quality",
    "quality": "code_quality",
    "security": "security",
    "performance": "performance",
    "perf": "performance",
    "maintainability": "maintainability",
    "maintainability_and_readability": "maintainability",
    "testing": "testing",
    "tests": "testing",
    "test_coverage": "testing",
    "documentation": "maintainability",
    "readability": "code_quality",
}

SEVERITY_ALIASES: dict[str, str] = {
    "blocker": "critical",
    "severe": "critical",
    "major": "high",
    "moderate": "medium",
    "minor": "low",
    "trivial": "info",
    "informational": "info",
    "warning": "medium",
    "error": "high",
    "note": "info",
    "nit": "info",
}

#: Which assessment dimension each category rolls up into.
CATEGORY_DIMENSION: dict[str, str] = {
    "bugs": "severity",
    "security": "security",
    "performance": "performance",
    "code_quality": "quality",
    "maintainability": "maintainability",
    "testing": "testing",
}


# --------------------------------------------------------------------------
# Normalizers
# --------------------------------------------------------------------------


SEVERITY_RANK: dict[str, int] = {name: index for index, name in enumerate(SEVERITY_ORDER)}


def _slug(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def normalize_category(value: Any, default: str = "maintainability") -> str:
    """Map any known category spelling — legacy or Sprint 3 — onto Sprint 3.

    Unrecognised input is folded to *default* rather than passed through, so a
    hallucinated category from the model can never widen the API contract.
    """
    slug = _slug(value)
    if not slug:
        return default
    if slug in AI_CATEGORIES:
        return slug
    return CATEGORY_ALIASES.get(slug, default)


def normalize_severity(value: Any, default: str = "info") -> str:
    slug = _slug(value)
    if not slug:
        return default
    if slug in SEVERITY_RANK:
        return slug
    return SEVERITY_ALIASES.get(slug, default)


def normalize_source(value: Any, default: str = "ai") -> str:
    slug = _slug(value)
    if slug == "gemini":
        # Sprint 2 called the model source "gemini"; Sprint 3 calls it "ai".
        return "ai"
    return slug if slug in AI_SOURCES else default


def clamp_confidence(value: Any, default: float = 0.5) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number != number or number in (float("inf"), float("-inf")):  # NaN / inf
        return default
    return max(0.0, min(1.0, round(number, 4)))


def _clean_text(value: Any, limit: int = 4000) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip()
    return text[:limit]


def _clean_code(value: Any, limit: int = 2000) -> str | None:
    text = _clean_text(value, limit)
    return text or None


# --------------------------------------------------------------------------
# Domain objects
# --------------------------------------------------------------------------


class ReviewSuggestion(BaseModel):
    """A concrete, applicable change proposed for a finding."""

    model_config = ConfigDict(extra="forbid")

    suggestion_id: str
    finding_id: str | None = None
    file: str | None = None
    title: str
    description: str = ""
    original_code: str | None = None
    suggested_code: str | None = None
    rationale: str | None = None

    @field_validator("title")
    @classmethod
    def _title(cls, v: str) -> str:
        return _clean_text(v, 300) or "Suggested change"


class ReviewFinding(BaseModel):
    """A single, addressable review finding.

    ``line`` is required by contract. Findings that genuinely apply to a whole
    file (binary files, deletions, file-level notes) carry
    :data:`FILE_LEVEL_LINE` (``0``) instead of a fabricated line number.
    """

    model_config = ConfigDict(extra="forbid")

    finding_id: str
    file: str
    line: int
    severity: str = "info"
    category: str = "maintainability"
    confidence: float = 0.5
    title: str
    description: str = ""
    suggestion: str = ""
    original_code: str | None = None
    suggested_code: str | None = None
    source: str = "ai"
    rule_id: str | None = None

    @field_validator("severity")
    @classmethod
    def _severity(cls, v: Any) -> str:
        return normalize_severity(v)

    @field_validator("category")
    @classmethod
    def _category(cls, v: Any) -> str:
        return normalize_category(v)

    @field_validator("source")
    @classmethod
    def _source(cls, v: Any) -> str:
        return normalize_source(v)

    @field_validator("confidence")
    @classmethod
    def _confidence(cls, v: Any) -> float:
        return clamp_confidence(v)

    @field_validator("title")
    @classmethod
    def _title(cls, v: str) -> str:
        return _clean_text(v, 300) or "Untitled finding"

    @field_validator("description", "suggestion")
    @classmethod
    def _prose(cls, v: str) -> str:
        return _clean_text(v, 4000)

    @field_validator("original_code", "suggested_code")
    @classmethod
    def _code(cls, v: str | None) -> str | None:
        return _clean_code(v)

    @field_validator("line")
    @classmethod
    def _line(cls, v: int) -> int:
        try:
            number = int(v)
        except (TypeError, ValueError):
            return FILE_LEVEL_LINE
        return max(FILE_LEVEL_LINE, number)

    @field_validator("file")
    @classmethod
    def _file(cls, v: str) -> str:
        return _clean_text(v, 500)

    @property
    def is_file_level(self) -> bool:
        return self.line == FILE_LEVEL_LINE


class ReviewFile(BaseModel):
    """One changed file in the pull request, with its per-file findings."""

    model_config = ConfigDict(extra="forbid")

    path: str
    previous_path: str | None = None
    status: str = "modified"
    language: str | None = None
    additions: int = 0
    deletions: int = 0
    changes: int = 0
    is_binary: bool = False
    patch: str | None = None
    finding_ids: list[str] = Field(default_factory=list)

    @field_validator("status")
    @classmethod
    def _status(cls, v: Any) -> str:
        slug = _slug(v)
        return slug if slug in AI_FILE_STATUSES else "modified"

    @field_validator("additions", "deletions", "changes")
    @classmethod
    def _counts(cls, v: int) -> int:
        try:
            return max(0, int(v))
        except (TypeError, ValueError):
            return 0

    @model_validator(mode="after")
    def _sync_status(self) -> "ReviewFile":
        # ``status`` and ``is_binary`` describe the same fact, so they are
        # reconciled here rather than in a field validator: by this point both
        # have been validated, and the caller cannot end up with a binary file
        # that claims to be modified (or the reverse).
        if self.status == "binary" or self.is_binary:
            object.__setattr__(self, "is_binary", True)
            object.__setattr__(self, "status", "binary")
        if (self.additions or self.deletions) and not self.changes:
            object.__setattr__(self, "changes", self.additions + self.deletions)
        return self


class AssessmentMetric(BaseModel):
    """One labelled dimension of the AI review assessment panel."""

    model_config = ConfigDict(extra="forbid")

    dimension: str
    label: str
    score: int = 100
    finding_count: int = 0

    @field_validator("score")
    @classmethod
    def _score(cls, v: Any) -> int:
        try:
            return max(0, min(100, round(float(v))))
        except (TypeError, ValueError):
            return 100


class ReviewSummary(BaseModel):
    """Aggregate, deterministic view of one review.

    The score is always presented under :data:`ASSESSMENT_LABEL` with
    :data:`ASSESSMENT_DISCLAIMER` so it is never mistaken for a verdict on the
    software as a whole.
    """

    model_config = ConfigDict(extra="forbid")

    assessment_label: str = ASSESSMENT_LABEL
    assessment_disclaimer: str = ASSESSMENT_DISCLAIMER
    assessment_score: int = 100
    assessment_severity: str = "info"
    metrics: list[AssessmentMetric] = Field(default_factory=list)
    total_findings: int = 0
    severity_counts: dict[str, int] = Field(default_factory=dict)
    category_counts: dict[str, int] = Field(default_factory=dict)
    files_reviewed: int = 0
    lines_added: int = 0
    lines_deleted: int = 0
    highest_severity: str | None = None

    @field_validator("assessment_severity")
    @classmethod
    def _severity(cls, v: Any) -> str:
        return normalize_severity(v)

    @field_validator("assessment_score")
    @classmethod
    def _score(cls, v: Any) -> int:
        try:
            return max(0, min(100, round(float(v))))
        except (TypeError, ValueError):
            return 100

    @property
    def primary_score(self) -> int:
        return self.assessment_score


class Review(BaseModel):
    """A complete, persisted AI pull request review."""

    model_config = ConfigDict(extra="forbid")

    review_id: str
    schema_version: int = 2
    status: str = "complete"
    ai_status: str = "complete"
    owner: str
    repository: str
    pull_request_number: int
    pull_request_title: str | None = None
    commit_sha: str | None = None
    provider: str = "github"
    summary: ReviewSummary = Field(default_factory=ReviewSummary)
    files: list[ReviewFile] = Field(default_factory=list)
    findings: list[ReviewFinding] = Field(default_factory=list)
    suggestions: list[ReviewSuggestion] = Field(default_factory=list)
    error: str | None = None
    duration_ms: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @field_validator("status")
    @classmethod
    def _status(cls, v: Any) -> str:
        slug = _slug(v) or "complete"
        return slug if slug in REVIEW_STATUSES else "complete"

    @field_validator("ai_status")
    @classmethod
    def _ai_status(cls, v: Any) -> str:
        slug = _slug(v) or "complete"
        return slug if slug in AI_STATUSES else "complete"

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.repository}"


# --------------------------------------------------------------------------
# Request / response envelopes
# --------------------------------------------------------------------------


class CreateReviewRequest(BaseModel):
    """Body for ``POST /api/reviews``."""

    model_config = ConfigDict(extra="forbid")

    owner: str = Field(..., min_length=1, max_length=200)
    repository: str = Field(..., min_length=1, max_length=200)
    pull_request_number: int = Field(..., ge=1)
    provider: str = "github"

    @field_validator("provider")
    @classmethod
    def _provider(cls, v: str) -> str:
        slug = _slug(v)
        return slug if slug in ("github", "gitlab") else "github"

    @field_validator("owner", "repository")
    @classmethod
    def _trim(cls, v: str) -> str:
        return v.strip()


class ReviewFindingsResponse(BaseModel):
    """Body for ``GET /api/reviews/{review_id}/findings``."""

    model_config = ConfigDict(extra="forbid")

    review_id: str
    total: int = 0
    findings: list[ReviewFinding] = Field(default_factory=list)

    @field_validator("total")
    @classmethod
    def _total(cls, v: int) -> int:
        return max(0, int(v))


# --------------------------------------------------------------------------
# Legacy bridge
# --------------------------------------------------------------------------


def from_legacy_finding(finding: dict[str, Any]) -> ReviewFinding:
    """Convert a stored Phase 1-4 ``Finding`` document into the v2 shape.

    Reads both the legacy keys (``id``/``code``/``recommendation``) and their
    Sprint 3 equivalents so a re-run never has to guess which generation a
    document came from.
    """
    finding_id = finding.get("finding_id") or finding.get("id") or ""
    original = finding.get("original_code") or finding.get("code")
    suggestion_text = finding.get("suggestion") or finding.get("recommendation") or ""
    return ReviewFinding(
        finding_id=str(finding_id),
        file=str(finding.get("file") or "unknown"),
        line=finding.get("line") if finding.get("line") is not None else FILE_LEVEL_LINE,
        severity=normalize_severity(finding.get("severity")),
        category=normalize_category(finding.get("category")),
        confidence=clamp_confidence(finding.get("confidence")),
        title=finding.get("title") or "Untitled finding",
        description=finding.get("description") or "",
        suggestion=suggestion_text or "",
        original_code=original,
        suggested_code=finding.get("suggested_code"),
        source=normalize_source(finding.get("source")),
        rule_id=finding.get("rule_id"),
    )
