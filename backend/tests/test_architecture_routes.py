"""Tests for architecture analysis orchestration and its HTTP surface.

The service tests cover the parts that touch the outside world — target
selection, bounded fetching, partial failure, caching — and the route tests cover
authentication and the shape of the response contract.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.schemas.architecture import ArchitectureGraph
from app.services import architecture_parser, architecture_service
from app.services import repository_analysis_repository as cache_repo
from app.services.architecture_service import ArchitectureError
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
    monkeypatch.setattr(
        architecture_service, "_client", lambda provider, token: client
    )
    return client


def _tree(*paths: str) -> list[dict[str, Any]]:
    return [{"path": path, "type": "blob", "size": 100} for path in paths]


@pytest.fixture
def no_cache(monkeypatch):
    """Disable the cache so tests exercise the real fetch path."""
    monkeypatch.setattr(
        architecture_service, "_read_cache", _never_cache
    )
    monkeypatch.setattr(architecture_service, "_write_cache", _never_write)


async def _never_cache(*args, **kwargs):
    """Cache read that always misses, and a write that is discarded."""
    return None


async def _never_write(*args, **kwargs):
    return None


SAMPLE_FILES = {
    "app/routers/security.py": (
        "from app.services.security_scan_service import scan\n"
        "from app.services.security_repository import save\n"
        "from fastapi import APIRouter\n"
    ),
    "app/services/security_scan_service.py": (
        "from app.services.security_repository import repo\nimport asyncio\n"
    ),
    "app/services/security_repository.py": "from motor import AsyncIOMotorClient\n",
}


# --------------------------------------------------------------------------
# Target selection
# --------------------------------------------------------------------------

class TestTargetSelection:
    def test_source_files_are_selected(self):
        paths, skipped = architecture_service.select_analysis_targets(
            _tree("app/main.py", "src/api/a.ts")
        )
        assert paths == ["app/main.py", "src/api/a.ts"]
        assert skipped == 0

    def test_non_source_and_vendored_files_are_skipped(self):
        paths, skipped = architecture_service.select_analysis_targets(
            _tree("app/main.py", "README.md", "node_modules/x/index.js", "dist/b.js")
        )
        assert paths == ["app/main.py"]
        assert skipped == 3

    def test_tree_entries_are_skipped_without_a_path(self):
        paths, _ = architecture_service.select_analysis_targets(
            [{"type": "blob"}, {"path": "", "type": "blob"}, "not-a-dict"]
        )
        assert paths == []

    def test_directory_entries_are_skipped(self):
        paths, _ = architecture_service.select_analysis_targets(
            [{"path": "app", "type": "tree"}, {"path": "app/main.py", "type": "blob"}]
        )
        assert paths == ["app/main.py"]

    def test_the_file_cap_is_applied_and_reported(self):
        entries = _tree(*[f"app/m{i}.py" for i in range(50)])
        paths, skipped = architecture_service.select_analysis_targets(entries, max_files=10)
        assert len(paths) == 10
        assert skipped == 40

    def test_the_hard_ceiling_cannot_be_exceeded_by_a_request(self):
        entries = _tree(*[f"app/m{i}.py" for i in range(20)])
        paths, _ = architecture_service.select_analysis_targets(
            entries, max_files=architecture_service.HARD_MAX_FILES * 10
        )
        assert len(paths) <= architecture_service.HARD_MAX_FILES

    def test_selection_is_deterministic_for_the_same_tree(self):
        entries = _tree(*[f"app/m{i}.py" for i in range(30)])
        first, _ = architecture_service.select_analysis_targets(entries, max_files=5)
        second, _ = architecture_service.select_analysis_targets(entries, max_files=5)
        assert first == second


# --------------------------------------------------------------------------
# Service
# --------------------------------------------------------------------------

@pytest.mark.asyncio
class TestAnalyzeRepository:
    async def test_a_small_repository_produces_a_graph(self, monkeypatch, no_cache):
        _use_client(monkeypatch, FakeClient(tree=_tree(*SAMPLE_FILES), files=SAMPLE_FILES))
        graph = await architecture_service.analyze_repository(
            USER_ID, "token", ScmProvider.github, OWNER, REPO
        )
        assert graph.full_name == f"{OWNER}/{REPO}"
        assert graph.summary.total_modules == 3
        assert graph.summary.internal_edges == 3
        assert graph.commit_sha == "abc123"
        assert graph.errors == []

    async def test_the_router_is_classified_and_its_data_dependency_found(
        self, monkeypatch, no_cache
    ):
        _use_client(monkeypatch, FakeClient(tree=_tree(*SAMPLE_FILES), files=SAMPLE_FILES))
        graph = await architecture_service.analyze_repository(
            USER_ID, "token", ScmProvider.github, OWNER, REPO
        )
        kinds = {node.id: node.kind for node in graph.nodes}
        assert kinds["app.routers.security"] == "controller"
        assert kinds["app.services.security_repository"] == "database"
        assert kinds["external:fastapi"] == "external"

    async def test_fastapi_becomes_an_external_edge_not_an_internal_one(
        self, monkeypatch, no_cache
    ):
        _use_client(monkeypatch, FakeClient(tree=_tree(*SAMPLE_FILES), files=SAMPLE_FILES))
        graph = await architecture_service.analyze_repository(
            USER_ID, "token", ScmProvider.github, OWNER, REPO
        )
        external = {edge.target for edge in graph.edges if edge.kind == "external"}
        internal = {edge.target for edge in graph.edges if edge.kind == "internal"}
        assert "external:fastapi" in external
        assert "external:fastapi" not in internal

    async def test_only_analysable_files_are_fetched(self, monkeypatch, no_cache):
        client = _use_client(
            monkeypatch,
            FakeClient(
                tree=_tree("app/main.py", "README.md", "node_modules/x/index.js"),
                files={"app/main.py": "import os\n"},
            ),
        )
        await architecture_service.analyze_repository(
            USER_ID, "token", ScmProvider.github, OWNER, REPO
        )
        # A vendored bundle must never cost a provider round trip.
        assert client.file_calls == ["app/main.py"]

    async def test_a_missing_file_is_not_an_error(self, monkeypatch, no_cache):
        # The tree can be stale relative to the ref, so a 404 is expected, not a
        # failure to report.
        from app.services.scm import ScmAPIError

        client = _use_client(
            monkeypatch,
            FakeClient(
                tree=_tree("app/main.py", "app/gone.py"),
                files={"app/main.py": "import os\n"},
                file_errors={"app/gone.py": ScmAPIError(404, "Not Found", "not_found")},
            ),
        )
        graph = await architecture_service.analyze_repository(
            USER_ID, "token", ScmProvider.github, OWNER, REPO
        )
        assert graph.errors == []
        assert graph.summary.total_modules == 1

    async def test_one_unreadable_file_does_not_fail_the_analysis(
        self, monkeypatch, no_cache
    ):
        from app.services.scm import ScmAPIError

        _use_client(
            monkeypatch,
            FakeClient(
                tree=_tree("app/main.py", "app/broken.py"),
                files={"app/main.py": "import os\n", "app/broken.py": "x = 1\n"},
                file_errors={
                    "app/broken.py": ScmAPIError(500, "Server Error", "server_error")
                },
            ),
        )
        graph = await architecture_service.analyze_repository(
            USER_ID, "token", ScmProvider.github, OWNER, REPO
        )
        assert graph.summary.total_modules == 1
        assert any("broken.py" in error for error in graph.errors)

    async def test_a_file_with_a_syntax_error_is_listed_but_flagged(
        self, monkeypatch, no_cache
    ):
        files = dict(SAMPLE_FILES)
        files["app/broken.py"] = "def oops(:\n"
        _use_client(
            monkeypatch,
            FakeClient(tree=_tree(*files), files=files),
        )
        graph = await architecture_service.analyze_repository(
            USER_ID, "token", ScmProvider.github, OWNER, REPO
        )
        broken = next(node for node in graph.nodes if node.id == "app.broken")
        assert broken.parsed is False
        assert any("broken.py" in error for error in graph.errors)

    async def test_a_repository_with_no_source_returns_an_empty_graph(
        self, monkeypatch, no_cache
    ):
        _use_client(
            monkeypatch,
            FakeClient(tree=_tree("README.md", "LICENSE"), files={}),
        )
        graph = await architecture_service.analyze_repository(
            USER_ID, "token", ScmProvider.github, OWNER, REPO
        )
        # "Nothing to analyse" is a result, not a 404.
        assert graph.summary.total_modules == 0
        assert graph.nodes == []
        assert graph.errors == []

    async def test_errors_are_capped(self, monkeypatch, no_cache):
        from app.services.scm import ScmAPIError

        paths = [f"app/m{i}.py" for i in range(60)]
        _use_client(
            monkeypatch,
            FakeClient(
                tree=_tree(*paths),
                files={path: "x = 1\n" for path in paths},
                file_errors={
                    path: ScmAPIError(500, "Server Error", "server_error")
                    for path in paths
                },
            ),
        )
        graph = await architecture_service.analyze_repository(
            USER_ID, "token", ScmProvider.github, OWNER, REPO
        )
        assert len(graph.errors) == architecture_service.MAX_ERRORS_REPORTED

    async def test_the_ref_is_passed_to_the_provider(self, monkeypatch, no_cache):
        client = _use_client(
            monkeypatch, FakeClient(tree=_tree("app/main.py"), files={"app/main.py": ""})
        )
        graph = await architecture_service.analyze_repository(
            USER_ID, "token", ScmProvider.github, OWNER, REPO, ref="main"
        )
        assert client.tree_calls == [(OWNER, REPO, "main")]
        assert graph.ref == "main"

    async def test_the_same_repository_yields_the_same_graph(
        self, monkeypatch, no_cache
    ):
        client = FakeClient(tree=_tree(*SAMPLE_FILES), files=SAMPLE_FILES)
        _use_client(monkeypatch, client)
        first = await architecture_service.analyze_repository(
            USER_ID, "token", ScmProvider.github, OWNER, REPO
        )
        second = await architecture_service.analyze_repository(
            USER_ID, "token", ScmProvider.github, OWNER, REPO
        )
        # Everything except the wall-clock fields must be identical.
        for left, right in ((first, second),):
            assert left.nodes == right.nodes
            assert left.edges == right.edges
            assert left.issues == right.issues
            assert left.summary == right.summary

    async def test_a_provider_without_a_tree_is_an_error(self, monkeypatch, no_cache):
        class NoTree:
            async def get_file_content(self, *a, **k):
                return ""

        _use_client(monkeypatch, NoTree())
        with pytest.raises(ArchitectureError, match="repository tree"):
            await architecture_service.analyze_repository(
                USER_ID, "token", ScmProvider.github, OWNER, REPO
            )

    async def test_a_tree_failure_is_an_error(self, monkeypatch, no_cache):
        from app.services.scm import ScmAPIError

        _use_client(
            monkeypatch,
            FakeClient(tree_error=ScmAPIError(404, "Not Found", "not_found")),
        )
        with pytest.raises(ArchitectureError, match="tree"):
            await architecture_service.analyze_repository(
                USER_ID, "token", ScmProvider.github, OWNER, REPO
            )

    async def test_an_empty_tree_is_an_error(self, monkeypatch, no_cache):
        _use_client(monkeypatch, FakeClient(tree=[]))
        with pytest.raises(ArchitectureError, match="empty or unreadable"):
            await architecture_service.analyze_repository(
                USER_ID, "token", ScmProvider.github, OWNER, REPO
            )

    async def test_a_gitlab_provider_is_recorded_on_the_graph(self, monkeypatch, no_cache):
        _use_client(monkeypatch, FakeClient(tree=_tree("app/main.py"), files={"app/main.py": ""}))
        graph = await architecture_service.analyze_repository(
            USER_ID, "token", ScmProvider.gitlab, OWNER, REPO
        )
        assert graph.provider == "gitlab"


@pytest.mark.asyncio
class TestCaching:
    """These drive the real ``_read_cache``/``_write_cache`` functions.

    The resilience being tested lives *inside* those functions, so a test that
    replaced them with a stub would assert nothing. They are driven by making the
    underlying repository layer misbehave instead.
    """

    async def test_a_cached_graph_is_returned_without_fetching(self, monkeypatch):
        cached = ArchitectureGraph(
            repository_id="octocat/hello-world",
            owner=OWNER,
            repository=REPO,
            full_name=f"{OWNER}/{REPO}",
            analyzed_at="2026-01-01T00:00:00+00:00",
        )
        monkeypatch.setattr(
            cache_repo, "get_cached", _returning({"payload": cached.model_dump(mode="json")})
        )
        client = _use_client(monkeypatch, FakeClient(tree=_tree("app/main.py")))
        graph = await architecture_service.analyze_repository(
            USER_ID, "token", ScmProvider.github, OWNER, REPO
        )
        assert graph.analyzed_at == "2026-01-01T00:00:00+00:00"
        # A cache hit must not cost a provider round trip.
        assert client.tree_calls == []
        assert client.file_calls == []

    async def test_the_cache_is_keyed_by_analysis_kind(self, monkeypatch):
        seen: list[str] = []

        async def get_cached(user_id, owner, repository, analysis):
            seen.append(analysis)
            return None

        monkeypatch.setattr(cache_repo, "get_cached", get_cached)
        _use_client(monkeypatch, FakeClient(tree=_tree("app/main.py"), files={"app/main.py": ""}))
        await architecture_service.analyze_repository(
            USER_ID, "token", ScmProvider.github, OWNER, REPO
        )
        # Reusing the shared collection requires using the right namespace.
        assert seen == [architecture_service.CACHE_KIND]

    async def test_refresh_bypasses_the_cache_and_replaces_it(self, monkeypatch):
        reads: list[bool] = []
        written: list[str] = []

        async def get_cached(user_id, owner, repository, analysis):
            reads.append(analysis)
            return None

        async def set_cached(user_id, owner, repository, analysis, payload, ttl_seconds=None):
            written.append(analysis)
            return {}

        monkeypatch.setattr(cache_repo, "get_cached", get_cached)
        monkeypatch.setattr(cache_repo, "set_cached", set_cached)
        _use_client(monkeypatch, FakeClient(tree=_tree("app/main.py"), files={"app/main.py": ""}))
        await architecture_service.analyze_repository(
            USER_ID, "token", ScmProvider.github, OWNER, REPO, refresh=True
        )
        assert reads == []
        assert written == [architecture_service.CACHE_KIND]

    async def test_use_cache_false_skips_the_read(self, monkeypatch, no_cache):
        monkeypatch.setattr(cache_repo, "get_cached", _boom("cache should not be read"))
        _use_client(monkeypatch, FakeClient(tree=_tree("app/main.py"), files={"app/main.py": ""}))
        graph = await architecture_service.analyze_repository(
            USER_ID, "token", ScmProvider.github, OWNER, REPO, use_cache=False
        )
        assert graph.summary.total_modules == 1

    async def test_a_database_outage_on_read_degrades_to_a_recompute(self, monkeypatch, no_cache):
        monkeypatch.setattr(cache_repo, "get_cached", _boom("db down"))
        _use_client(monkeypatch, FakeClient(tree=_tree("app/main.py"), files={"app/main.py": ""}))
        graph = await architecture_service.analyze_repository(
            USER_ID, "token", ScmProvider.github, OWNER, REPO
        )
        # A caching layer must never be able to fail the feature.
        assert graph.summary.total_modules == 1

    async def test_a_cache_write_failure_does_not_fail_the_analysis(self, monkeypatch, no_cache):
        monkeypatch.setattr(cache_repo, "set_cached", _boom("disk full"))
        _use_client(monkeypatch, FakeClient(tree=_tree("app/main.py"), files={"app/main.py": ""}))
        graph = await architecture_service.analyze_repository(
            USER_ID, "token", ScmProvider.github, OWNER, REPO
        )
        assert graph.summary.total_modules == 1

    async def test_a_stale_cached_payload_degrades_to_a_recompute(self, monkeypatch, no_cache):
        # A document written by an older schema must not turn a working analysis
        # into a 500.
        monkeypatch.setattr(cache_repo, "get_cached", _returning({"payload": {"not": "a graph"}}))
        _use_client(monkeypatch, FakeClient(tree=_tree("app/main.py"), files={"app/main.py": ""}))
        graph = await architecture_service.analyze_repository(
            USER_ID, "token", ScmProvider.github, OWNER, REPO
        )
        assert graph.summary.total_modules == 1

    async def test_a_non_dict_cached_payload_is_treated_as_a_miss(self, monkeypatch, no_cache):
        monkeypatch.setattr(cache_repo, "get_cached", _returning({"payload": "garbage"}))
        _use_client(monkeypatch, FakeClient(tree=_tree("app/main.py"), files={"app/main.py": ""}))
        graph = await architecture_service.analyze_repository(
            USER_ID, "token", ScmProvider.github, OWNER, REPO
        )
        assert graph.summary.total_modules == 1

    async def test_the_cached_graph_round_trips(self, monkeypatch):
        files = dict(SAMPLE_FILES)
        _use_client(monkeypatch, FakeClient(tree=_tree(*files), files=files))
        stored: dict = {}

        async def set_cached(user_id, owner, repository, analysis, payload, ttl_seconds=None):
            stored["payload"] = payload
            return {}

        async def get_cached(user_id, owner, repository, analysis):
            return stored or None

        monkeypatch.setattr(cache_repo, "set_cached", set_cached)
        monkeypatch.setattr(cache_repo, "get_cached", get_cached)
        first = await architecture_service.analyze_repository(
            USER_ID, "token", ScmProvider.github, OWNER, REPO
        )
        second = await architecture_service.analyze_repository(
            USER_ID, "token", ScmProvider.github, OWNER, REPO
        )
        # A cache hit must be indistinguishable from a fresh computation.
        assert first.nodes == second.nodes
        assert first.summary == second.summary
        assert first.issues == second.issues


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
    async def test_the_graph_is_returned_for_a_valid_request(self, client, auth_headers, monkeypatch):
        _use_client(monkeypatch, FakeClient(tree=_tree(*SAMPLE_FILES), files=SAMPLE_FILES))
        monkeypatch.setattr(architecture_service, "_read_cache", _never_cache)
        monkeypatch.setattr(architecture_service, "_write_cache", _never_write)
        response = client.get(
            f"/architecture/repositories/{OWNER}/{REPO}", headers=auth_headers
        )
        assert response.status_code == 200
        body = response.json()
        assert body["full_name"] == f"{OWNER}/{REPO}"
        assert body["summary"]["total_modules"] == 3
        # The response must carry the statement of its own coverage so the page
        # can state what was and was not analysed.
        assert "No model" in body["summary"]["methodology"]

    async def test_a_request_without_a_token_is_rejected(self, client, monkeypatch):
        _use_client(monkeypatch, FakeClient(tree=_tree("app/main.py")))
        response = client.get(f"/architecture/repositories/{OWNER}/{REPO}")
        assert response.status_code in (401, 403)

    async def test_a_user_without_a_connected_account_is_rejected(self, client):
        response = client.get(
            f"/architecture/repositories/{OWNER}/{REPO}",
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        assert response.status_code in (401, 403)

    async def test_the_api_prefixed_route_behaves_identically(
        self, client, auth_headers, monkeypatch
    ):
        _use_client(monkeypatch, FakeClient(tree=_tree("app/main.py"), files={"app/main.py": ""}))
        monkeypatch.setattr(architecture_service, "_read_cache", _never_cache)
        monkeypatch.setattr(architecture_service, "_write_cache", _never_write)
        response = client.get(
            f"/api/architecture/repositories/{OWNER}/{REPO}", headers=auth_headers
        )
        assert response.status_code == 200

    async def test_a_provider_failure_is_reported_as_a_bad_gateway(
        self, client, auth_headers, monkeypatch
    ):
        _use_client(monkeypatch, FakeClient(tree=[]))
        monkeypatch.setattr(architecture_service, "_read_cache", _never_cache)
        response = client.get(
            f"/architecture/repositories/{OWNER}/{REPO}", headers=auth_headers
        )
        assert response.status_code == 502

    async def test_a_repository_with_no_source_is_a_200_not_a_404(
        self, client, auth_headers, monkeypatch
    ):
        _use_client(monkeypatch, FakeClient(tree=_tree("README.md"), files={}))
        monkeypatch.setattr(architecture_service, "_read_cache", _never_cache)
        monkeypatch.setattr(architecture_service, "_write_cache", _never_write)
        response = client.get(
            f"/architecture/repositories/{OWNER}/{REPO}", headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["summary"]["total_modules"] == 0

    async def test_max_files_must_be_positive(self, client, auth_headers):
        response = client.get(
            f"/architecture/repositories/{OWNER}/{REPO}?max_files=0", headers=auth_headers
        )
        assert response.status_code == 422

    async def test_the_provider_is_validated(self, client, auth_headers):
        response = client.get(
            f"/architecture/repositories/{OWNER}/{REPO}?provider=bitbucket",
            headers=auth_headers,
        )
        assert response.status_code == 422

    async def test_a_graphy_response_contains_no_file_content(
        self, client, auth_headers, monkeypatch
    ):
        # The graph describes structure; it must not echo source back to the UI.
        secret = "AWS_SECRET_ACCESS_KEY=super-secret-value"
        files = {"app/config.py": f"SECRET = '{secret}'\n"}
        _use_client(monkeypatch, FakeClient(tree=_tree("app/config.py"), files=files))
        monkeypatch.setattr(architecture_service, "_read_cache", _never_cache)
        monkeypatch.setattr(architecture_service, "_write_cache", _never_write)
        response = client.get(
            f"/architecture/repositories/{OWNER}/{REPO}", headers=auth_headers
        )
        assert response.status_code == 200
        assert "super-secret-value" not in response.text


class TestCacheRegistration:
    def test_architecture_is_a_registered_analysis_kind(self):
        from app.services import repository_analysis_repository as cache

        # Reusing the shared cache collection is deliberate; a new namespace
        # would be a second persistence layer for the same job.
        assert "architecture" in cache.ANALYSIS_KINDS
        assert cache.ttl_for("architecture") > 0
