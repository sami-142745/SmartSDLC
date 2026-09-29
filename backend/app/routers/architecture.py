"""HTTP surface for the Architecture Intelligence Engine.

Authentication
--------------
Every route requires a signed-in user (``get_current_user``) and a connected SCM
token (``require_github_token``), because analysing a repository reads live
provider content. There is no token-free architecture read: unlike a stored
security scan, a graph is always recomputed from the provider, so it can never be
served without a token.

Ownership
---------
A repository belongs to whichever SCM account the token belongs to. Analysis
reads through that token, so a user cannot analyse a repository their token
cannot read. Cached graphs are keyed by ``user_id``, so one user's cache is never
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

from app.schemas.architecture import ArchitectureGraph
from app.services import architecture_service
from app.services.architecture_service import ArchitectureError
from app.services.scm import ScmAPIError, ScmProvider, scm_error_response
from app.services.security import get_current_user, require_github_token

router = APIRouter()

BASE = "/architecture"


@router.get(f"{BASE}/repositories/{{owner}}/{{repo}}", response_model=ArchitectureGraph)
async def get_architecture_graph(
    owner: str,
    repo: str,
    provider: ScmProvider = Query(ScmProvider.github),
    ref: str | None = Query(None),
    refresh: bool = Query(False),
    max_files: int | None = Query(None, ge=1, le=architecture_service.HARD_MAX_FILES),
    user: dict[str, Any] = Depends(get_current_user),
    token: str = Depends(require_github_token),
) -> ArchitectureGraph:
    """The dependency graph, module inventory, issues and summary for a repository.

    Results are cached. ``refresh=true`` recomputes and replaces the entry, which
    is what a user wants after pushing new code.

    A repository with no analysable source is a ``200`` with an empty graph and
    ``truncated`` reflecting whether the file cap was hit — not a 404. "Nothing
    to analyse" is a result the page can explain.
    """
    try:
        return await architecture_service.get_architecture(
            user["github_id"],
            token,
            provider,
            owner,
            repo,
            ref=ref,
            max_files=max_files,
            refresh=refresh,
        )
    except ArchitectureError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ScmAPIError as exc:
        raise scm_error_response(provider, exc)
