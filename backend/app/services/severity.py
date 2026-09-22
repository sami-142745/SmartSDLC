from __future__ import annotations

from typing import Any

from app.services.config import settings

# ---------------------------------------------------------------------------
# Legacy Phase 4 severity API (0..1 domain). Kept byte-compatible so the
# existing severity tests and the stored review_score semantics do not break.
# ---------------------------------------------------------------------------

PRIORITY = {"critical": 4.0, "high": 3.0, "medium": 2.0, "low": 1.0, "info": 0.5}

SEVERITY_WEIGHTS = {
    "security": settings.SEVERITY_HEURISTIC_SEC_WEIGHT,
    "complexity": settings.SEVERITY_HEURISTIC_COMPLEXITY_WEIGHT,
    "history": settings.SEVERITY_HISTORY_WEIGHT,
}

MAX_SIGNAL = 1.6


def compute_severity_score(
    *,
    security_evidence: float = 0.0,
    complexity: float = 0.0,
    history: float = 0.0,
) -> float:
    """S = (Wsec × P) + (Wcomp × C) + (Whist × H), Phase 4 spec formula."""
    return (
        SEVERITY_WEIGHTS["security"] * security_evidence
        + SEVERITY_WEIGHTS["complexity"] * complexity
        + SEVERITY_WEIGHTS["history"] * history
    )


def map_score_to_severity(score: float) -> str:
    if score >= 0.85:
        return "critical"
    if score >= 0.65:
        return "high"
    if score >= 0.45:
        return "medium"
    if score >= 0.2:
        return "low"
    return "info"


def _aggregate_security_signal(findings: list[dict[str, Any]]) -> float:
    # Weighted, confidence-scaled security evidence from heuristic findings.
    signal = 0.0
    for finding in findings:
        if finding.get("source") not in ("heuristic", "combined"):
            continue
        hint = finding.get("heuristic_severity", finding.get("severity", "info"))
        weight = PRIORITY.get(hint, PRIORITY["info"])
        confidence = float(finding.get("confidence", 0.5))
        signal += weight * confidence
    return min(signal, MAX_SIGNAL)


def _aggregate_complexity_signal(findings: list[dict[str, Any]]) -> float:
    signal = 0.0
    for finding in findings:
        if finding.get("source") not in ("gemini", "combined"):
            continue
        if finding.get("category") not in ("complexity", "maintainability"):
            continue
        if finding.get("severity") not in ("high", "critical"):
            continue
        weight = PRIORITY.get(finding.get("severity"), PRIORITY["info"])
        confidence = float(finding.get("confidence", 0.5))
        signal += weight * confidence
    return min(signal, MAX_SIGNAL)


def score_findings(findings: list[dict[str, Any]]) -> dict[str, Any]:
    """Legacy discriminator (0..1 score + severity + critical_flags).

    Retained for backward compatibility with the stored review_score field and
    with existing tests. Prefer :func:`score_review` (0..100 + explanation) for
    new code paths.
    """
    security_evidence = _aggregate_security_signal(findings)
    complexity_evidence = _aggregate_complexity_signal(findings)

    score = compute_severity_score(
        security_evidence=security_evidence,
        complexity=complexity_evidence,
        history=0.0,
    )
    return {
        "score": round(min(score, 1.0), 3),
        "severity": map_score_to_severity(score),
        "critical_flags": sum(
            1
            for f in findings
            if f.get("source") in ("heuristic", "combined")
            and f.get("heuristic_severity") == "critical"
        ),
    }


# ---------------------------------------------------------------------------
# Deterministic 0..100 reviewer score with a transparent explanation.
# ---------------------------------------------------------------------------

PERFECT_SCORE = 100.0

SEVERITY_PENALTY = {
    "critical": 25.0,
    "high": 15.0,
    "medium": 9.0,
    "low": 5.0,
    "info": 2.0,
}

SEVERITY_ORDER = ("critical", "high", "medium", "low", "info")


def _effective_finding_severity(finding: dict[str, Any]) -> str:
    """Severity used for scoring: heuristic evidence wins for heuristic sources."""
    if finding.get("source") in ("heuristic", "combined"):
        hint = finding.get("heuristic_severity")
        if hint in SEVERITY_PENALTY:
            return hint
    value = finding.get("severity")
    return value if value in SEVERITY_PENALTY else "info"


def score_review(findings: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute a deterministic 0..100 review score explained per finding.

    Rules (Phase 4 spec):
      * Start at 100.
      * Every deduplicated finding deducts a fixed penalty based on its
        *effective* severity (critical 25, high 15, medium 9, low 5, info 2).
      * The score is clamped to [0, 100]. The deduction applies once per
        finding, so duplicate findings later removed by the deduper are never
        double-counted here.
      * A review with zero findings is a perfect 100/100 (clean PR).

    Returns ``{"score", "severity", "score_breakdown", "score_explanation"}``
    where ``score_breakdown`` lists per-severity counts and the total penalty,
    and ``score_explanation`` is a human-readable sentence describing exactly
    why the score is what it is.
    """
    breakdown: dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    penalty = 0.0
    for finding in findings:
        sev = _effective_finding_severity(finding)
        breakdown[sev] += 1
        penalty += SEVERITY_PENALTY[sev]

    score = max(0.0, round(PERFECT_SCORE - penalty, 1))
    score = min(score, PERFECT_SCORE)

    counts = [f"{v} {k}" for k, v in breakdown.items() if v]
    if not counts:
        explanation = "No findings: the pull request is clean, score is 100/100."
    else:
        explanation = (
            "Score starts at 100 and deducts per finding: "
            + ", ".join(counts)
            + f". Total penalty {penalty:g}pt -> score {score:g}/100."
        )

    return {
        "score": score,
        "severity": _severity_for_score(score),
        "score_breakdown": breakdown,
        "total_penalty": round(penalty, 1),
        "score_explanation": explanation,
    }


def _severity_for_score(score: float) -> str:
    if score >= 90:
        return "low"
    if score >= 75:
        return "medium"
    if score >= 50:
        return "high"
    return "critical"
