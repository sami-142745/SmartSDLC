from datetime import datetime

from pydantic import BaseModel, Field


class LearningProfile(BaseModel):
    owner: str
    repository: str
    category: str
    accepted_count: int = 0
    dismissed_count: int = 0
    total_count: int = 0
    acceptance_rate: float = 0.0
    learned_weight: float = 1.0
    confidence: float = 0.0
    updated_at: datetime | None = None


class FeedbackLearningResponse(BaseModel):
    profiles: list[LearningProfile] = Field(default_factory=list)
    repositories: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    total_feedback: int = 0
    data_available: bool = False