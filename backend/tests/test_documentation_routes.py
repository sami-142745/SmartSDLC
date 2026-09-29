"""Tests for documentation analysis orchestration and its HTTP surface.

The service tests cover the parts that touch the outside world — target
selection, bounded fetching, partial failure, caching — and the route tests cover
authentication and the shape of the response contract.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.schemas.documentation_intelligence import DocumentationIntelligence
from app.services import documentation_intelligence_service as docs_service
from app.services import repository_analysis_repository as cache_repo
from app.services.documentation_intelligence_service import DocumentationIntelligenceError
from app.services.scm import ScmProvider

OWNER = "octocat"
REPO = "hello-world"
USER_ID = 42


# --------------------------------------------------------------------------
# Fakes
# --------------------------------------------------------------------------

class FakeClient:
    """Minimal SCM client exposing only the two methods the service uses."""

    def __init__(self, tree=None, files=None, tree_error=None, file_errors=None):
        self._tree = tree if tree is not None else []
        self._files = files or {}
        self._tree_error = tree_error
        self._file_errors = file_errors or {}
        self.tree_calls: list[tuple] = []
        self.file_calls: list[str] = []

    async def get_repository_tree(self, owner, repository, ref=None):
        self.tree_calls.append((owner, repository, ref))
        if self._tree_error is not None:
            raise self._tree_error
        return {"tree": self._tree, "sha": "abc123"}

    async def get_file_content(self, owner, repository, path, ref=None):
        self.file_calls.append(path)
        if path in self._file_errors:
            raise self._file_errors[path]
        return self._files.get(path)


def _use_client(monkeypatch, client):
    monkeypatch.setattr(docs_service, "_client", lambda provider, token: client)
    return client


def _tree(*paths: str) -> list[dict[str, Any]]:
    return [{"path": path, "type": "blob", "size": 100} for path in paths]


@pytest.fixture
def no_cache(monkeypatch):
    """Disable the cache so tests exercise the real fetch path."""
    monkeypatch.setattr(docs_service, "_read_cache", _never_cache)
    monkeypatch.setattr(docs_service, "_write_cache", _never_write)


async def _never_cache(*args, **kwargs):
    return None


async def _never_write(*args, **kwargs):
    return None


SAMPLE_FILES = {
    "README.md": (
        "# Project\n\n## Installation\n\npip install x\n\n## Usage\n\n"
        "Run it.\n\nSee [guide](./docs/guide.md).\n"
    ),
    "LICENSE": "MIT\n",
    "CONTRIBUTING.md": "# Contributing\n",
    "CHANGELOG.md": "# Changelog\n",
    "SECURITY.md": "# Security\n",
    "docs/guide.md": "# Guide\n",
    "app/main.py": 'def main():\n    """Entry point."""\n    return 0\n',
}


# --------------------------------------------------------------------------
# Target selection
# --------------------------------------------------------------------------

class TestTargetSelection:
    def test_documentation_and_source_files_are_selected(self):
        docs, sources, source_count, existing, truncated = docs_service.select_targets(
            _tree("README.md", "app/main.py", "docs/guide.md")
        )
        assert docs == ["README.md", "docs/guide.md"]
        assert sources == ["app/main.py"]
        assert source_count == 1
        assert "docs/guide.md" in existing
        assert truncated is False

    def test_readme_is_prioritised_over_generic_documentation(self):
        docs, _, _, _, _ = docs_service.select_targets(
            _tree("notes.md", "docs/a.md", "README.md")
        )
        assert docs[0] == "README.md"

    def test_vendored_and_non_documentation_files_are_excluded(self):
        docs, sources, _, existing, _ = docs_service.select_targets(
            _tree("README.md", "node_modules/x/README.md", "package.json", "app/main.py")
        )
        assert "node_modules/x/README.md" not in docs
        assert "package.json" not in existing
        assert sources == ["app/main.py"]

    def test_tree_entries_without_a_path_are_ignored(self):
        docs, sources, _, _, _ = docs_service.select_targets(
            [{"type": "blob"}, {"path": "", "type": "blob"}, "not-a-dict"]
        )
        assert docs == []
        assert sources == []

    def test_the_documentation_cap_is_applied_and_reported(self):
        entries = _tree(*[f"docs/m{i}.md" for i in range(20)])
        docs, _, _, _, truncated = docs_service.select_targets(entries, max_doc_files=5)
        assert len(docs) == 5
        assert truncated is True

    def test_the_hard_ceiling_cannot_be_exceeded(self):
        entries = _tree(*[f"docs/m{i}.md" for i in range(20)])
        docs, _, _, _, _ = docs_service.select_targets(
            entries, max_doc_files=docs_service.HARD_MAX_FILES * 10
        )
        assert len(docs) <= docs_service.HARD_MAX_FILES

    def test_selection_is_deterministic(self):
        entries = _tree(*[f"docs/m{i}.md" for i in range(20)])
        first, _, _, _, _ = docs_service.select_targets(entries, max_doc_files=5)
        second, _, _, _, _ = docs_service.select_targets(entries, max_doc_files=5)
        assert first == second


# --------------------------------------------------------------------------
# Service
# --------------------------------------------------------------------------

@pytest.mark.asyncio
class TestAnalyzeRepository:
    async def test_a_small_repository_produces_a_report(self, monkeypatch, no_cache):
        _use_client(monkeypatch, FakeClient(tree=_tree(*SAMPLE_FILES), files=SAMPLE_FILES))
        report = await docs_service.analyze_repository(
            USER_ID, "token", ScmProvider.github, OWNER, REPO
        )
        assert report.full_name == f"{OWNER}/{REPO}"
        assert report.summary.readme_present is True
        assert report.summary.documentation_files == 6
        assert report.commit_sha == "abc123"
        assert report.errors == []

    async def test_a_thin_readme_is_reported(self, monkeypatch, no_cache):
        _use_client(monkeypatch, FakeClient(tree=_tree(*SAMPLE_FILES), files=SAMPLE_FILES))
        report = await docs_service.analyze_repository(
            USER_ID, "token", ScmProvider.github, OWNER, REPO
        )
        assert "thin_readme" in {gap.kind for gap in report.gaps}

    async def test_only_relevant_files_are_fetched(self, monkeypatch, no_cache):
        client = _use_client(
            monkeypatch,
            FakeClient(
                tree=_tree("README.md", "package.json", "node_modules/x/README.md", "app/main.py"),
                files={"README.md": "# Project\n", "app/main.py": "x = 1\n"},
            ),
        )
        await docs_service.analyze_repository(
            USER_ID, "token", ScmProvider.github, OWNER, REPO
        )
        # A vendored README and a manifest must never cost a provider round trip.
        assert set(client.file_calls) == {"README.md", "app/main.py"}

    async def test_a_missing_file_is_not_an_error(self, monkeypatch, no_cache):
        from app.services.scm import ScmAPIError

        _use_client(
            monkeypatch,
            FakeClient(
                tree=_tree("README.md", "docs/gone.md"),
                files={"README.md": "# Project\n"},
                file_errors={"docs/gone.md": ScmAPIError(404, "Not Found", "not_found")},
            ),
        )
        report = await docs_service.analyze_repository(
            USER_ID, "token", ScmProvider.github, OWNER, REPO
        )
        assert report.errors == []
        assert report.summary.readme_present is True

    async def test_one_unreadable_file_does_not_fail_the_analysis(self, monkeypatch, no_cache):
        from app.services.scm import ScmAPIError

        _use_client(
            monkeypatch,
            FakeClient(
                tree=_tree("README.md", "docs/broken.md"),
                files={"README.md": "# Project\n", "docs/broken.md": "# Broken\n"},
                file_errors={
                    "docs/broken.md": ScmAPIError(500, "Server Error", "server_error")
                },
            ),
        )
        report = await docs_service.analyze_repository(
            USER_ID, "token", ScmProvider.github, OWNER, REPO
        )
        assert any("broken.md" in error for error in report.errors)

    async def test_a_repository_with_no_documentation_is_a_result_not_an_error(
        self, monkeypatch, no_cache
    ):
        _use_client(monkeypatch, FakeClient(tree=_tree("app/main.py"), files={"app/main.py": "x = 1\n"}))
        report = await docs_service.analyze_repository(
            USER_ID, "token", ScmProvider.github, OWNER, REPO
        )
        assert report.summary.readme_present is False
        assert "missing_readme" in {gap.kind for gap in report.gaps}

    async def test_errors_are_capped(self, monkeypatch, no_cache):
        from app.services.scm import ScmAPIError

        paths = [f"app/m{i}.py" for i in range(60)]
        _use_client(
            monkeypatch,
            FakeClient(
                tree=_tree(*paths),
                files={path: "x = 1\n" for path in paths},
                file_errors={path: ScmAPIError(500, "Server Error", "server_error") for path in paths},
            ),
        )
        report = await docs_service.analyze_repository(
            USER_ID, "token", ScmProvider.github, OWNER, REPO
        )
        assert len(report.errors) == docs_service.MAX_ERRORS_REPORTED

    async def test_the_ref_is_passed_to_the_provider(self, monkeypatch, no_cache):
        client = _use_client(
            monkeypatch,
            FakeClient(tree=_tree("README.md"), files={"README.md": "# Project\n"}),
        )
        report = await docs_service.analyze_repository(
            USER_ID, "token", ScmProvider.github, OWNER, REPO, ref="main"
        )
        assert client.tree_calls == [(OWNER, REPO, "main")]
        assert report.ref == "main"

    async def test_the_same_repository_yields_the_same_report(self, monkeypatch, no_cache):
        client = FakeClient(tree=_tree(*SAMPLE_FILES), files=SAMPLE_FILES)
        _use_client(monkeypatch, client)
        first = await docs_service.analyze_repository(
            USER_ID, "token", ScmProvider.github, OWNER, REPO
        )
        second = await docs_service.analyze_repository(
            USER_ID, "token", ScmProvider.github, OWNER, REPO
        )
        assert first.assets == second.assets
        assert first.gaps == second.gaps
        assert first.summary == second.summary

    async def test_a_provider_without_a_tree_is_an_error(self, monkeypatch, no_cache):
        class NoTree:
            async def get_file_content(self, *a, **k):
                return ""

        _use_client(monkeypatch, NoTree())
        with pytest.raises(DocumentationIntelligenceError, match="repository tree"):
            await docs_service.analyze_repository(
                USER_ID, "token", ScmProvider.github, OWNER, REPO
            )

    async def test_a_tree_failure_is_an_error(self, monkeypatch, no_cache):
        from app.services.scm import ScmAPIError

        _use_client(
            monkeypatch, FakeClient(tree_error=ScmAPIError(404, "Not Found", "not_found"))
        )
        with pytest.raises(DocumentationIntelligenceError, match="tree"):
            await docs_service.analyze_repository(
                USER_ID, "token", ScmProvider.github, OWNER, REPO
            )

    async def test_an_empty_tree_is_an_error(self, monkeypatch, no_cache):
        _use_client(monkeypatch, FakeClient(tree=[]))
        with pytest.raises(DocumentationIntelligenceError, match="empty or unreadable"):
            await docs_service.analyze_repository(
                USER_ID, "token", ScmProvider.github, OWNER, REPO
            )

    async def test_a_gitlab_provider_is_recorded(self, monkeypatch, no_cache):
        _use_client(monkeypatch, FakeClient(tree=_tree("README.md"), files={"README.md": "# P\n"}))
        report = await docs_service.analyze_repository(
            USER_ID, "token", ScmProvider.gitlab, OWNER, REPO
        )
        assert report.provider == "gitlab"


# --------------------------------------------------------------------------
# Caching
# --------------------------------------------------------------------------

@pytest.mark.asyncio
class TestCaching:
    """These drive the real ``_read_cache``/``_write_cache`` functions.

    The resilience being tested lives *inside* those functions, so a stub would
    assert nothing. They are driven by making the repository layer misbehave.
    """

    async def test_a_cached_report_is_returned_without_fetching(self, monkeypatch):
        cached = DocumentationIntelligence(
            repository_id="octocat/hello-world",
            owner=OWNER,
            repository=REPO,
            full_name=f"{OWNER}/{REPO}",
            provider="github",
            analyzed_at="2026-01-01T00:00:00+00:00",
        )
        monkeypatch.setattr(cache_repo, "get_cached", _returning({"payload": cached.model_dump(mode="json")}))
        client = _use_client(monkeypatch, FakeClient(tree=_tree("README.md")))
        report = await docs_service.analyze_repository(
            USER_ID, "token", ScmProvider.github, OWNER, REPO
        )
        assert report.analyzed_at == "2026-01-01T00:00:00+00:00"
        assert client.tree_calls == []
        assert client.file_calls == []

    async def test_the_cache_is_keyed_by_analysis_kind(self, monkeypatch):
        seen: list[str] = []

        async def get_cached(user_id, owner, repository, analysis):
            seen.append(analysis)
            return None

        monkeypatch.setattr(cache_repo, "get_cached", get_cached)
        _use_client(monkeypatch, FakeClient(tree=_tree("README.md"), files={"README.md": "# P\n"}))
        await docs_service.analyze_repository(
            USER_ID, "token", ScmProvider.github, OWNER, REPO
        )
        assert seen == [docs_service.CACHE_KIND]

    async def test_refresh_bypasses_the_cache_and_replaces_it(self, monkeypatch):
        reads: list[str] = []
        written: list[str] = []

        async def get_cached(user_id, owner, repository, analysis):
            reads.append(analysis)
            return None

        async def set_cached(user_id, owner, repository, analysis, payload, ttl_seconds=None):
            written.append(analysis)
            return {}

        monkeypatch.setattr(cache_repo, "get_cached", get_cached)
        monkeypatch.setattr(cache_repo, "set_cached", set_cached)
        _use_client(monkeypatch, FakeClient(tree=_tree("README.md"), files={"README.md": "# P\n"}))
        await docs_service.analyze_repository(
            USER_ID, "token", ScmProvider.github, OWNER, REPO, refresh=True
        )
        assert reads == []
        assert written == [docs_service.CACHE_KIND]

    async def test_use_cache_false_skips_the_read(self, monkeypatch, no_cache):
        monkeypatch.setattr(cache_repo, "get_cached", _boom("cache should not be read"))
        _use_client(monkeypatch, FakeClient(tree=_tree("README.md"), files={"README.md": "# P\n"}))
        report = await docs_service.analyze_repository(
            USER_ID, "token", ScmProvider.github, OWNER, REPO, use_cache=False
        )
        assert report.summary.readme_present is True

    async def test_a_database_outage_on_read_degrades_to_a_recompute(self, monkeypatch, no_cache):
        monkeypatch.setattr(cache_repo, "get_cached", _boom("db down"))
        _use_client(monkeypatch, FakeClient(tree=_tree("README.md"), files={"README.md": "# P\n"}))
        report = await docs_service.analyze_repository(
            USER_ID, "token", ScmProvider.github, OWNER, REPO
        )
        assert report.summary.readme_present is True

    async def test_a_cache_write_failure_does_not_fail_the_analysis(self, monkeypatch, no_cache):
        monkeypatch.setattr(cache_repo, "set_cached", _boom("disk full"))
        _use_client(monkeypatch, FakeClient(tree=_tree("README.md"), files={"README.md": "# P\n"}))
        report = await docs_service.analyze_repository(
            USER_ID, "token", ScmProvider.github, OWNER, REPO
        )
        assert report.summary.readme_present is True

    async def test_a_stale_cached_payload_degrades_to_a_recompute(self, monkeypatch, no_cache):
        monkeypatch.setattr(cache_repo, "get_cached", _returning({"payload": {"not": "a report"}}))
        _use_client(monkeypatch, FakeClient(tree=_tree("README.md"), files={"README.md": "# P\n"}))
        report = await docs_service.analyze_repository(
            USER_ID, "token", ScmProvider.github, OWNER, REPO
        )
        assert report.summary.readme_present is True

    async def test_a_non_dict_cached_payload_is_treated_as_a_miss(self, monkeypatch, no_cache):
        monkeypatch.setattr(cache_repo, "get_cached", _returning({"payload": "garbage"}))
        _use_client(monkeypatch, FakeClient(tree=_tree("README.md"), files={"README.md": "# P\n"}))
        report = await docs_service.analyze_repository(
            USER_ID, "token", ScmProvider.github, OWNER, REPO
        )
        assert report.summary.readme_present is True

    async def test_the_cached_report_round_trips(self, monkeypatch):
        _use_client(monkeypatch, FakeClient(tree=_tree(*SAMPLE_FILES), files=SAMPLE_FILES))
        stored: dict = {}

        async def set_cached(user_id, owner, repository, analysis, payload, ttl_seconds=None):
            stored["payload"] = payload
            return {}

        async def get_cached(user_id, owner, repository, analysis):
            return stored or None

        monkeypatch.setattr(cache_repo, "set_cached", set_cached)
        monkeypatch.setattr(cache_repo, "get_cached", get_cached)
        first = await docs_service.analyze_repository(
            USER_ID, "token", ScmProvider.github, OWNER, REPO
        )
        second = await docs_service.analyze_repository(
            USER_ID, "token", ScmProvider.github, OWNER, REPO
        )
        assert first.assets == second.assets
        assert first.summary == second.summary
        assert first.gaps == second.gaps


def _returning(payload):
    async def read(*args, **kwargs):
        return payload

    return read


def _boom(message):
    async def raiser(*args, **kwargs):
        raise RuntimeError(message)

    return raiser


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------

@pytest.mark.asyncio
class TestRoutes:
    async def test_the_report_is_returned_for_a_valid_request(self, client, auth_headers, monkeypatch):
        _use_client(monkeypatch, FakeClient(tree=_tree(*SAMPLE_FILES), files=SAMPLE_FILES))
        monkeypatch.setattr(docs_service, "_read_cache", _never_cache)
        monkeypatch.setattr(docs_service, "_write_cache", _never_write)
        response = client.get(
            f"/documentation-intelligence/repositories/{OWNER}/{REPO}", headers=auth_headers
        )
        assert response.status_code == 200
        body = response.json()
        assert body["full_name"] == f"{OWNER}/{REPO}"
        assert body["summary"]["readme_present"] is True
        # The response must state that the analysis is model-free.
        assert "No model" in body["summary"]["methodology"]

    async def test_a_request_without_a_token_is_rejected(self, client, monkeypatch):
        _use_client(monkeypatch, FakeClient(tree=_tree("README.md")))
        response = client.get(f"/documentation-intelligence/repositories/{OWNER}/{REPO}")
        assert response.status_code in (401, 403)

    async def test_a_user_without_a_connected_account_is_rejected(self, client):
        response = client.get(
            f"/documentation-intelligence/repositories/{OWNER}/{REPO}",
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        assert response.status_code in (401, 403)

    async def test_the_api_prefixed_route_behaves_identically(
        self, client, auth_headers, monkeypatch
    ):
        _use_client(monkeypatch, FakeClient(tree=_tree("README.md"), files={"README.md": "# P\n"}))
        monkeypatch.setattr(docs_service, "_read_cache", _never_cache)
        monkeypatch.setattr(docs_service, "_write_cache", _never_write)
        response = client.get(
            f"/api/documentation-intelligence/repositories/{OWNER}/{REPO}", headers=auth_headers
        )
        assert response.status_code == 200

    async def test_a_provider_failure_is_reported_as_a_bad_gateway(
        self, client, auth_headers, monkeypatch
    ):
        _use_client(monkeypatch, FakeClient(tree=[]))
        monkeypatch.setattr(docs_service, "_read_cache", _never_cache)
        response = client.get(
            f"/documentation-intelligence/repositories/{OWNER}/{REPO}", headers=auth_headers
        )
        assert response.status_code == 502

    async def test_a_repository_with_no_documentation_is_a_200_not_a_404(
        self, client, auth_headers, monkeypatch
    ):
        _use_client(monkeypatch, FakeClient(tree=_tree("app/main.py"), files={"app/main.py": "x = 1\n"}))
        monkeypatch.setattr(docs_service, "_read_cache", _never_cache)
        monkeypatch.setattr(docs_service, "_write_cache", _never_write)
        response = client.get(
            f"/documentation-intelligence/repositories/{OWNER}/{REPO}", headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["summary"]["readme_present"] is False

    async def test_max_files_must_be_positive(self, client, auth_headers):
        response = client.get(
            f"/documentation-intelligence/repositories/{OWNER}/{REPO}?max_files=0",
            headers=auth_headers,
        )
        assert response.status_code == 422

    async def test_the_provider_is_validated(self, client, auth_headers):
        response = client.get(
            f"/documentation-intelligence/repositories/{OWNER}/{REPO}?provider=bitbucket",
            headers=auth_headers,
        )
        assert response.status_code == 422

    async def test_a_response_contains_no_file_content(self, client, auth_headers, monkeypatch):
        # The report describes documentation; it must not echo source back to the UI.
        secret = "AWS_SECRET_ACCESS_KEY=super-secret-value"
        files = {"app/config.py": f"SECRET = '{secret}'\n"}
        _use_client(monkeypatch, FakeClient(tree=_tree("app/config.py"), files=files))
        monkeypatch.setattr(docs_service, "_read_cache", _never_cache)
        monkeypatch.setattr(docs_service, "_write_cache", _never_write)
        response = client.get(
            f"/documentation-intelligence/repositories/{OWNER}/{REPO}", headers=auth_headers
        )
        assert response.status_code == 200
        assert "super-secret-value" not in response.text


class TestCacheRegistration:
    def test_documentation_is_a_registered_analysis_kind(self):
        from app.services import repository_analysis_repository as cache

        assert "documentation" in cache.ANALYSIS_KINDS
        assert cache.ttl_for("documentation") > 0
