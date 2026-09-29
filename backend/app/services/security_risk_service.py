"""Deterministic risk scoring and repository posture.

No model is involved, by design. A posture number that a language model can move
by a point is not a posture number — it is noise, and a reviewer who watches it
jitter stops trusting the number and then stops reading the page. Every value
here is a pure function of the finding set, so the same repository always scores
the same and a score change always means a finding changed.

The weights are not invented here either. ``critical=8, high=3, medium=1`` are
the weights the Security page has always used, and they are re-exported as
:data:`SEVERITY_WEIGHTS` so there is a single definition in the backend. The
``SecurityPage`` component keeps its own copy for the review-derived view; the
two must not be allowed to drift, and the test suite asserts the same numbers.
"""

from __future__ import annotations

from typing import Iterable, Sequence

from app.schemas.security import (
    SEVERITIES,
    SecurityFinding,
    SecurityRiskSummary,
    SeverityCounts,
)
from app.services import security_normalizer

#: Severity weights, matching ``SecurityPage.postureScore``. ``low`` and
#: ``info`` contribute nothing: they are not actionable and would let a
#: repository of informational notes score worse than one with a real problem.
SEVERITY_WEIGHTS: dict[str, int] = {
    "critical": 8,
    "high": 3,
    "medium": 1,
    "low": 0,
    "info": 0,
}

#: Score floor and ceiling. The ceiling is reachable: a repository with no
#: findings scores 100 rather than being treated as unscored.
SCORE_CEILING = 100
SCORE_FLOOR = 0

#: Posture is a score, so the finding count it is divided by is bounded. Without
#: a cap, a single incident with 5 000 findings would produce a negative
#: penalty ratio and a meaningless number. The cap keeps the curve readable: a
#: repository with a handful of criticals already scores badly.
SCORING_FINDING_CAP = 200


def weighted_risk(findings: Iterable[SecurityFinding]) -> int:
    """Sum of per-severity weights across all findings."""
    return sum(SEVERITY_WEIGHTS.get(finding.severity, 0) for finding in findings)


def exposure_score(findings: Iterable[SecurityFinding]) -> int:
    """Weighted exposure, the same number the Security page displays."""
    return weighted_risk(findings)


def posture_score(findings: Sequence[SecurityFinding]) -> int:
    """Convert findings into a 0-100 posture score.

    The penalty is divided by the finding count, floored at
    :data:`SCORING_FINDING_CAP` so a very noisy repository cannot push the score
    arbitrarily negative. Mean weight per finding is therefore bounded at 8, and
    a repository of nothing but criticals lands at 0 rather than below it.
    """
    total = len(findings)
    if total == 0:
        return SCORE_CEILING
    divisor = max(1, min(total, SCORING_FINDING_CAP))
    penalty = weighted_risk(findings) / divisor
    return max(SCORE_FLOOR, min(SCORE_CEILING, int(SCORE_CEILING - penalty)))


def severity_counts(findings: Iterable[SecurityFinding]) -> SeverityCounts:
    counts = security_normalizer.severity_counts(findings)
    return SeverityCounts(**{severity: counts[severity] for severity in SEVERITIES})


def summarize(
    findings: Sequence[SecurityFinding],
    *,
    files_scanned: int = 0,
    files_skipped: int = 0,
    dependencies_analyzed: int = 0,
) -> SecurityRiskSummary:
    """Build the full risk summary for a scan."""
    return SecurityRiskSummary(
        total_findings=len(findings),
        severity_counts=severity_counts(findings),
        weighted_risk=weighted_risk(findings),
        posture_score=posture_score(findings),
        category_distribution=security_normalizer.category_distribution(findings),
        scanner_distribution=security_normalizer.scanner_distribution(findings),
        files_scanned=files_scanned,
        files_skipped=files_skipped,
        findings_by_file=security_normalizer.findings_by_file(findings),
        dependencies_analyzed=dependencies_analyzed,
    )


def grade(posture: int) -> str:
    """Human label for a posture score.

    Banded to match the tone thresholds the frontend already uses for the
    review-derived score, so a user does not see one page say "at risk" for 70
    and another say "healthy" for the same number.
    """
    if posture >= 90:
        return "healthy"
    if posture >= 70:
        return "watch"
    if posture >= 40:
        return "at_risk"
    return "critical"


def riskiest_files(findings: Iterable[SecurityFinding], limit: int = 5) -> list[str]:
    """Files with the most findings, worst first.

    Ties break on path so the list is stable between scans.
    """
    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.file] = counts.get(finding.file, 0) + 1
    return [
        path
        for path, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
    ]
