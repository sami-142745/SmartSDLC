from __future__ import annotations

from datetime import datetime, timezone

from app.services.database import get_db

WEBHOOK_EVENTS_COLLECTION = "webhook_events"


async def record_webhook_event(
    *,
    event: str,
    action: str,
    repository: str | None,
    pull_number: int | None,
    sender: str | None,
    installation_id: int | None,
) -> None:
    db = get_db()
    document = {
        "event": event,
        "action": action,
        "repository": repository,
        "pull_number": pull_number,
        "sender": sender,
        "installation_id": installation_id,
        "received_at": datetime.now(timezone.utc),
        "processed": True,
    }
    await db[WEBHOOK_EVENTS_COLLECTION].insert_one(document)