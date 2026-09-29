from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class WorkflowEventType(str, Enum):
    """Types of workflow events that can be recorded."""

    REPOSITORY_IMPORT = "repository_import"
    REPOSITORY_ANALYSIS = "repository_analysis"
    SECURITY_SCAN = "security_scan"
    SUPPLY_CHAIN_SCAN = "supply_chain_scan"
    ARCHITECTURE_ANALYSIS = "architecture_analysis"
    AI_REVIEW = "ai_review"
    DOCUMENTATION_GENERATION = "documentation_generation"
    TEST_GENERATION = "test_generation"
    DEPLOYMENT = "deployment"
    CI_CD_PIPELINE = "ci_cd_pipeline"


WORKFLOW_EVENT_TYPES = tuple(WorkflowEventType)


class WorkflowEventStatus(str, Enum):
    """Status of a workflow event."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowRunStatus(str, Enum):
    """Overall status of a workflow run."""

    QUEUED = "queued"  # Legacy: Sprint 3 used "queued" for pending workflows
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"  # Some events completed, some failed


class WorkflowStage(str, Enum):
    """Stages in the standard SmartSDLC workflow pipeline."""

    REPOSITORY_IMPORT = "repository_import"
    REPOSITORY_ANALYSIS = "repository_analysis"
    SECURITY_SCAN = "security_scan"
    SUPPLY_CHAIN_SCAN = "supply_chain_scan"
    ARCHITECTURE_ANALYSIS = "architecture_analysis"
    AI_REVIEW = "ai_review"
    DOCUMENTATION = "documentation"
    TEST_GENERATION = "test_generation"
    DEPLOYMENT = "deployment"


# Default stage sequence for a full pipeline
DEFAULT_STAGE_SEQUENCE = (
    WorkflowStage.REPOSITORY_IMPORT,
    WorkflowStage.REPOSITORY_ANALYSIS,
    WorkflowStage.SECURITY_SCAN,
    WorkflowStage.SUPPLY_CHAIN_SCAN,
    WorkflowStage.ARCHITECTURE_ANALYSIS,
    WorkflowStage.AI_REVIEW,
    WorkflowStage.DOCUMENTATION,
    WorkflowStage.TEST_GENERATION,
    WorkflowStage.DEPLOYMENT,
)


# ---------------------------------------------------------------------------
# Event Models
# ---------------------------------------------------------------------------

class WorkflowEvent(BaseModel):
    """A single event in a workflow run."""

    model_config = {"extra": "forbid"}

    event_id: str
    workflow_run_id: str
    event_type: WorkflowEventType
    status: WorkflowEventStatus
    stage: Optional[WorkflowStage] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    source: str  # e.g., "api", "webhook", "scheduler"
    triggered_by: Optional[int] = None  # user_id


class WorkflowEventCreate(BaseModel):
    """Request to create a workflow event."""

    model_config = {"extra": "forbid"}

    workflow_run_id: str
    event_type: WorkflowEventType
    stage: Optional[WorkflowStage] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    source: str = "api"


# ---------------------------------------------------------------------------
# Run Models
# ---------------------------------------------------------------------------

class WorkflowRun(BaseModel):
    """A complete workflow run for a repository.

    Includes legacy fields (``stage``, ``review_id``, ``history``) for
    backward compatibility with the Sprint 3 workflow schema.
    """

    model_config = {"extra": "forbid"}

    workflow_id: str
    owner: str
    repository: str
    pull_request_number: Optional[int] = None
    trigger: str = "manual"
    provider: str = "github"
    status: WorkflowRunStatus = WorkflowRunStatus.PENDING
    current_stage: Optional[WorkflowStage] = None
    stages: list[WorkflowStage] = Field(default_factory=list)
    stage_sequence: list[WorkflowStage] = Field(default_factory=lambda: list(DEFAULT_STAGE_SEQUENCE))
    error: Optional[str] = None
    duration_ms: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    events: list[WorkflowEvent] = Field(default_factory=list)

    # Legacy fields (Sprint 3 compatibility)
    stage: Optional[str] = None
    review_id: Optional[str] = None
    history: list[dict[str, Any]] = Field(default_factory=list)


class WorkflowRunCreate(BaseModel):
    """Request to create a workflow run."""

    model_config = {"extra": "forbid"}

    owner: str
    repository: str
    pull_request_number: Optional[int] = None
    trigger: str = "manual"
    provider: str = "github"
    stages: Optional[list[WorkflowStage]] = None
    stage_sequence: Optional[list[WorkflowStage]] = None


class WorkflowRunUpdate(BaseModel):
    """Request to update a workflow run."""

    model_config = {"extra": "forbid"}

    status: Optional[WorkflowRunStatus] = None
    current_stage: Optional[WorkflowStage] = None
    error: Optional[str] = None


class WorkflowRunListResponse(BaseModel):
    """Paginated list of workflow runs."""

    model_config = {"extra": "forbid"}

    items: list[WorkflowRun] = Field(default_factory=list)
    page: int = 1
    per_page: int = 20
    total: int = 0
    total_pages: int = 0


# ---------------------------------------------------------------------------
# CI/CD Models
# ---------------------------------------------------------------------------

class CICDProvider(str, Enum):
    """Supported CI/CD providers."""

    GITHUB_ACTIONS = "github_actions"
    AZURE_PIPELINES = "azure_pipelines"
    GITLAB_CI = "gitlab_ci"
    JENKINS = "jenkins"
    CUSTOM = "custom"


class CICDWorkflowRun(BaseModel):
    """A CI/CD pipeline run from an external provider."""

    model_config = {"extra": "forbid"}

    run_id: str
    provider: CICDProvider
    owner: str
    repository: str
    workflow_name: Optional[str] = None
    branch: str
    commit_sha: str
    status: Literal["pending", "running", "success", "failure", "cancelled", "skipped"]
    conclusion: Optional[str] = None
    url: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    jobs: list[dict[str, Any]] = Field(default_factory=list)


class CICDProviderConfig(BaseModel):
    """Configuration for a CI/CD provider integration."""

    model_config = {"extra": "forbid"}

    provider: CICDProvider
    enabled: bool = True
    external_url: Optional[str] = None
    api_token: Optional[str] = None  # Stored encrypted
    webhook_secret: Optional[str] = None  # Stored encrypted
    repository_patterns: list[str] = Field(default_factory=list)
    branch_patterns: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Request/Response Models
# ---------------------------------------------------------------------------

class WorkflowEventsResponse(BaseModel):
    """Paginated list of workflow events."""

    model_config = {"extra": "forbid"}

    items: list[WorkflowEvent] = Field(default_factory=list)
    page: int = 1
    per_page: int = 50
    total: int = 0
    total_pages: int = 0


class WorkflowRunWithEvents(BaseModel):
    """A workflow run with its events included."""

    model_config = {"extra": "forbid"}

    workflow: WorkflowRun
    events: list[WorkflowEvent] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Summary/Analytics Models
# ---------------------------------------------------------------------------

class WorkflowStageSummary(BaseModel):
    """Summary of a workflow stage across runs."""

    model_config = {"extra": "forbid"}

    stage: WorkflowStage
    total_runs: int = 0
    completed_runs: int = 0
    failed_runs: int = 0
    average_duration_ms: Optional[int] = None
    success_rate: float = 0.0


class WorkflowSummary(BaseModel):
    """Aggregate workflow statistics for a repository or user."""

    model_config = {"extra": "forbid"}

    owner: str
    repository: Optional[str] = None
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    running_runs: int = 0
    average_duration_ms: Optional[int] = None
    stage_summaries: list[WorkflowStageSummary] = Field(default_factory=list)
    recent_runs: list[WorkflowRun] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Maximum events per workflow run
MAX_EVENTS_PER_RUN = 200

# Maximum metadata size per event (bytes)
MAX_EVENT_METADATA_BYTES = 65536

# Default page sizes
DEFAULT_EVENTS_PER_PAGE = 50
DEFAULT_RUNS_PER_PAGE = 20