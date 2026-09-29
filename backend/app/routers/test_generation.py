"""HTTP surface for the Test Generation Engine.

Authentication
--------------
Every route requires a signed-in user (``get_current_user``) and a connected SCM
token (``require_github_token``), because generation reads live provider content.

Ownership
---------
A repository belongs to whichever SCM account the token belongs to. Generation
reads through that token, so a user cannot generate against a repository their
token cannot read. Cached results are keyed by ``user_id``, so one user's cache is
never returned to another.

Nothing is written
------------------
There is no route, and no SCM client method, that writes a generated file to a
repository. This is a preview: the response is a set of proposed files with the
evidence behind them, and a person copies what they want. That is a deliberate
limitation, not a missing feature — an endpoint that commits model-written code to
a user's repository is the kind of thing that must be a separate, explicit,
audited action, and it is not in this release.

Route registration
------------------
Mounted twice by :mod:`app.main`: at the root, matching every other router here,
and under ``/api``, matching the documented public contract. Both registrations
hit the same handlers.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.schemas.test_generation import (
    MAX_TARGETS,
    TestGeneration,
    TestTarget,
    GeneratedTestFile,
    TestLanguage,
    TestFramework,
    ValidationIssue,
)
from app.services import test_generation_service as generation_service
from app.services.scm import ScmAPIError, ScmProvider, scm_error_response
from app.services.security import get_current_user, require_github_token
from app.services.test_generation_service import TestGenerationError
from app.services.test_generator import GeneratedTestPayload

router = APIRouter()

BASE = "/test-generation"


@router.get(f"{BASE}/repositories/{{owner}}/{{repo}}", response_model=TestGeneration)
async def get_test_generation(
    owner: str,
    repo: str,
    provider: ScmProvider = Query(ScmProvider.github),
    ref: str | None = Query(None),
    refresh: bool = Query(False),
    max_files: int | None = Query(None, ge=1, le=generation_service.HARD_MAX_FILES),
    max_targets: int = Query(generation_service.DEFAULT_MAX_TARGETS, ge=1, le=MAX_TARGETS),
    user: dict[str, Any] = Depends(get_current_user),
    token: str = Depends(require_github_token),
) -> TestGeneration:
    """Untested public symbols and proposed tests for a repository.

    Results are cached. ``refresh=true`` recomputes and replaces the entry, which
    is what a user wants after pushing new code or new tests.

    A repository with no test suite is a ``200`` whose targets all carry the
    ``no_test_suite`` reason — not a 404, and not an invented coverage number.
    "Nothing is tested yet" is a result the page can explain.

    Every returned file is a preview. Nothing is written to the repository.
    """
    try:
        return await generation_service.get_test_generation(
            user["github_id"],
            token,
            provider,
            owner,
            repo,
            ref=ref,
            max_files=max_files,
            max_targets=max_targets,
            refresh=refresh,
        )
    except TestGenerationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ScmAPIError as exc:
        raise scm_error_response(provider, exc)


@router.post(f"{BASE}/repositories/{{owner}}/{{repo}}/validate", response_model=GeneratedTestFile)
async def validate_test_file(
    owner: str,
    repo: str,
    file_path: str = Query(...),
    language: str = Query(...),
    framework: str = Query(...),
    targets: list[TestTarget] = [],
    source: str = "",
    provider: ScmProvider = Query(ScmProvider.github),
    user: dict[str, Any] = Depends(get_current_user),
    token: str = Depends(require_github_token),
) -> GeneratedTestFile:
    """Validate a generated or user-edited test file without caching.

    Returns the validated file with screening issues. Does not persist.
    """
    try:
        validated, _ = await generation_service.validate_generated_test(
            user["github_id"],
            token,
            provider,
            owner,
            repo,
            file_path=file_path,
            language=language,
            framework=framework,
            targets=targets,
            source=source,
        )
        return validated
    except TestGenerationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ScmAPIError as exc:
        raise scm_error_response(provider, exc)


@router.post(f"{BASE}/repositories/{{owner}}/{{repo}}/regenerate", response_model=GeneratedTestFile)
async def regenerate_test_file(
    owner: str,
    repo: str,
    file_path: str = Query(...),
    language: str = Query(...),
    framework: str = Query(...),
    targets: list[TestTarget] = [],
    source_content: str = "",
    provider: ScmProvider = Query(ScmProvider.github),
    user: dict[str, Any] = Depends(get_current_user),
    token: str = Depends(require_github_token),
) -> GeneratedTestFile:
    """Regenerate a single test file for the given targets.

    Returns the regenerated file. Does not modify the cached report.
    """
    try:
        regenerated = await generation_service.regenerate_single_test_file(
            user["github_id"],
            token,
            provider,
            owner,
            repo,
            file_path=file_path,
            language=language,
            framework=framework,
            targets=targets,
            source_content=source_content,
        )
        return regenerated
    except TestGenerationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ScmAPIError as exc:
        raise scm_error_response(provider, exc)
