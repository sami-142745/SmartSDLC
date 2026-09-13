import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Request

from app.schemas.webhook import WebhookEvent, WebhookEventListResponse
from app.services.config import settings
from app.services.review_service import REVIEWABLE_ACTIONS, run_review_for_webhook
from app.services.security import get_current_user
from app.services.webhook_repository import (
    find_webhook_event_by_delivery,
    find_webhook_event_by_payload_hash,
    list_webhook_events,
    record_webhook_event,
)
from app.services.webhook_security import payload_hash, verify_webhook_signature

logger = logging.getLogger(__name__)

router = APIRouter()

SUPPORTED_PR_ACTIONS = {"opened", "synchronize", "reopened", "closed"}


@router.post("/webhook")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_github_event: str | None = Header(default=None, alias="X-GitHub-Event"),
    x_hub_signature_256: str | None = Header(default=None, alias="X-Hub-Signature-256"),
    x_github_delivery: str | None = Header(default=None, alias="X-GitHub-Delivery"),
):
    body = await request.body()

    if not verify_webhook_signature(body, x_hub_signature_256, settings.GITHUB_WEBHOOK_SECRET):
        logger.warning("Rejected webhook with missing or invalid signature")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    if x_github_event == "ping":
        return {"status": "ok", "event": "ping"}

    if x_github_event != "pull_request":
        logger.info("Ignoring unsupported webhook event: %s", x_github_event)
        return {"status": "ignored", "event": x_github_event}

    try:
        payload = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    action = payload.get("action")
    pr = payload.get("pull_request") or {}
    repository = payload.get("repository") or {}
    sender = payload.get("sender") or {}
    installation = payload.get("installation") or {}

    pr_number = pr.get("number")
    repo_full_name = repository.get("full_name")
    sender_login = sender.get("login")
    installation_id = installation.get("id")

    if pr_number is None:
        return {"status": "ignored", "event": "pull_request", "reason": "missing_pull_request"}

    if action not in SUPPORTED_PR_ACTIONS:
        logger.info("Ignoring pull_request event with unsupported action: %s", action)
        return {"status": "ignored", "event": "pull_request", "action": action}

    event_hash = payload_hash(body)
    existing = None
    if x_github_delivery:
        existing = await find_webhook_event_by_delivery(x_github_delivery)
    if existing is None:
        existing = await find_webhook_event_by_payload_hash(event_hash)
    if existing is not None:
        logger.info(
            "Rejected replayed webhook %s: %s#%s (delivery=%s, hash=%s)",
            action,
            repo_full_name,
            pr_number,
            x_github_delivery,
            event_hash[:12],
        )
        return {
            "status": "replayed",
            "event": x_github_event,
            "action": action,
            "delivery": x_github_delivery,
        }

    await record_webhook_event(
        event="pull_request",
        action=action,
        repository=repo_full_name,
        pull_number=pr_number,
        sender=sender_login,
        installation_id=installation_id,
        delivery_id=x_github_delivery,
        payload_hash=event_hash,
    )

    logger.info(
        "Webhook pull_request %s: %s#%s by %s (installation_id=%s)",
        action,
        repo_full_name,
        pr_number,
        sender_login,
        installation_id,
    )

    if action in REVIEWABLE_ACTIONS and repo_full_name:
        owner, repo = repo_full_name.split("/", 1) if "/" in repo_full_name else (repo_full_name, "")
        if repo:
            background_tasks.add_task(run_review_for_webhook, owner, repo, pr_number, sender_login)

    return {"status": "ok", "event": "pull_request", "action": action}


def _to_webhook_event(doc: dict) -> dict:
    payload_hash_value = doc.get("payload_hash")
    return {
        "id": str(doc.get("_id")),
        "event": doc.get("event"),
        "action": doc.get("action"),
        "repository": doc.get("repository"),
        "pull_number": doc.get("pull_number"),
        "sender": doc.get("sender"),
        "delivery_id": doc.get("delivery_id"),
        "payload_hash_prefix": f"{payload_hash_value[:16]}\u2026" if payload_hash_value else None,
        "received_at": doc.get("received_at"),
    }


@router.get("/webhook/events", response_model=WebhookEventListResponse)
async def get_webhook_events(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    data = await list_webhook_events(page=page, per_page=per_page)
    return {
        "items": [_to_webhook_event(doc) for doc in data["items"]],
        "total": data["total"],
    }