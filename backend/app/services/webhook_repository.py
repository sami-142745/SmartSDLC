from __future__ import annotations

from datetime import datetime, timezone

from app.services.database import get_db

WEBHOOK_EVENTS_COLLECTION = "webhook_events"


async def ensure_indexes() -> None:
    db = get_db()
    await db[WEBHOOK_EVENTS_COLLECTION].create_index(
        "delivery_id",
        unique=True,
        sparse=True,
        name="idx_webhook_events_delivery",
    )


async def record_webhook_event(
    *,
    event: str,
    action: str,
    repository: str | None,
    pull_number: int | None,
    sender: str | None,
    installation_id: int | None,
    delivery_id: str | None = None,
    payload_hash: str | None = None,
) -> None:
    db = get_db()
    document = {
        "event": event,
        "action": action,
        "repository": repository,
        "pull_number": pull_number,
        "sender": sender,
        "installation_id": installation_id,
        "delivery_id": delivery_id,
        "payload_hash": payload_hash,
        "received_at": datetime.now(timezone.utc),
        "processed": True,
    }
    await db[WEBHOOK_EVENTS_COLLECTION].insert_one(document)


async def find_webhook_event_by_delivery(delivery_id: str) -> dict | None:
    if not delivery_id:
        return None
    db = get_db()
    return await db[WEBHOOK_EVENTS_COLLECTION].find_one({"delivery_id": delivery_id})


async def find_webhook_event_by_payload_hash(payload_hash: str) -> dict | None:
    if not payload_hash:
        return None
    db = get_db()
    return await db[WEBHOOK_EVENTS_COLLECTION].find_one({"payload_hash": payload_hash})


async def list_webhook_events(*, page: int = 1, per_page: int = 20) -> dict:
    db = get_db()
    total = await db[WEBHOOK_EVENTS_COLLECTION].count_documents({})
    cursor = (
        db[WEBHOOK_EVENTS_COLLECTION]
        .find({})
        .sort("received_at", -1)
        .skip((page - 1) * per_page)
        .limit(per_page)
    )
    items = [doc async for doc in cursor]
    return {"items": items, "total": total}