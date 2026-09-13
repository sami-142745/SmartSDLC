from __future__ import annotations

import logging
import time
from typing import Any

from app.services import document_repository
from app.services.config import settings
from app.services.document_repository import DOCUMENT_SECTIONS
from app.services.gemini_service import GeminiUnavailable, generate_code_documentation
from app.services.github_client import GitHubAPIError, GitHubClient
from app.services.sanitize import redact_secrets

logger = logging.getLogger(__name__)

STATUS_COMPLETE = "complete"
STATUS_FAILED = "failed"

_EXCLUDED_DIRS = {
    "node_modules",
    "vendor",
    "dist",
    "build",
    "out",
    "coverage",
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    ".next",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    "target",
}

_EXCLUDED_FILENAMES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "Pipfile.lock",
    "npm-shrinkwrap.json",
    "composer.lock",
    "Cargo.lock",
}

_BINARY_SUFFIXES = (
    ".min.js",
    ".map",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".pdf",
    ".lock",
)


class DocumentGenerationError(Exception):
    pass


def _is_generated_file(path: str) -> bool:
    parts = path.split("/")
    if any(part in _EXCLUDED_DIRS for part in parts):
        return True
    name = parts[-1].lower()
    return name in _EXCLUDED_FILENAMES or name.endswith(_BINARY_SUFFIXES)


def _score_path(path: str) -> int:
    name = path.rsplit("/", 1)[-1].lower()
    if name in ("readme.md", "readme.rst", "readme.markdown", "readme"):
        return 110
    if name == "package.json":
        return 90
    if name in (
        "pyproject.toml",
        "setup.py",
        "requirements.txt",
        "app.py",
        "main.py",
        "server.py",
        "wsgi.py",
        "asgi.py",
        "manage.py",
        "index.ts",
        "index.tsx",
        "main.ts",
        "main.tsx",
        "vite.config.ts",
        "vite.config.js",
        "next.config.js",
        "tsconfig.json",
        "dockerfile",
        "docker-compose.yml",
        "docker-compose.yaml",
        "cargo.toml",
        "go.mod",
        "pom.xml",
        "build.gradle",
        "Gemfile",
        "composer.json",
    ):
        return 80
    if path.startswith(("src/", "app/", "backend/", "frontend/", "lib/", "core/", "server/", "internal/")):
        return 40
    if name.endswith((".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".rb", ".php", ".cs", ".kt")):
        return 20
    if name.endswith((".md", ".rst", ".txt")):
        return 15
    return 5


def _select_source_paths(tree: dict[str, Any], limit: int) -> list[str]:
    entries = tree.get("tree") or []
    paths = [
        entry.get("path")
        for entry in entries
        if entry.get("type") == "blob" and entry.get("path") and not _is_generated_file(entry["path"])
    ]
    paths.sort(key=_score_path, reverse=True)
    return paths[:limit]


async def _fetch_file_contents(
    github: GitHubClient,
    owner: str,
    repository: str,
    paths: list[str],
    branch: str | None,
) -> list[dict[str, str]]:
    files: list[dict[str, str]] = []
    total = 0
    for path in paths:
        try:
            content = await github.get_file_content(owner, repository, path, ref=branch)
        except GitHubAPIError:
            continue
        content = redact_secrets(content)
        content = content[: settings.DOC_MAX_FILE_CHARS]
        if not content.strip():
            continue
        files.append({"path": path, "code": content})
        total += len(content)
        if total >= settings.DOC_MAX_CODE_CHARS:
            break
    return files


def _documentation_context(
    repo: dict[str, Any],
    owner: str,
    repository: str,
    files: list[dict[str, str]],
    pull_request: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "repository": f"{owner}/{repository}",
        "description": repo.get("description"),
        "default_branch": repo.get("default_branch"),
        "pull_request_number": (pull_request or {}).get("number"),
        "pull_request_title": (pull_request or {}).get("title"),
        "files": files,
    }


def to_documentation_response(doc: dict[str, Any]) -> dict[str, Any]:
    pull_request_number = doc.get("pull_request_number")
    commit_sha = doc.get("commit_sha")
    default_branch = doc.get("default_branch")
    return {
        "id": str(doc.get("_id")),
        "title": doc.get("title") or "Untitled documentation",
        "summary": doc.get("summary") or "",
        "architecture": doc.get("architecture") or "",
        "modules": doc.get("modules") or [],
        "api": doc.get("api") or [],
        "changes": doc.get("changes") or [],
        "configuration": doc.get("configuration") or [],
        "security": doc.get("security") or [],
        "setup": doc.get("setup") or [],
        "source": {
            "repository": f"{doc.get('owner')}/{doc.get('repository')}",
            "owner": doc.get("owner") or "",
            "pull_request": f"#{pull_request_number}" if pull_request_number else None,
            "commit": commit_sha,
            "branch": default_branch,
        },
        "model": doc.get("model"),
        "status": doc.get("status", STATUS_COMPLETE),
        "error": doc.get("error"),
        "duration_ms": doc.get("duration_ms"),
        "generated_at": doc.get("created_at"),
    }


async def generate_documentation(
    github: GitHubClient,
    owner: str,
    repository: str,
    *,
    pull_request: int | None = None,
    user_id: int | None = None,
) -> dict[str, Any]:
    started = time.monotonic()

    try:
        repo = await github.get_repository(owner, repository)
        pull_request_data: dict[str, Any] | None = None
        commit_sha: str | None = None
        pull_request_title: str | None = None
        if pull_request is not None:
            pull_request_data = await github.get_pull_request(owner, repository, pull_request)
            pull_request_title = pull_request_data.get("title")
            commit_sha = pull_request_data.get("head_sha") or (pull_request_data.get("head") or {}).get("sha")

        branch = repo.get("default_branch") or None
        paths = _select_source_paths(
            await github.get_repository_tree(owner, repository, ref=branch),
            settings.DOC_MAX_FILES,
        )
        files = await _fetch_file_contents(github, owner, repository, paths, branch)
        if not files:
            raise DocumentGenerationError("No analyzable source files found in this repository")
    except GitHubAPIError:
        raise

    context = _documentation_context(repo, owner, repository, files, pull_request_data)
    try:
        documentation = await generate_code_documentation(context)
    except GeminiUnavailable as exc:
        logger.warning("Documentation generation unavailable for %s/%s: %s", owner, repository, exc)
        raise DocumentGenerationError("Documentation generation failed: AI engine unavailable")

    payload = documentation.model_dump()
    duration_ms = int((time.monotonic() - started) * 1000)
    doc_id = await document_repository.save_document(
        user_id=user_id,
        owner=owner,
        repository=repository,
        pull_request_number=pull_request,
        pull_request_title=pull_request_title,
        commit_sha=commit_sha,
        default_branch=repo.get("default_branch"),
        documentation=payload,
        model=settings.GEMINI_MODEL,
        status=STATUS_COMPLETE,
        duration_ms=duration_ms,
    )
    saved: dict[str, Any] = {
        "_id": doc_id,
        "user_id": user_id,
        "owner": owner,
        "repository": repository,
        "pull_request_number": pull_request,
        "pull_request_title": pull_request_title,
        "commit_sha": commit_sha,
        "default_branch": repo.get("default_branch"),
        "model": settings.GEMINI_MODEL,
        "status": STATUS_COMPLETE,
        "error": None,
        "duration_ms": duration_ms,
        "created_at": None,
    }
    saved.update({"title": payload.get("title") or "Untitled documentation"})
    saved.update({section: payload.get(section) for section in DOCUMENT_SECTIONS})
    return to_documentation_response(saved)