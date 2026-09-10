import time

import jwt as pyjwt

from app.services.config import settings
from app.services.jwt_service import create_access_token, decode_access_token

PROTECTED_PATHS = ["/repositories", "/pullrequests", "/dashboard", "/history"]


def _auth(token: str):
    return {"Authorization": f"Bearer {token}"}


def test_protected_endpoints_reject_missing_token(client):
    for path in PROTECTED_PATHS:
        resp = client.get(path)
        assert resp.status_code == 401, path
        assert resp.json()["detail"] == "Not authenticated"


def test_protected_endpoints_reject_invalid_token(client):
    for path in PROTECTED_PATHS:
        resp = client.get(path, headers=_auth("not-a-real-token"))
        assert resp.status_code == 401, path
        assert resp.json()["detail"] == "Could not validate credentials"


def test_protected_endpoints_reject_expired_token(client):
    expired = pyjwt.encode(
        {"sub": "42", "login": "octocat", "iat": 0, "exp": int(time.time()) - 100},
        settings.JWT_SECRET,
        algorithm="HS256",
    )
    for path in PROTECTED_PATHS:
        resp = client.get(path, headers=_auth(expired))
        assert resp.status_code == 401, path
        assert resp.json()["detail"] == "Token has expired"


def test_protected_endpoints_reject_token_for_unknown_user(client, monkeypatch):
    async def no_user(github_id):
        return None

    monkeypatch.setattr("app.services.security.get_user_by_github_id", no_user)
    token = create_access_token({"sub": "42", "login": "ghost"})
    for path in PROTECTED_PATHS:
        resp = client.get(path, headers=_auth(token))
        assert resp.status_code == 401, path
        assert resp.json()["detail"] == "User no longer exists"


def test_protected_endpoints_allow_known_user_to_reach_dashboard(client, monkeypatch, fake_db):
    async def known_user(github_id):
        return {"github_id": github_id, "login": "octocat", "github_access_token": "gho_secret"}

    monkeypatch.setattr("app.services.security.get_user_by_github_id", known_user)
    token = create_access_token({"sub": "42", "login": "octocat"})

    # Auth passes and the dashboard endpoints resolve (empty DB -> zero structures).
    resp = client.get("/dashboard", headers=_auth(token))
    assert resp.status_code == 200, resp.text

    resp = client.get("/history", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["items"] == []


def test_token_does_not_contain_github_access_token():
    user_doc = {"github_id": 42, "login": "octocat", "github_access_token": "gho_should_never_be_in_jwt"}
    token = create_access_token({"sub": str(user_doc["github_id"]), "login": user_doc["login"]})
    payload = decode_access_token(token)
    assert "github_access_token" not in payload
    assert payload["sub"] == "42"