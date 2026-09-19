from __future__ import annotations

import logging
import time
from typing import Any, Awaitable, Callable

from app.services import feedback_learning_service, review_repository, severity, workflow_service
from app.services.config import settings
from app.services.gemini_service import GeminiUnavailable, review_code
from app.services.github_client import GitHubAPIError, GitHubClient
from app.services.heuristics import run_heuristics
from app.services.user_repository import get_user_by_login

logger = logging.getLogger(__name__)

REVIEWABLE_ACTIONS = ("opened", "synchronize", "reopened")


def _truncate(text: str | None, limit: int) -> str:
    if not text:
        return ""
    return text if len(text) <= limit else text[:limit]


def _bounded_files(files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    bounded: list[dict[str, Any]] = []
    for entry in files[: settings.REVIEW_MAX_FILES]:
        copy = dict(entry)
        if copy.get("patch"):
            copy["patch"] = _truncate(copy["patch"], settings.REVIEW_MAX_FILE_CHARS)
        bounded.append(copy)
    return bounded


def _normalize_key(finding: dict[str, Any]) -> tuple[str, str | None, int | None]:
    title = (finding.get("title") or "").strip().lower()
    return title, finding.get("file"), finding.get("line")


def _merge_findings(heuristic: list[dict[str, Any]], gemini: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = list(heuristic)
    seen = {_normalize_key(f) for f in merged}
    for finding in gemini:
        key = _normalize_key(finding)
        if key in seen:
            continue
        seen.add(key)
        merged.append(finding)
    return merged


def _review_context(pull_request: dict[str, Any], files: list[dict[str, Any]], repo_full_name: str) -> dict[str, Any]:
    bounded = _bounded_files(files)
    heuristic = []
    for entry in bounded:
        if entry.get("patch"):
            heuristic.extend(run_heuristics(entry["patch"], entry.get("filename")))
    diff_parts = [
        f"### {entry.get('filename')}\n```diff\n{_truncate(entry.get('patch') or '', settings.REVIEW_MAX_FILE_CHARS)}\n```"
        for entry in bounded
        if entry.get("patch")
    ]
    diff = "\n".join(diff_parts)[: settings.REVIEW_MAX_DIFF_CHARS]
    return {
        "repository": repo_full_name or "unknown/unknown",
        "pull_request_number": pull_request.get("number"),
        "pull_request_title": pull_request.get("title"),
        "diff": diff,
        "heuristic_findings": heuristic,
        "files": bounded,
    }


def _build_response(review: dict[str, Any]) -> dict[str, Any]:
    findings = review["findings"]
    return {
        "status": review["status"],
        "repository": review["repository"],
        "owner": review["owner"],
        "pull_request_number": review["pull_request_number"],
        "pull_request_title": review["pull_request_title"],
        "commit_sha": review.get("commit_sha"),
        "review_id": review.get("review_id"),
        "findings": findings,
        "heuristic_finding_count": sum(1 for f in findings if f.get("source") in ("heuristic", "combined")),
        "gemini_finding_count": sum(1 for f in findings if f.get("source") in ("gemini", "combined")),
        "total_finding_count": len(findings),
        "review_score": review.get("review_score"),
        "review_severity": review.get("review_severity"),
        "duration_ms": review.get("duration_ms"),
        "created_at": review.get("created_at"),
        "updated_at": review.get("updated_at"),
    }


async def run_review(
    github: GitHubClient,
    owner: str,
    repo: str,
    number: int,
    *,
    user_id: int | None = None,
    progress: Callable[[str], Awaitable[None]] | None = None,
) -> dict[str, Any]:
    started = time.monotonic()
    try:
        pull_request = await github.get_pull_request(owner, repo, number)
        raw_files = await github.get_pull_request_files(owner, repo, number)
    except GitHubAPIError:
        raise

    if progress:
        await progress("FETCHING")

    context = _review_context(pull_request, raw_files, f"{owner}/{repo}")
    heuristic = context["heuristic_findings"]
    gemini: list[dict[str, Any]] = []
    status = "complete"
    error: str | None = None

    if context["files"]:
        try:
            gemini = await review_code(context)
        except GeminiUnavailable as exc:
            logger.warning("Gemini unavailable for %s/%s#%s: %s", owner, repo, number, exc)
            status = "gemini_unavailable"
            error = str(exc)

    if progress:
        await progress("ANALYZING")

    findings = _merge_findings(heuristic, gemini)
    scoring = severity.score_findings(findings)

    if user_id is not None:
        categories = {finding.get("category") or "unknown" for finding in findings}
        weights = await feedback_learning_service.resolve_learning_weights(
            user_id, owner, repo, categories
        )
    else:
        weights = {}
    findings = feedback_learning_service.annotate_findings(findings, weights)

    if progress:
        await progress("GENERATING_REVIEW")

    duration_ms = int((time.monotonic() - started) * 1000)
    review_id = await review_repository.save_review(
        status=status,
        owner=owner,
        repository=repo,
        pull_request_number=number,
        pull_request_title=pull_request.get("title"),
        commit_sha=pull_request.get("head_sha") or pull_request.get("head", {}).get("sha"),
        findings=findings,
        review_score=scoring["score"] if status == "complete" else None,
        review_severity=scoring["severity"] if status == "complete" else None,
        duration_ms=duration_ms,
        error=error,
        user_id=user_id,
    )
    if progress:
        await progress("PERSISTING")
    return _build_response(
        {
            "status": status,
            "repository": repo,
            "owner": owner,
            "pull_request_number": number,
            "pull_request_title": pull_request.get("title"),
            "commit_sha": pull_request.get("head_sha") or pull_request.get("head", {}).get("sha"),
            "review_id": review_id,
            "review_score": scoring["score"] if status == "complete" else None,
            "review_severity": scoring["severity"] if status == "complete" else None,
            "duration_ms": duration_ms,
            "created_at": None,
            "updated_at": None,
            "findings": findings,
            "error": error,
        }
    )


async def run_review_for_webhook(owner: str, repo: str, number: int, sender_login: str | None) -> None:
    """Best-effort review triggered from a webhook. Never raises."""
    try:
        user = await get_user_by_login(sender_login) if sender_login else None
        token = (user or {}).get("github_access_token")
        if not token:
            logger.info(
                "No GitHub token for %r; skipping automated review of %s/%s#%s",
                sender_login,
                owner,
                repo,
                number,
            )
            return
        workflow_id = await workflow_service.begin_workflow(
            user_id=(user or {}).get("github_id"),
            owner=owner,
            repository=repo,
            pull_request_number=number,
            trigger="webhook",
            initiated_by="webhook",
            provider="github",
        )
        if workflow_id:
            await workflow_service.advance_workflow(workflow_id, "VALIDATED")

        async def progress(stage: str) -> None:
            await workflow_service.advance_workflow(workflow_id, stage)

        result = await run_review(
            GitHubClient(token),
            owner,
            repo,
            number,
            user_id=(user or {}).get("github_id"),
            progress=progress,
        )
        if workflow_id:
            await workflow_service.complete_workflow(workflow_id, review_id=result.get("review_id"))
    except Exception:
        logger.exception("Background review failed for %s/%s#%s", owner, repo, number)
        if "workflow_id" in locals() and workflow_id:
            await workflow_service.fail_workflow(workflow_id, error="Background review failed")