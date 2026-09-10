from __future__ import annotations

from app.services.config import settings

PRIORITY = {"critical": 4.0, "high": 3.0, "medium": 2.0, "low": 1.0, "info": 0.5}

SEVERITY_WEIGHTS = {
    "security": settings.SEVERITY_HEURISTIC_SEC_WEIGHT,
    "complexity": settings.SEVERITY_HEURISTIC_COMPLEXITY_WEIGHT,
    "history": settings.SEVERITY_HISTORY_WEIGHT,
}

MAX_SIGNAL = 1.6


def compute_severity_score(*, security_evidence: float = 0.0, complexity: float = 0.0, history: float = 0.0) -> float:
    """S = (Wsec × P) + (Wcomp × C) + (Whist × H), per the Phase 4 spec."""
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


def _aggregate_security_signal(findings: list[dict]) -> float:
    signal = 0.0
    for finding in findings:
        if finding.get("source") not in ("heuristic", "combined"):
            continue
        hint = finding.get("heuristic_severity", finding.get("severity", "info"))
        weight = PRIORITY.get(hint, PRIORITY["info"])
        confidence = float(finding.get("confidence", 0.5))
        signal += weight * confidence
    return min(signal, MAX_SIGNAL)


def _aggregate_complexity_signal(findings: list[dict]) -> float:
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


def score_findings(findings: list[dict]) -> dict:
    """Compute the review score and severity from normalized findings.

    security_evidence (P) aggregates heuristic security findings (weighted by
    confidence), complexity (C) aggregates high/critical AI complexity signals,
    historical evidence (H) is 0 for Phase 4 (history-based prioritization is a
    later phase).
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
            if f.get("source") in ("heuristic", "combined") and f.get("heuristic_severity") == "critical"
        ),
    }