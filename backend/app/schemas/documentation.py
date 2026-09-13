from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

DocumentStatus = Literal["complete", "failed"]


class DocumentationSource(BaseModel):
    repository: str
    owner: str
    pull_request: str | None = None
    commit: str | None = None
    branch: str | None = None


class DocumentationResponse(BaseModel):
    id: str
    title: str
    summary: str = ""
    architecture: str = ""
    modules: list[str] = Field(default_factory=list)
    api: list[str] = Field(default_factory=list)
    changes: list[str] = Field(default_factory=list)
    configuration: list[str] = Field(default_factory=list)
    security: list[str] = Field(default_factory=list)
    setup: list[str] = Field(default_factory=list)
    source: DocumentationSource
    model: str
    status: DocumentStatus
    error: str | None = None
    duration_ms: int | None = None
    generated_at: datetime | None = None


class DocumentationListResponse(BaseModel):
    items: list[DocumentationResponse] = Field(default_factory=list)
    page: int = 1
    per_page: int = 20
    total: int = 0
    total_pages: int = 0


class GenerateDocumentationRequest(BaseModel):
    owner: str
    repository: str
    pull_request: int | None = Field(default=None, ge=1)