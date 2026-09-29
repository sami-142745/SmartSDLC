"""Deterministic repository health scoring.

Methodology
-----------
The health score is a weighted average of five independently observable signals.
Each signal is a pure function of provider-reported metadata; no model inference
is involved and no signal is invented.

======================  ======  ==========================================
Signal                  Weight  Derivation
======================  ======  ==========================================
``documentation``          0.20  100 when a non-empty README exists, else 0.
``licensing``              0.15  100 when a license is declared, else 0.
``maintenance``            0.25  Linear decay on days since the last push.
``community``              0.20  Saturating log curve on stars + forks.
``hygiene``                0.20  Ratio of open issues to project scale.
======================  ======  ==========================================

Weights sum to 1.0. When a signal cannot be observed it is scored ``None``,
excluded from the average, and its key is reported through
``unavailable_signals``; the remaining weights are renormalized so the score is
always a real average of what was actually measured. A repository for which
nothing can be observed yields ``score = 0.0`` with every signal reported
unavailable, which is visibly different from a genuine score of 0.

Curve definitions
-----------------
* **maintenance** — ``100`` for a push within ``MAINTENANCE_FLOOR_DAYS``, then
  linear to ``0`` at ``MAINTENANCE_CEILING_DAYS``. A repository never pushed to
  has no ``pushed_at`` and is therefore *unavailable*, not stale.
* **community** — ``100 * log10(1 + stars + forks) / log10(1 + COMMUNITY_SATURATION)``
  clamped to ``0..100``. Logarithmic because a repository with 50 stars is not
  meaningfully less "community" than one with 100; the curve saturates at
  ``COMMUNITY_SATURATION`` total stars+forks.
* **hygiene** — ``open_issues`` against ``max(HYGIENE_FLOOR_SCALE, stars + forks)``.
  Full marks at or below ``HYGIENE_CLEAN_RATIO`` of open issues per unit of
  scale, zero at or above ``HYGIENE_POOR_RATIO``. The floor keeps a brand-new
  repository with a single issue from scoring zero for an unrelated reason.

Grades
------
``A >= 90``, ``B >= 80``, ``C >= 70``, ``D >= 60``, else ``F``. These are the
same bands used by the CI gate thresholds so a repository reads consistently
across the product.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from app.schemas.repository_intelligence import HealthComponent, RepositoryHealth

MAINTENANCE_FLOOR_DAYS = 7
MAINTENANCE_CEILING_DAYS = 730
COMMUNITY_SATURATION = 5000
HYGIENE_CLEAN_RATIO = 0.02
HYGIENE_POOR_RATIO = 0.5
HYGIENE_FLOOR_SCALE = 10

WEIGHTS: dict[str, float] = {
    "documentation": 0.20,
    "licensing": 0.15,
    "maintenance": 0.25,
    "community": 0.20,
    "hygiene": 0.20,
}

LABELS: dict[str, str] = {
    "documentation": "Documentation",
    "licensing": "Licensing",
    "maintenance": "Maintenance",
    "community": "Community",
    "hygiene": "Hygiene",
}

GRADE_THRESHOLDS: tuple[tuple[float, str], ...] = (
    (90.0, "A"),
    (80.0, "B"),
    (70.0, "C"),
    (60.0, "D"),
)


class RepositoryIntelligenceError(Exception):
    """Raised when repository intelligence cannot be produced."""


def grade_for(score: float) -> str:
    for threshold, grade in GRADE_THRESHOLDS:
        if score >= threshold:
            return grade
    return "F"


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, value))


def _parse_timestamp(value: Any) -> datetime | None:
    """Parse an ISO-8601 timestamp, tolerating the trailing ``Z`` GitHub uses."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _documentation_component(has_readme: bool | None) -> HealthComponent:
    if has_readme is None:
        return HealthComponent(
            key="documentation",
            label=LABELS["documentation"],
            score=None,
            weight=WEIGHTS["documentation"],
            detail="README presence could not be determined.",
        )
    return HealthComponent(
        key="documentation",
        label=LABELS["documentation"],
        score=100.0 if has_readme else 0.0,
        weight=WEIGHTS["documentation"],
        detail=(
            "A README is present."
            if has_readme
            else "No README found; adopters have no entry point."
        ),
    )


def _licensing_component(license_name: str | None) -> HealthComponent:
    if license_name is None:
        return HealthComponent(
            key="licensing",
            label=LABELS["licensing"],
            score=0.0,
            weight=WEIGHTS["licensing"],
            detail="No license is declared.",
        )
    return HealthComponent(
        key="licensing",
        label=LABELS["licensing"],
        score=100.0,
        weight=WEIGHTS["licensing"],
        detail=f"Licensed under {license_name}.",
    )


