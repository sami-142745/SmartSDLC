from datetime import datetime

from pydantic import BaseModel, Field


class WorkflowHistoryEntry(BaseModel):
    stage: str
    at: datetime | None = None
    detail: str | None = None


class Workflow(BaseModel):
    workflow_id: str
    owner: str
    repository: str
    pull_request_number: int
    trigger: str = "manual"
    provider: str = "github"
    status: str
    stage: str
    error: str | None = None
    review_id: str | None = None
    duration_ms: int | None = None
    history: list[WorkflowHistoryEntry] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class WorkflowListResponse(BaseModel):
    items: list[Workflow] = Field(default_factory=list)
    page: int = 1
    per_page: int = 20
    total: int = 0
    total_pages: int = 0