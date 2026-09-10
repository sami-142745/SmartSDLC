from __future__ import annotations

import logging
from urllib.parse import urlencode

import httpx
from fastapi.responses import RedirectResponse

from app.services import user_repository
from app.services.config import settings
from app.services.oauth_state import create_state, verify_state

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_API_BASE = "https://api.github.com"
GITHUB_API_HEADERS = {"Accept": "application/vnd.github+json"}

logger = logging.getLogger(__name__)


class OAuthError(Exception):
    pass


def _new_http_client(**kwargs) -> httpx.AsyncClient:
    return httpx.AsyncClient(**kwargs)


class GithubOAuth:
    def get_authorization_redirect(self) -> RedirectResponse:
        params = {
            "client_id": settings.GITHUB_CLIENT_ID,
            "redirect_uri": settings.GITHUB_OAUTH_CALLBACK_URL,
            "scope": "read:user repo",
            "state": create_state(settings.JWT_SECRET),
        }
        url = f"{GITHUB_AUTHORIZE_URL}?{urlencode(params)}"
        return RedirectResponse(url)

    async def exchange_code_for_token(self, code: str) -> str:
        payload = {
            "client_id": settings.GITHUB_CLIENT_ID,
            "client_secret": settings.GITHUB_CLIENT_SECRET,
            "code": code,
            "redirect_uri": settings.GITHUB_OAUTH_CALLBACK_URL,
        }
        headers = {**GITHUB_API_HEADERS, "Accept": "application/json"}
        try:
            async with _new_http_client(timeout=10) as client:
                resp = await client.post(GITHUB_TOKEN_URL, data=payload, headers=headers)
        except httpx.HTTPError:
            logger.exception("GitHub token exchange failed")
            raise OAuthError("Could not reach GitHub during token exchange")

        if resp.status_code != 200:
            raise OAuthError("GitHub rejected the authorization code")

        data = resp.json()
        access_token = data.get("access_token")
        if not access_token:
            raise OAuthError("GitHub token exchange did not return an access token")
        return access_token

    async def fetch_user_profile(self, access_token: str) -> dict:
        headers = {"Authorization": f"Bearer {access_token}", **GITHUB_API_HEADERS}
        try:
            async with _new_http_client(timeout=10) as client:
                resp = await client.get(f"{GITHUB_API_BASE}/user", headers=headers)
        except httpx.HTTPError:
            logger.exception("GitHub user profile fetch failed")
            raise OAuthError("Could not reach GitHub while fetching the user profile")

        if resp.status_code != 200:
            raise OAuthError("GitHub could not authenticate the user")

        profile = resp.json()
        if not profile.get("id"):
            raise OAuthError("GitHub user profile is missing an id")
        return profile

    async def handle_callback(self, code: str, state: str | None) -> dict[str, object]:
        if not verify_state(state, settings.JWT_SECRET):
            raise OAuthError("Invalid or expired OAuth state")

        access_token = await self.exchange_code_for_token(code)
        profile = await self.fetch_user_profile(access_token)
        user = await user_repository.upsert_github_user(profile, access_token)
        return user_repository.to_safe_user(user)


github_oauth = GithubOAuth()