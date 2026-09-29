"""HTTP surface for the Documentation Intelligence Engine.

Authentication
--------------
Every route requires a signed-in user (``get_current_user``) and a connected SCM
token (``require_github_token``), because analysing a repository reads live
provider content.

Ownership
---------
A repository belongs to whichever SCM account the token belongs to. Analysis
reads through that token, so a user cannot analyse a repository their token
cannot read. Cached reports are keyed by ``user_id``, so one user's cache is never
returned to another.

Route registration
------------------
Mounted twice by :mod:`app.main`: at the root, matching every other router here,
and under ``/api``, matching the documented public contract. Both registrations
hit the same handlers.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.schemas.documentation_intelligence import DocumentationIntelligence
from app.services import documentation_intelligence_service as docs_service
from app.services.documentation_intelligence_service import DocumentationIntelligenceError
from app.services.scm import ScmAPIError, ScmProvider, scm_error_response
from app.services.security import get_current_user, require_github_token

router = APIRouter()

BASE = "/documentation-intelligence"


@router.get(f"{BASE}/repositories/{{owner}}/{{repo}}", response_model=DocumentationIntelligence)
async def get_documentation_intelligence(
    owner: str,
    repo: str,
    provider: ScmProvider = Query(ScmProvider.github),
    ref: str | None = Query(None),
    refresh: bool = Query(False),
    max_files: int | None = Query(None, ge=1, le=docs_service.HARD_MAX_FILES),
    user: dict[str, Any] = Depends(get_current_user),
    token: str = Depends(require_github_token),
) -> DocumentationIntelligence:
    """Documentation assets, coverage, gaps and summary for a repository.

    Results are cached. ``refresh=true`` recomputes and replaces the entry, which
    is what a user wants after pushing documentation changes.

    A repository with no documentation is a ``200`` with an empty asset list and
    gaps explaining what is missing — not a 404. "Nothing documented yet" is a
    result the page can explain.
    """
    try:
        return await docs_service.get_documentation_intelligence(
            user["github_id"],
            token,
            provider,
            owner,
            repo,
            ref=ref,
            max_files=max_files,
            refresh=refresh,
        )
    except DocumentationIntelligenceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ScmAPIError as exc:
        raise scm_error_response(provider, exc)
