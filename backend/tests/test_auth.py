from app.services.github_oauth import OAuthError
from app.services.config import settings


def test_login_redirects_to_github(client, monkeypatch):
    monkeypatch.setattr(settings, "GITHUB_CLIENT_ID", "cid-123")

    resp = client.get("/auth/github/login", follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert "client_id=cid-123" in resp.headers["location"]


async def _fake_handle_callback(code, state):
    return {
        "github_id": 42,
        "login": "octocat",
        "name": "Octo Cat",
        "email": "octo@example.com",
        "avatar_url": "https://avatars.example.com/1",
        "created_at": None,
        "updated_at": None,
    }


def test_callback_success_returns_token_and_user(client, monkeypatch):
    monkeypatch.setattr("app.routers.auth.github_oauth.handle_callback", _fake_handle_callback)
    resp = client.get("/auth/github/callback?code=abc&state=valid.state.value?sig")
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["user"]["login"] == "octocat"
    assert body["user"]["github_id"] == 42
    assert "github_access_token" not in str(body)


def test_callback_error_returns_401(client, monkeypatch):
    async def failing(code, state):
        raise OAuthError("Invalid or expired OAuth state")

    monkeypatch.setattr("app.routers.auth.github_oauth.handle_callback", failing)
    resp = client.get("/auth/github/callback?code=abc&state=nope")
    assert resp.status_code == 401
    assert "Invalid or expired OAuth state" in resp.json()["detail"]


def test_login_endpoint_removed(client):
    resp = client.post("/auth/login", json={"username": "octocat", "password": "pw"})
    assert resp.status_code == 404