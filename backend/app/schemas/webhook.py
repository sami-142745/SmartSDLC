from datetime import datetime

from pydantic import BaseModel, Field


class WebhookEvent(BaseModel):
    id: str
    event: str
    action: str
    repository: str | None = None
    pull_number: int | None = None
    sender: str | None = None
    delivery_id: str | None = None
    payload_hash_prefix: str | None = None
    received_at: datetime | None = None


class WebhookEventListResponse(BaseModel):
    items: list[WebhookEvent] = Field(default_factory=list)
    total: int = 0