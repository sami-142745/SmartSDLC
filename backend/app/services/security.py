from __future__ import annotations

import jwt as pyjwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from typing import Any

from app.services.jwt_service import decode_access_token
from app.services.user_repository import get_user_by_github_id

bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any]:
    if credentials is None:
        raise _unauthorized("Not authenticated")

    try:
        payload = decode_access_token(credentials.credentials)
    except pyjwt.ExpiredSignatureError:
        raise _unauthorized("Token has expired")
    except pyjwt.InvalidTokenError:
        raise _unauthorized("Could not validate credentials")

    sub = payload.get("sub")
    if sub is None:
        raise _unauthorized("Could not validate credentials")

    try:
        github_id = int(sub)
    except (TypeError, ValueError):
        raise _unauthorized("Could not validate credentials")

    user = await get_user_by_github_id(github_id)
    if user is None:
        raise _unauthorized("User no longer exists")

    return user


async def require_github_token(
    user: dict[str, Any] = Depends(get_current_user),
) -> str:
    token = user.get("github_access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="GitHub account is not connected",
        )
    return token