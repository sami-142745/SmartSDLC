from __future__ import annotations

import logging
from typing import Any

from app.services import learning_repository, review_repository
from app.services.severity import PRIORITY

logger = logging.getLogger(__name__)

MAX_ADJUSTMENT = 0.15
CONFIDENCE_SATURATION = 5.0
MIN_TOTAL = 2
DEFAULT_WEIGHT = 1.0
DEFAULT_SOURCE = "default"
ADJUSTMENT_SOURCE_REPO = "repository+category"
ADJUSTMENT_SOURCE_USER = "user+category"

ALLOWED_CATEGORIES = {"security", "bug", "performance", "complexity", "maintainability", "style"}

FEEDBACK_ACTIONS = ("accepted", "dismissed")


def _normalize_category(category: str | None) -> str:
    if not category:
        return "unknown"
    normalized = category.strip().lower().replace(" ", "_").replace("-", "_")
    return normalized if normalized in ALLOWED_CATEGORIES else "unknown"


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _stats_from_counts(accepted: int, dismissed: int) -> dict[str, float]:
    """Derive (rate, base weight, confidence, effective weight) from raw counts.

    Base weight maps an acceptance rate of 0..1 into a bounded multiplier
    (0.85..1.15). Effective weight blends toward neutral by confidence so a
    single signal never dominates a review.
    """
    total = accepted + dismissed
    rate = round(accepted / total, 4) if total else 0.0
    base = _clamp(1.0 + (rate - 0.5) * 2 * MAX_ADJUSTMENT, 1.0 - MAX_ADJUSTMENT, 1.0 + MAX_ADJUSTMENT)
    confidence = round(min(1.0, total / CONFIDENCE_SATURATION), 4)
    effective = round(1.0 + (base - 1.0) * confidence, 4)
    return {"rate": rate, "base": round(base, 4), "confidence": confidence, "effective": effective}


def _to_profile(doc: dict[str, Any]) -> dict[str, Any]:
    accepted = doc.get("accepted_count") or 0
    dismissed = doc.get("dismissed_count") or 0
    stats = _stats_from_counts(accepted, dismissed)
    return {
        "owner": doc.get("owner"),
        "repository": doc.get("repository"),
        "category": doc.get("category"),
        "accepted_count": accepted,
        "dismissed_count": dismissed,
        "total_count": accepted + dismissed,
        "acceptance_rate": stats["rate"],
        "learned_weight": stats["base"],
        "confidence": stats["confidence"],
        "updated_at": doc.get("updated_at"),
    }


async def get_learning(
    user_id: int,
    owner: str | None = None,
    repository: str | None = None,
) -> dict[str, Any]:
    profiles = await learning_repository.list_profiles(user_id, owner, repository)
    items = [_to_profile(doc) for doc in profiles]
    return {
        "profiles": items,
        "repositories": sorted({item["repository"] for item in items}),
        "categories": sorted({item["category"] for item in items}),
        "total_feedback": sum(item["total_count"] for item in items),
        "data_available": bool(items),
    }


async def record_feedback(
    user_id: int,
    owner: str,
    repository: str,
    category: str | None,
    action: str,
) -> None:
    """Incrementally maintain the learning cache. Never raises."""
    if action not in FEEDBACK_ACTIONS:
        return
    try:
        key = _normalize_category(category)
        if action == "accepted":
            await learning_repository.upsert_counts(
                user_id=user_id, owner=owner, repository=repository, category=key, accepted_delta=1
            )
        else:
            await learning_repository.upsert_counts(
                user_id=user_id, owner=owner, repository=repository, category=key, dismissed_delta=1
            )
    except Exception:
        logger.exception("Feedback learning cache update failed for user=%s repo=%s/%s", user_id, owner, repository)


