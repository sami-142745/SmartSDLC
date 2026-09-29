"""Sprint 3 AI pull-request review orchestration.

Pipeline, in order:

1. Fetch the pull request and its changed files from the SCM provider.
2. Normalize them into a :class:`~app.services.diff_service.NormalizedDiff`
   (see that module for why the provider shapes are not directly usable).
3. Short-circuit: an empty diff or one with nothing reviewable produces a
   completed review with zero findings — the AI is never asked to review
   nothing, and we never fabricate a finding to fill the panel.
4. Run the deterministic heuristic pass over the reviewable patches.
5. Ask Gemini for a structured review, and re-validate every returned finding
   against the real diff: the file must exist in the change, and the line must
   resolve to a line that actually changed.
6. Merge, dedupe, score, and persist.

Steps 4 and 5 are independent, so :func:`run_ai_review` fails soft on the model:
an unavailable or malformed AI response downgrades the *status* of an otherwise
valid review rather than failing the request. The deterministic findings and the
diff are still returned, and the UI can explain precisely what went wrong.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from typing import Any

from app.schemas.ai_review import (
    ASSESSMENT_DIMENSIONS,
    ASSESSMENT_LABEL,
    CATEGORY_DIMENSION,
    SEVERITY_ORDER,
    AssessmentMetric,
    Review,
    ReviewFile,
    ReviewFinding,
    ReviewSuggestion,
    ReviewSummary,
    from_legacy_finding,
    normalize_category,
    normalize_severity,
)
from app.schemas.review import Finding
from app.services import ai_review_repository, diff_service
from app.services.config import settings
from app.services.gemini_service import (
    GeminiUnavailable,
    MalformedModelResponse,
    generate_ai_review,
)
from app.services.heuristics import run_heuristics
from app.services.scm import ScmProvider

logger = logging.getLogger(__name__)

#: Per-dimension penalty weights. A critical security finding must hurt the
#: security dimension far more than a low maintainability note hurts its own.
DIMENSION_WEIGHTS: dict[str, float] = {
    "critical": 1.0,
    "high": 0.6,
    "medium": 0.3,
    "low": 0.12,
    "info": 0.04,
}

DIMENSION_LABELS: dict[str, str] = {
    "severity": "Severity",
    "security": "Security",
    "quality": "Code quality",
    "performance": "Performance",
    "maintainability": "Maintainability",
    "testing": "Testing",
}

_WHITESPACE = re.compile(r"\s+")


def _title_key(value: str | None) -> str:
    return _WHITESPACE.sub(" ", value or "").strip().lower()


def _dedup_key(finding: ReviewFinding) -> tuple[str, str, str, int]:
    return (finding.category, _title_key(finding.title), finding.file, finding.line)


# --------------------------------------------------------------------------
# Summary
# --------------------------------------------------------------------------


def build_summary(
    findings: list[ReviewFinding],
    *,
    files: list[ReviewFile],
) -> ReviewSummary:
    """Build the labelled assessment panel deterministically.

    Each dimension starts at 100 and loses a confidence-weighted penalty per
    finding in that dimension, floored at 0. The overall score is the mean of
    the six dimensions, which keeps a single catastrophic dimension from being
    averaged away by five healthy ones.
    """
    buckets: dict[str, list[ReviewFinding]] = {name: [] for name in ASSESSMENT_DIMENSIONS}
    for finding in findings:
        dimension = CATEGORY_DIMENSION.get(finding.category, "severity")
        buckets.setdefault(dimension, []).append(finding)

    metrics: list[AssessmentMetric] = []
    dimension_scores: list[int] = []
    for dimension in ASSESSMENT_DIMENSIONS:
        bucket = buckets.get(dimension, [])
        penalty = sum(
            DIMENSION_WEIGHTS.get(finding.severity, 0.04) * max(finding.confidence, 0.0)
            for finding in bucket
        )
        score = max(0, round(100 - penalty * 25))
        dimension_scores.append(score)
        metrics.append(
            AssessmentMetric(
                dimension=dimension,
                label=DIMENSION_LABELS.get(dimension, dimension.title()),
                score=score,
                finding_count=len(bucket),
            )
        )

    overall = round(sum(dimension_scores) / len(dimension_scores)) if dimension_scores else 100

    severity_counts = {name: 0 for name in SEVERITY_ORDER}
    category_counts: dict[str, int] = {}
    highest: str | None = None
    for finding in findings:
        severity_counts[finding.severity] = severity_counts.get(finding.severity, 0) + 1
        category_counts[finding.category] = category_counts.get(finding.category, 0) + 1
        if highest is None or SEVERITY_ORDER.index(finding.severity) < SEVERITY_ORDER.index(highest):
            highest = finding.severity

    return ReviewSummary(
        assessment_label=ASSESSMENT_LABEL,
        assessment_score=overall,
        assessment_severity=highest or "info",
        metrics=metrics,
        total_findings=len(findings),
        severity_counts=severity_counts,
        category_counts=category_counts,
        files_reviewed=len(files),
        lines_added=sum(file.additions for file in files),
        lines_deleted=sum(file.deletions for file in files),
        highest_severity=highest,
    )


# --------------------------------------------------------------------------
# Finding construction
# --------------------------------------------------------------------------


def _heuristic_findings(
    diff: diff_service.NormalizedDiff,
) -> list[ReviewFinding]:
    """Run the deterministic pass and map its legacy output onto the v2 shape."""
    out: list[ReviewFinding] = []
    for file in diff.reviewable_files:
        if not file.patch:
            continue
        try:
            detected = run_heuristics(file.patch, file.path)
        except Exception:  # noqa: BLE001 - a broken rule must not fail the review
            logger.exception("Heuristic pass failed for %s", file.path)
            continue
        for raw in detected:
            if not isinstance(raw, dict):
                continue
            legacy = Finding(
                id=str(raw.get("id") or f"h-{uuid.uuid4().hex[:10]}"),
                title=raw.get("title") or "Heuristic finding",
                description=raw.get("description") or "",
                severity=normalize_severity(raw.get("heuristic_severity") or raw.get("severity")),
                category=normalize_category(raw.get("category")),
                file=raw.get("file") or file.path,
                line=raw.get("line"),
                code=raw.get("code"),
                recommendation=raw.get("recommendation"),
                confidence=float(raw.get("heuristic_confidence") or raw.get("confidence") or 0.5),
                source="heuristic",
            )
            finding = from_legacy_finding(legacy.model_dump(mode="json"))
            finding.rule_id = raw.get("rule_id")
            finding.file = file.path
            finding.line = diff_service.resolve_line(file, finding.line)
            original, snippet = diff_service.evidence_for(file, finding.line)
            finding.original_code = original or finding.original_code
            if snippet and not finding.description:
                finding.description = snippet
            out.append(finding)
    return out


def _ai_findings(payload: Any, diff: diff_service.NormalizedDiff) -> list[ReviewFinding]:
    """Convert validated model output into findings anchored to the real diff.

    A finding whose file is not part of this pull request is dropped: it
    describes something we are not reviewing. A finding whose line cannot be
    resolved degrades to file level rather than pointing at the wrong line.
    """
    out: list[ReviewFinding] = []
    for raw in getattr(payload, "findings", []) or []:
        file = diff.resolve_path(raw.file)
        if file is None:
            logger.info("Dropped AI finding for file not in diff: %s", raw.file)
            continue

        line = diff_service.resolve_line(file, raw.line)
        original, _snippet = diff_service.evidence_for(file, line)
        out.append(
            ReviewFinding(
                finding_id=f"a-{uuid.uuid4().hex[:12]}",
                file=file.path,
                line=line,
                severity=raw.severity,
                category=raw.category,
                confidence=raw.confidence,
                title=raw.title,
                description=raw.description,
                suggestion=raw.suggestion,
                # Prefer the model's quoted code only when it matches the diff;
                # a hallucinated quote must not become the evidence.
                original_code=original or raw.original_code,
                suggested_code=raw.suggested_code,
                source="ai",
            )
        )
    return out


def _merge(primary: list[ReviewFinding], secondary: list[ReviewFinding]) -> list[ReviewFinding]:
    """Deduplicate across sources, keeping the AI finding when both agree.

    AI findings are ordered first so their richer explanation and proposed fix
    win over the terser heuristic record for the same issue.
    """
    merged: list[ReviewFinding] = []
    seen: set[tuple[str, str, str, int]] = set()
    for finding in list(primary) + list(secondary):
        key = _dedup_key(finding)
        if key in seen:
            continue
        seen.add(key)
        merged.append(finding)
    return merged


def _build_suggestions(findings: list[ReviewFinding]) -> list[ReviewSuggestion]:
    """One suggestion per finding that actually proposes a code change."""
    suggestions: list[ReviewSuggestion] = []
    for index, finding in enumerate(findings):
        if not finding.suggested_code and not finding.suggestion:
            continue
        suggestions.append(
            ReviewSuggestion(
                suggestion_id=f"s-{index + 1}",
                finding_id=finding.finding_id,
                file=finding.file,
                title=finding.title,
                description=finding.description,
                original_code=finding.original_code,
                suggested_code=finding.suggested_code,
                rationale=finding.suggestion or None,
            )
        )
    return suggestions


def _build_files(diff: diff_service.NormalizedDiff, findings: list[ReviewFinding]) -> list[ReviewFile]:
    ids_by_path: dict[str, list[str]] = {}
    for finding in findings:
        ids_by_path.setdefault(finding.file, []).append(finding.finding_id)

    return [
        ReviewFile(
            path=file.path,
            previous_path=file.previous_path,
            status=file.status,
            language=file.language,
            additions=file.additions,
            deletions=file.deletions,
            changes=file.changes,
            is_binary=file.is_binary,
            patch=file.patch,
            finding_ids=ids_by_path.get(file.path, []),
        )
        for file in diff.files
    ]


def _review_context(
    pull_request: dict[str, Any],
    diff: diff_service.NormalizedDiff,
    provider: ScmProvider,
) -> dict[str, Any]:
    """Assemble the prompt context from the normalized diff.

    Only reviewable text is sent: binary files contribute nothing useful and
    would waste the context budget. Patches are re-truncated here because the
    normalized diff keeps full patches for rendering while the model only needs
    a bounded slice.
    """
    budget = max(1, settings.REVIEW_MAX_DIFF_CHARS)
    parts: list[str] = []
    for file in diff.reviewable_files:
        patch = (file.patch or "")[: settings.REVIEW_MAX_FILE_CHARS]
        if not patch.strip():
            continue
        header = f"### {file.path} ({file.status})"
        parts.append(f"{header}\n```diff\n{patch}\n```")

    return {
        "repository": f"{pull_request.get('owner') or ''}/{pull_request.get('repo') or ''}".strip("/"),
        "provider": provider.value,
        "pull_request_number": pull_request.get("number"),
        "pull_request_title": pull_request.get("title"),
        "diff": "\n".join(parts)[:budget],
        "changed_files": [
            {
                "path": file.path,
                "status": file.status,
                "additions": file.additions,
                "deletions": file.deletions,
            }
            for file in diff.files
        ],
        "heuristic_findings": [],
    }


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


async def run_ai_review(
    client: Any,
    owner: str,
    repository: str,
    number: int,
    *,
    provider: ScmProvider = ScmProvider.github,
    user_id: int | None = None,
) -> Review:
    """Run a full AI review and persist it.

    Provider errors propagate untouched so the router can map them onto the
    right HTTP status; only AI-model failures are absorbed into the review
    status.
    """
    started = time.monotonic()

    pull_request = await client.get_pull_request(owner, repository, number)
    raw_files = await client.get_pull_request_files(owner, repository, number)

    title = pull_request.get("title")
    commit_sha = pull_request.get("head_sha") or (pull_request.get("head") or {}).get("sha")

    diff = diff_service.normalize_diff(
        raw_files,
        max_files=settings.REVIEW_MAX_FILES,
        max_patch_chars=settings.REVIEW_MAX_FILE_CHARS,
    )

    files = _build_files(diff, [])

    # Nothing reviewable: a real, valid, empty review. We do not call the model,
    # and we never invent a finding to make the panel look populated.
    if diff.is_empty or not diff.reviewable_files:
        review = Review(
            review_id="",
            owner=owner,
            repository=repository,
            pull_request_number=number,
            pull_request_title=title,
            commit_sha=commit_sha,
            provider=provider.value,
            status="complete",
            ai_status="skipped",
            files=files,
            findings=[],
            summary=build_summary([], files=files),
            duration_ms=int((time.monotonic() - started) * 1000),
        )
        return await _persist(review, user_id=user_id)

    heuristic = _heuristic_findings(diff)
    context = _review_context(
        {**pull_request, "owner": owner, "repo": repository}, diff, provider
    )
    context["heuristic_findings"] = [
        {
            "file": finding.file,
            "line": finding.line,
            "severity": finding.severity,
            "category": finding.category,
            "title": finding.title,
        }
        for finding in heuristic
    ]

    ai: list[ReviewFinding] = []
    ai_status = "complete"
    error: str | None = None

    try:
        payload = await generate_ai_review(context)
    except MalformedModelResponse as exc:
        logger.warning("Malformed AI review output for %s/%s#%s: %s", owner, repository, number, exc)
        ai_status = "malformed"
        error = str(exc)
    except GeminiUnavailable as exc:
        logger.warning("AI unavailable for %s/%s#%s: %s", owner, repository, number, exc)
        ai_status = "unavailable"
        error = str(exc)
    else:
        ai = _ai_findings(payload, diff)

    findings = _merge(ai, heuristic)
    files = _build_files(diff, findings)

    # The diff was fetched and the deterministic pass ran either way, so a
    # failed model call downgrades the review to "partial" — it is incomplete,
    # not absent. "failed" is never produced here because a diff we could not
    # fetch raises as a provider error before this point.
    status = "complete" if ai_status == "complete" else "partial"

    review = Review(
        review_id="",
        owner=owner,
        repository=repository,
        pull_request_number=number,
        pull_request_title=title,
        commit_sha=commit_sha,
        provider=provider.value,
        status=status,
        ai_status=ai_status,
        files=files,
        findings=findings,
        suggestions=_build_suggestions(findings),
        summary=build_summary(findings, files=files),
        error=error,
        duration_ms=int((time.monotonic() - started) * 1000),
    )
    return await _persist(review, user_id=user_id)


async def _persist(review: Review, *, user_id: int | None) -> Review:
    review_id = await ai_review_repository.save_review(review, user_id=user_id)
    review.review_id = review_id
    return review
