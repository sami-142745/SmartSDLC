import httpx
import pytest

from app.services import user_repository
from app.services.config import settings
from app.services.github_oauth import OAuthError, github_oauth
from app.services.oauth_state import create_state


def _client_with(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=10)


def _install_mock_client(monkeypatch, handler):
    monkeypatch.setattr(
        "app.services.github_oauth._new_http_client",
        lambda **kw: _client_with(handler),
    )


def _valid_state(secret: str = "sec") -> str:
    return create_state(secret, ttl_seconds=600)


@pytest.fixture
def oauth_settings(monkeypatch):
    monkeypatch.setattr(settings, "GITHUB_CLIENT_ID", "cid-123")
    monkeypatch.setattr(settings, "GITHUB_CLIENT_SECRET", "cs-456")
    monkeypatch.setattr(settings, "GITHUB_OAUTH_CALLBACK_URL", "http://localhost:8000/auth/github/callback")


def test_authorization_redirect_contains_expected_params(oauth_settings):
    resp = github_oauth.get_authorization_redirect()
    url = resp.headers["location"]
    assert url.startswith("https://github.com/login/oauth/authorize?")
    assert "client_id=cid-123" in url
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fauth%2Fgithub%2Fcallback" in url
    assert "scope=read%3Auser+repo" in url
    assert "state=" in url


@pytest.mark.asyncio
async def test_exchange_code_for_token_returns_token(monkeypatch, oauth_settings):
    def handler(request):
        assert request.url == "https://github.com/login/oauth/access_token"
        assert b"code=abc" in request.content
        assert b"client_secret=cs-456" in request.content
        return httpx.Response(200, json={"access_token": "gho_live_token", "scope": "repo"})

    _install_mock_client(monkeypatch, handler)
    token = await github_oauth.exchange_code_for_token("abc")
    assert token == "gho_live_token"


@pytest.mark.asyncio
async def test_exchange_rejects_non_200(monkeypatch, oauth_settings):
    def handler(request):
        return httpx.Response(400, json={"error": "bad_verification_code"})

    _install_mock_client(monkeypatch, handler)
    with pytest.raises(OAuthError):
        await github_oauth.exchange_code_for_token("abc")


@pytest.mark.asyncio
async def test_exchange_rejects_missing_token(monkeypatch, oauth_settings):
    def handler(request):
        return httpx.Response(200, json={"error": "invalid_grant"})

    _install_mock_client(monkeypatch, handler)
    with pytest.raises(OAuthError):
        await github_oauth.exchange_code_for_token("abc")


@pytest.mark.asyncio
async def test_exchange_handles_connection_error(monkeypatch, oauth_settings):
    def handler(request):
        raise httpx.ConnectError("boom")

    _install_mock_client(monkeypatch, handler)
    with pytest.raises(OAuthError):
        await github_oauth.exchange_code_for_token("abc")


@pytest.mark.asyncio
async def test_fetch_user_profile_returns_profile(monkeypatch, oauth_settings):
    def handler(request):
        assert request.headers["authorization"] == "Bearer gho_live_token"
        assert request.url == "https://api.github.com/user"
        return httpx.Response(200, json={"id": 42, "login": "octocat", "name": "Octo Cat"})

    _install_mock_client(monkeypatch, handler)
    profile = await github_oauth.fetch_user_profile("gho_live_token")
    assert profile["login"] == "octocat"


@pytest.mark.asyncio
async def test_fetch_user_profile_rejects_non_200(monkeypatch, oauth_settings):
    def handler(request):
        return httpx.Response(401, json={"message": "Bad credentials"})

    _install_mock_client(monkeypatch, handler)
    with pytest.raises(OAuthError):
        await github_oauth.fetch_user_profile("gho_bad")


@pytest.mark.asyncio
async def test_handle_callback_success(monkeypatch, oauth_settings):
    monkeypatch.setattr(settings, "JWT_SECRET", "sec")

    async def fake_exchange(code):
        return "gho_live_token"

    async def fake_fetch(token):
        return {"id": 42, "login": "octocat", "name": "Octo Cat", "avatar_url": None, "email": None}

    async def fake_upsert(profile, token):
        return {
            "github_id": 42,
            "login": "octocat",
            "name": "Octo Cat",
            "avatar_url": None,
            "email": None,
            "github_access_token": token,
            "created_at": None,
            "updated_at": None,
        }

    monkeypatch.setattr(github_oauth, "exchange_code_for_token", fake_exchange)
    monkeypatch.setattr(github_oauth, "fetch_user_profile", fake_fetch)
    monkeypatch.setattr(user_repository, "upsert_github_user", fake_upsert)

    user = await github_oauth.handle_callback(code="abc", state=_valid_state("sec"))
    assert user["login"] == "octocat"
    assert "github_access_token" not in user


@pytest.mark.asyncio
async def test_handle_callback_rejects_invalid_state(oauth_settings, monkeypatch):
    monkeypatch.setattr(settings, "JWT_SECRET", "sec")
    with pytest.raises(OAuthError):
        await github_oauth.handle_callback(code="abc", state="forged.state.value")