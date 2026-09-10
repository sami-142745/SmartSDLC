from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.github_oauth import OAuthError, github_oauth
from app.services.jwt_service import create_access_token

router = APIRouter()


class UserSummary(BaseModel):
    github_id: int
    login: str
    name: str | None = None
    email: str | None = None
    avatar_url: str | None = None


class AuthResponse(BaseModel):
    access_token: str
    user: UserSummary


@router.get("/github/login")
def github_login():
    return github_oauth.get_authorization_redirect()


@router.get("/github/callback", response_model=AuthResponse)
async def github_callback(code: str, state: str | None = None):
    try:
        user = await github_oauth.handle_callback(code=code, state=state)
    except OAuthError as e:
        raise HTTPException(status_code=401, detail=str(e))

    jwt = create_access_token({"sub": str(user["github_id"]), "login": user["login"]})
    return {"access_token": jwt, "user": user}


@router.post("/login")
def login(payload: dict):
    raise HTTPException(501, "Use /auth/github/callback")