async def recalculate_learning(user_id: int) -> dict[str, Any]:
    """Rebuild the learning cache from raw feedback; prune stale profiles."""
    raw = await review_repository.list_feedback_for_user(
        user_id=user_id, page=1, per_page=100000
    )
    grouped: dict[tuple[str, str, str], list[int]] = {}
    for doc in raw["items"]:
        owner = doc.get("owner")
        repository = doc.get("repository")
        category = _normalize_category(doc.get("category"))
        if not owner or not repository:
            continue
        key = (owner, repository, category)
        grouped.setdefault(key, [0, 0])
        if doc.get("action") == "accepted":
            grouped[key][0] += 1
        elif doc.get("action") == "dismissed":
            grouped[key][1] += 1

    active_keys = set()
    for (owner, repository, category), (accepted, dismissed) in grouped.items():
        await learning_repository.set_counts(
            user_id=user_id,
            owner=owner,
            repository=repository,
            category=category,
            accepted=accepted,
            dismissed=dismissed,
        )
        active_keys.add((owner, repository, category))

    cached = await learning_repository.list_profiles(user_id)
    for doc in cached:
        key = (doc.get("owner"), doc.get("repository"), doc.get("category"))
        if key not in active_keys:
            await learning_repository.delete_profile(
                user_id=user_id,
                owner=doc.get("owner"),
                repository=doc.get("repository"),
                category=doc.get("category"),
            )

    return await get_learning(user_id)


async def resolve_learning_weights(
    user_id: int,
    owner: str,
    repository: str,
    categories: set[str],
) -> dict[str, dict[str, Any]]:
    """Resolve per-category feedback weights for a new review.

    Precedence: repository+category profile -> user+category profile -> neutral.
    A category only counts once it has at least MIN_TOTAL of feedback.
    Learning is best-effort: any failure yields neutral weights.
    """
    neutral = {category: {"weight": DEFAULT_WEIGHT, "pct": 0.0, "source": DEFAULT_SOURCE} for category in categories}
    try:
        profiles = await learning_repository.list_profiles(user_id)
    except Exception:
        logger.exception("Feedback learning resolution failed for user=%s", user_id)
        return neutral

    repo_groups: dict[tuple[str, str], dict[str, dict[str, int]]] = {}
    user_groups: dict[str, dict[str, int]] = {}
    for doc in profiles:
        category = doc.get("category")
        if not category:
            continue
        accepted = doc.get("accepted_count") or 0
        dismissed = doc.get("dismissed_count") or 0
        repo_key = (doc.get("owner"), doc.get("repository"))
        group = repo_groups.setdefault(repo_key, {}).setdefault(
            category, {"accepted": 0, "dismissed": 0}
        )
        group["accepted"] += accepted
        group["dismissed"] += dismissed
        user_group = user_groups.setdefault(category, {"accepted": 0, "dismissed": 0})
        user_group["accepted"] += accepted
        user_group["dismissed"] += dismissed

    for category in categories:
        norm = _normalize_category(category)
        counts = (repo_groups.get((owner, repository)) or {}).get(norm)
        source = ADJUSTMENT_SOURCE_REPO
        if counts is None or counts["accepted"] + counts["dismissed"] < MIN_TOTAL:
            counts = user_groups.get(norm)
            source = ADJUSTMENT_SOURCE_USER
        if counts is None or counts["accepted"] + counts["dismissed"] < MIN_TOTAL:
            neutral[category] = {"weight": DEFAULT_WEIGHT, "pct": 0.0, "source": DEFAULT_SOURCE}
            continue
        stats = _stats_from_counts(counts["accepted"], counts["dismissed"])
        neutral[category] = {
            "weight": stats["effective"],
            "pct": round((stats["effective"] - 1.0) * 100, 1),
            "source": source,
        }
    return neutral


def annotate_findings(
    findings: list[dict[str, Any]],
    weights: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Add passive priority hints without mutating severity/confidence/score."""
    annotated: list[dict[str, Any]] = []
    for finding in findings:
        category = finding.get("category") or "unknown"
        info = weights.get(category, {"weight": DEFAULT_WEIGHT, "pct": 0.0, "source": DEFAULT_SOURCE})
        base = PRIORITY.get(finding.get("severity") or "info", PRIORITY["info"])
        annotated.append(
            {
                **finding,
                "final_priority": round(base * float(info["weight"]), 4),
                "feedback_weight": float(info["weight"]),
                "feedback_adjustment_pct": float(info["pct"]),
                "adjustment_source": info["source"],
            }
        )
    return annotated