def _maintenance_component(pushed_at: Any, now: datetime) -> HealthComponent:
    parsed = _parse_timestamp(pushed_at)
    if parsed is None:
        return HealthComponent(
            key="maintenance",
            label=LABELS["maintenance"],
            score=None,
            weight=WEIGHTS["maintenance"],
            detail="No push timestamp is reported, so activity cannot be measured.",
        )
    days = max(0.0, (now - parsed).total_seconds() / 86400.0)
    if days <= MAINTENANCE_FLOOR_DAYS:
        score = 100.0
    elif days >= MAINTENANCE_CEILING_DAYS:
        score = 0.0
    else:
        span = MAINTENANCE_CEILING_DAYS - MAINTENANCE_FLOOR_DAYS
        score = 100.0 * (1.0 - (days - MAINTENANCE_FLOOR_DAYS) / span)
    rounded_days = int(round(days))
    if rounded_days == 0:
        detail = "Pushed to today."
    elif rounded_days == 1:
        detail = "Last push was 1 day ago."
    else:
        detail = f"Last push was {rounded_days} days ago."
    return HealthComponent(
        key="maintenance",
        label=LABELS["maintenance"],
        score=round(_clamp(score), 1),
        weight=WEIGHTS["maintenance"],
        detail=detail,
    )


def _community_component(stars: int, forks: int) -> HealthComponent:
    total = max(0, int(stars or 0)) + max(0, int(forks or 0))
    denominator = math.log10(1 + COMMUNITY_SATURATION)
    raw = 100.0 * math.log10(1 + total) / denominator if denominator else 0.0
    score = _clamp(raw)
    return HealthComponent(
        key="community",
        label=LABELS["community"],
        score=round(score, 1),
        weight=WEIGHTS["community"],
        detail=f"{stars} stars and {forks} forks.",
    )


def _hygiene_component(open_issues: int, stars: int, forks: int) -> HealthComponent:
    issues = max(0, int(open_issues or 0))
    scale = max(HYGIENE_FLOOR_SCALE, max(0, int(stars or 0)) + max(0, int(forks or 0)))
    ratio = issues / scale
    if ratio <= HYGIENE_CLEAN_RATIO:
        score = 100.0
        detail = f"{issues} open issues against a scale of {scale}."
    elif ratio >= HYGIENE_POOR_RATIO:
        score = 0.0
        detail = f"{issues} open issues against a scale of {scale} is heavily overloaded."
    else:
        span = HYGIENE_POOR_RATIO - HYGIENE_CLEAN_RATIO
        score = 100.0 * (1.0 - (ratio - HYGIENE_CLEAN_RATIO) / span)
        detail = f"{issues} open issues against a scale of {scale}."
    return HealthComponent(
        key="hygiene",
        label=LABELS["hygiene"],
        score=round(_clamp(score), 1),
        weight=WEIGHTS["hygiene"],
        detail=detail,
    )


def compute_health(
    profile: dict[str, Any] | None,
    *,
    has_readme: bool | None = None,
    now: datetime | None = None,
    owner: str = "",
    repository: str = "",
    cached: bool = False,
) -> RepositoryHealth:
    """Score a repository from observed profile metadata.

    ``profile`` is the normalized mapping produced by
    :meth:`app.services.github_client.GitHubClient.get_repository_profile`.
    ``has_readme`` comes from the README service; when it is None the
    documentation signal is reported unavailable rather than assumed.
    """
    if profile is None:
        return RepositoryHealth(
            owner=owner,
            repository=repository,
            score=0.0,
            grade="F",
            components=[
                HealthComponent(
                    key=key,
                    label=LABELS[key],
                    score=None,
                    weight=WEIGHTS[key],
                    detail="No repository metadata was available to measure.",
                )
                for key in WEIGHTS
            ],
            unavailable_signals=list(WEIGHTS),
            measured_weight=0.0,
            method="weighted-average",
            generated_at=None,
            cached=cached,
        )

    current = now or datetime.now(timezone.utc)
    components = [
        _documentation_component(has_readme),
        _licensing_component(profile.get("license_name")),
        _maintenance_component(profile.get("pushed_at"), current),
        _community_component(profile.get("stars", 0) or 0, profile.get("forks", 0) or 0),
        _hygiene_component(
            profile.get("open_issues", 0) or 0,
            profile.get("stars", 0) or 0,
            profile.get("forks", 0) or 0,
        ),
    ]

    available = [component for component in components if component.score is not None]
    unavailable = [component.key for component in components if component.score is None]
    measured_weight = sum(component.weight for component in available)

    if available and measured_weight > 0:
        score = sum(component.score * component.weight for component in available) / measured_weight
    else:
        score = 0.0

    return RepositoryHealth(
        owner=owner or str(profile.get("owner") or ""),
        repository=repository or str(profile.get("repository") or ""),
        score=round(_clamp(score), 1),
        grade=grade_for(score),
        components=components,
        unavailable_signals=unavailable,
        measured_weight=round(measured_weight, 4),
        method="weighted-average",
        generated_at=current.isoformat(),
        cached=cached,
    )
