"""MongoDB persistence for cached repository analysis.

Shape of a cache document
-------------------------
``user_id``/``owner``/``repository`` scope every entry, ``analysis`` names the
computation (``dashboard``, ``health``, ``languages``, ``dependencies``,
``readme``, ``tree``) and ``payload`` holds the serialized result. Each entry
carries ``created_at``/``expires_at``; a MongoDB TTL index removes entries once
they are stale, while reads also check ``expires_at`` so a cached value is never
served past its TTL even if the background TTL sweep has not run yet.

Caching is a pure optimization: every consumer in
:mod:`app.services.repository_intelligence_service` can recompute from the SCM
provider, so a cache miss or an unavailable database degrades to a slower
response rather than an error.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.services.database import get_db

REPOSITORY_ANALYSIS_COLLECTION = "repository_analysis"

#: Analysis kinds that may be cached. Kept explicit so a typo cannot silently
#: create a new, never-read cache namespace.
ANALYSIS_KINDS = (
    "dashboard",
    "health",
    "languages",
    "dependencies",
    "readme",
    "tree",
    "architecture",
    "documentation",
    "supply_chain",
    "test_generation",
)

#: Default time-to-live per analysis kind, in seconds. Cheap, mostly-static
#: signals live longer than the aggregate dashboard that composes them.
DEFAULT_TTL_SECONDS: dict[str, int] = {
    "dashboard": 900,
    "health": 1800,
    "languages": 21600,
    "dependencies": 21600,
    "readme": 21600,
    "tree": 3600,
    # Structure changes far less often than a dashboard aggregate, and a full
    # analysis costs one provider tree walk plus a read per source file.
    "architecture": 21600,
    # Documentation changes about as often as structure, and an analysis costs a
    # tree walk plus one read per documentation and source file.
    "documentation": 21600,
    # The supply-chain view reads the same small set of manifests and lockfiles
    # as the dependency inspector, so it costs about the same as one tree walk
    # plus a handful of reads.
    "supply_chain": 21600,
    # Test generation is the most expensive analysis in the system: one read per
    # source and test file, plus a model call per proposed test file. Cached
    # aggressively because the answer only changes when code or tests change.
    "test_generation": 21600,
}

FALLBACK_TTL_SECONDS = 1800


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def ttl_for(analysis: str) -> int:
    return DEFAULT_TTL_SECONDS.get(analysis, FALLBACK_TTL_SECONDS)


def _collection():
    return get_db()[REPOSITORY_ANALYSIS_COLLECTION]


def _identity(user_id: int, owner: str, repository: str, analysis: str) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "owner": owner,
        "repository": repository,
        "analysis": analysis,
    }


async def ensure_indexes() -> None:
    db = get_db()
    await db[REPOSITORY_ANALYSIS_COLLECTION].create_index(
        [("user_id", 1), ("owner", 1), ("repository", 1), ("analysis", 1)],
        name="idx_repo_analysis_identity",
        unique=True,
    )
    await db[REPOSITORY_ANALYSIS_COLLECTION].create_index(
        [("expires_at", 1)],
        name="idx_repo_analysis_expiry",
        expireAfterSeconds=0,
    )


async def get_cached(
    user_id: int,
    owner: str,
    repository: str,
    analysis: str,
) -> dict[str, Any] | None:
    """Return a live cache entry, or None when absent or expired."""
    doc = await _collection().find_one(_identity(user_id, owner, repository, analysis))
    if doc is None:
        return None

    expires_at = doc.get("expires_at")
    if expires_at is None:
        return None
    if expires_at <= _utcnow():
        return None
    return doc


async def set_cached(
    user_id: int,
    owner: str,
    repository: str,
    analysis: str,
    payload: Any,
    ttl_seconds: int | None = None,
) -> dict[str, Any]:
    """Upsert a cache entry and return the stored document."""
    now = _utcnow()
    ttl = ttl_seconds if ttl_seconds is not None else ttl_for(analysis)
    document = {
        **_identity(user_id, owner, repository, analysis),
        "payload": payload,
        "created_at": now,
        "updated_at": now,
        "expires_at": now + timedelta(seconds=max(0, ttl)),
        "ttl_seconds": ttl,
    }
    await _collection().update_one(
        _identity(user_id, owner, repository, analysis),
        {"$set": document},
        upsert=True,
    )
    return document


async def invalidate(user_id: int, owner: str, repository: str) -> int:
    """Drop every cached analysis for one repository. Returns entries removed."""
    result = await _collection().delete_many(
        {"user_id": user_id, "owner": owner, "repository": repository}
    )
    return int(getattr(result, "deleted_count", 0) or 0)


async def list_cached_repositories(user_id: int) -> list[dict[str, Any]]:
    """Distinct repositories with at least one live cache entry."""
    cursor = _collection().find({"user_id": user_id, "expires_at": {"$gt": _utcnow()}})
    seen: dict[str, dict[str, Any]] = {}
    async for doc in cursor:
        key = f"{doc.get('owner')}/{doc.get('repository')}"
        if key in seen:
            continue
        seen[key] = {
            "owner": doc.get("owner"),
            "repository": doc.get("repository"),
            "full_name": key,
            "cached_at": doc.get("created_at"),
        }
    return list(seen.values())
