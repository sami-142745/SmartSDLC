"""HTTP surface for the Dependency & Supply Chain Intelligence Engine.

Authentication
--------------
Every route requires a signed-in user (``get_current_user``) and a connected SCM
token (``require_github_token``), because analysing a repository reads live
provider content.

Ownership
---------
A repository belongs to whichever SCM account the token belongs to. Analysis
reads through that token, so a user cannot analyse a repository their token
cannot read. Cached reports are keyed by ``user_id``, so one user's cache is
never returned to another.

Route registration
------------------
Mounted twice by :mod:`app.main`: at the root, matching every other router here,
and under ``/api``, matching the documented public contract. Both registrations
hit the same handlers.

Scope note
----------
This engine reports supply-chain *hygiene*: licences, pinning, reproducibility
and the direct/transitive split. It does not report known vulnerabilities; that
is the security engine's job, and duplicating the advisory feed here would
produce two findings for one weakness.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.schemas.supply_chain import SupplyChainReport
from app.services import supply_chain_service
from app.services.scm import ScmAPIError, ScmProvider, scm_error_response
from app.services.security import get_current_user, require_github_token
from app.services.supply_chain_service import SupplyChainError

router = APIRouter()

BASE = "/supply-chain"


@router.get(f"{BASE}/repositories/{{owner}}/{{repo}}", response_model=SupplyChainReport)
async def get_supply_chain(
    owner: str,
    repo: str,
    provider: ScmProvider = Query(ScmProvider.github),
    ref: str | None = Query(None),
    refresh: bool = Query(False),
    max_dependencies: int | None = Query(
        None, ge=1, le=supply_chain_service.HARD_MAX_DEPENDENCIES
    ),
    user: dict[str, Any] = Depends(get_current_user),
    token: str = Depends(require_github_token),
) -> SupplyChainReport:
    """Dependency inventory, licence rollup, and supply-chain issues.

    Results are cached. ``refresh=true`` recomputes and replaces the entry, which
    is what a user wants after changing a manifest or lockfile.

    A repository with no dependency manifests is a ``200`` with the expected
    manifests reported as absent — not a 404. "This project declares no
    external dependencies" is a result the page can explain.
    """
    try:
        return await supply_chain_service.get_supply_chain(
            user["github_id"],
            token,
            provider,
            owner,
            repo,
            ref=ref,
            max_dependencies=max_dependencies,
            refresh=refresh,
        )
    except SupplyChainError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ScmAPIError as exc:
        raise scm_error_response(provider, exc)
