def test_health_degraded_when_db_unavailable(client, monkeypatch):
    async def fake_ping_false():
        return False

    monkeypatch.setattr("app.routers.health.ping_db", fake_ping_false)

    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["database"] == "unavailable"


def test_health_ok_when_db_available(client, monkeypatch):
    async def fake_ping_true():
        return True

    monkeypatch.setattr("app.routers.health.ping_db", fake_ping_true)

    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"
    assert body["version"] == "0.1.0"


def test_existing_routes_still_registered(client):
    login = client.get("/auth/github/login", follow_redirects=False)
    assert login.status_code in (302, 307)  # RedirectResponse default is 307
    assert login.headers["location"].startswith("https://github.com/login/oauth/authorize?")
    assert client.get("/dashboard").status_code == 401
    assert client.get("/history").status_code == 401