import pytest

from app.services import user_repository


class FakeUsers:
    def __init__(self):
        self.docs: dict = {}

    async def create_index(self, *args, **kwargs):
        return None

    async def update_one(self, filter_doc, update, upsert=False):
        github_id = filter_doc["github_id"]
        settable = update["$set"]
        if github_id in self.docs:
            self.docs[github_id].update(settable)
        else:
            self.docs[github_id] = {**filter_doc, **settable, **update["$setOnInsert"]}
        return None

    async def find_one(self, filter_doc):
        return self.docs.get(filter_doc["github_id"])


class FakeDb:
    def __init__(self):
        self.users = FakeUsers()

    def __getitem__(self, name):
        return getattr(self, name)


@pytest.mark.asyncio
async def test_upsert_creates_new_user(monkeypatch):
    fake_db = FakeDb()
    monkeypatch.setattr("app.services.user_repository.get_db", lambda: fake_db)

    profile = {"id": 123, "login": "octocat", "name": "Octo Cat", "email": "octo@example.com", "avatar_url": "https://avatars/1"}
    await user_repository.upsert_github_user(profile, "gho_token_secret")

    doc = fake_db.users.docs[123]
    assert doc["login"] == "octocat"
    assert doc["github_access_token"] == "gho_token_secret"
    assert doc["created_at"] is not None


@pytest.mark.asyncio
async def test_upsert_updates_existing_user(monkeypatch):
    fake_db = FakeDb()
    monkeypatch.setattr("app.services.user_repository.get_db", lambda: fake_db)

    await user_repository.upsert_github_user({"id": 123, "login": "octocat"}, "token1")
    await user_repository.upsert_github_user({"id": 123, "login": "octocat2"}, "token2")

    doc = fake_db.users.docs[123]
    assert doc["login"] == "octocat2"
    assert doc["github_access_token"] == "token2"
    assert doc["created_at"] is not None


@pytest.mark.asyncio
async def test_upsert_requires_github_id(monkeypatch):
    fake_db = FakeDb()
    monkeypatch.setattr("app.services.user_repository.get_db", lambda: fake_db)

    with pytest.raises(ValueError):
        await user_repository.upsert_github_user({"login": "no-id"}, "token")


def test_to_safe_user_never_includes_access_token():
    user = {
        "github_id": 1,
        "login": "alice",
        "github_access_token": "gho_super_secret",
        "created_at": "x",
        "updated_at": "y",
    }
    safe = user_repository.to_safe_user(user)
    assert "github_access_token" not in safe
    assert safe["login"] == "alice"
    assert safe["github_id"] == 1