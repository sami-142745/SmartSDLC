"""Tests for test-generation orchestration and its HTTP surface.

The service tests cover what touches the outside world — target selection,
bounded fetching, partial failure, proposed-path collisions, caching — and the
route tests cover authentication and the response contract. The property that
matters most here is that nothing in this module can write to a repository.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.schemas.test_generation import MAX_GENERATED_FILES, MAX_TARGETS, TestGeneration
from app.services import test_generation_service as gen_service
from app.services import test_generator
from app.services.repository_analysis_repository import DEFAULT_TTL_SECONDS
from app.services.repository_analysis_repository import ANALYSIS_KINDS
from app.services.scm import ScmAPIError, ScmProvider
from app.services.test_generation_service import TestGenerationError

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
    monkeypatch.setattr(gen_service, "_client", lambda provider, token: client)
    return client


def _tree(*paths: str) -> list[dict[str, Any]]:
    return [{"path": path, "type": "blob", "size": 100} for path in paths]


async def _never_cache(*args, **kwargs):
    return None


async def _never_write(*args, **kwargs):
    return None


@pytest.fixture
def no_cache(monkeypatch):
    monkeypatch.setattr(gen_service, "_read_cache", _never_cache)
    monkeypatch.setattr(gen_service, "_write_cache", _never_write)


@pytest.fixture
def no_model(monkeypatch):
    """Gemini unavailable, so generation is deterministic and offline."""
    monkeypatch.setattr(test_generator.settings, "GEMINI_API_KEY", "")


SAMPLE_FILES = {
    "app/services/covered.py": "def covered():\n    return 1\n",
    "app/services/orphan.py": 'def orphan(value):\n    """Doc."""\n    if value:\n        pass\n    return value\n',
    "tests/test_covered.py": "from app.services.covered import covered\n\ndef test_x():\n    covered()\n",
    "README.md": "# Project\n",
}


# --------------------------------------------------------------------------
# File selection
# --------------------------------------------------------------------------

class TestFileSelection:
    def test_source_and_test_files_are_separated(self):
        source, tests, source_count, test_count, truncated = gen_service.select_files(
            _tree(*SAMPLE_FILES)
        )
        assert source == ["app/services/covered.py", "app/services/orphan.py"]
        assert tests == ["tests/test_covered.py"]
        assert source_count == 2
        assert test_count == 1
        assert truncated is False

    def test_ignored_and_unsupported_paths_are_excluded(self):
        source, tests, *_ = gen_service.select_files(
            _tree("node_modules/p/i.js", "dist/bundle.js", "README.md", "Makefile")
        )
        assert source == []
        assert tests == []

    def test_directory_entries_are_ignored(self):
        source, tests, *_ = gen_service.select_files(
            [{"path": "app", "type": "tree"}, {"path": "app/a.py", "type": "blob"}]
        )
        assert source == ["app/a.py"]

    def test_malformed_entries_are_skipped(self):
        source, _, *_ = gen_service.select_files(
            [{"path": None}, {"type": "blob"}, "not a dict", {"path": "", "type": "blob"}]
        )
        assert source == []

    def test_traversal_segments_are_normalised_away(self):
        source, *_ = gen_service.select_files(_tree("app/../../etc/passwd.py"))
        # A ``..`` segment can never survive normalisation, so a crafted tree
        # entry cannot address anything outside the repository.
        assert source == ["app/etc/passwd.py"]
        assert all(".." not in path for path in source)

    def test_selection_is_capped_and_reported(self):
        entries = _tree(*[f"app/mod{i}.py" for i in range(10)])
        source, _, source_count, _, truncated = gen_service.select_files(
            entries, max_source_files=3
        )
        assert len(source) == 3
        assert source_count == 10
        assert truncated is True

    def test_test_files_are_capped_independently(self):
        entries = _tree(*[f"tests/test_{i}.py" for i in range(10)], "app/a.py")
        source, tests, _, test_count, _ = gen_service.select_files(
            entries, max_source_files=100, max_test_files=4
        )
        assert len(tests) == 4
        assert test_count == 10
        assert source == ["app/a.py"]

    def test_the_hard_ceiling_cannot_be_exceeded(self):
        entries = _tree(*[f"app/mod{i}.py" for i in range(30)])
        source, *_ = gen_service.select_files(entries, max_source_files=10**6)
        assert len(source) <= gen_service.HARD_MAX_FILES

    def test_selection_is_deterministic(self):
        entries = _tree(*SAMPLE_FILES)
        first = gen_service.select_files(entries)
        second = gen_service.select_files(list(reversed(entries)))
        assert first[0] == second[0]
        assert first[1] == second[1]

    def test_source_prefixes_are_prioritised(self):
        entries = _tree("zzz.py", "app/a.py", "scripts/b.py")
        source, *_ = gen_service.select_files(entries)
        assert source[0] == "app/a.py"


# --------------------------------------------------------------------------
# Proposed paths
# --------------------------------------------------------------------------

class TestProposedTestPath:
    def test_a_unique_stem_goes_flat_under_the_test_directory(self):
        assert (
            gen_service.proposed_test_path("app/services/scm.py", test_directories=["tests"])
            == "tests/test_scm.py"
        )

    def test_a_taken_path_is_qualified_by_directory(self):
        # Without this, app/other/util.py would propose tests/test_util.py and
        # shadow a real test file.
        assert (
            gen_service.proposed_test_path(
                "app/other/util.py",
                test_directories=["tests"],
                existing_paths=["tests/test_util.py"],
            )
            == "tests/other/test_util.py"
        )

    def test_a_taken_and_qualified_path_gets_a_suffix(self):
        assert (
            gen_service.proposed_test_path(
                "app/other/util.py",
                test_directories=["tests"],
                existing_paths=["tests/test_util.py", "tests/other/test_util.py"],
            )
            == "tests/other/test_util_2.py"
        )

    def test_colliding_stems_get_distinct_paths(self):
        a = gen_service.proposed_test_path("a/utils.py", test_directories=["tests"], ambiguous=True)
        b = gen_service.proposed_test_path("b/utils.py", test_directories=["tests"], ambiguous=True)
        assert a != b

    def test_javascript_co_locates_when_there_is_no_test_directory(self):
        assert gen_service.proposed_test_path("src/index.ts") == "src/index.test.ts"

    def test_a_source_already_named_test_something_is_not_doubled(self):
        assert (
            gen_service.proposed_test_path("app/test_helpers.py", test_directories=["tests"])
            == "tests/test_helpers.py"
        )

    def test_a_root_level_file_still_produces_a_path(self):
        assert (
            gen_service.proposed_test_path("main.py", test_directories=["tests"])
            == "tests/test_main.py"
        )

    def test_the_path_is_stable(self):
        paths = {
            gen_service.proposed_test_path("app/other/util.py", test_directories=["tests"])
            for _ in range(5)
        }
        assert len(paths) == 1


# --------------------------------------------------------------------------
# Running generation
# --------------------------------------------------------------------------

@pytest.mark.asyncio
class TestGenerateTestsForRepository:
    async def test_a_referenced_symbol_is_not_proposed(self, monkeypatch, no_cache, no_model):
        _use_client(monkeypatch, FakeClient(tree=_tree(*SAMPLE_FILES), files=SAMPLE_FILES))
        report = await gen_service.generate_tests_for_repository(
            USER_ID, "tok", ScmProvider.github, OWNER, REPO
        )
        assert [t.name for t in report.targets] == ["orphan"]
        assert report.summary.untested_symbols == 1
        assert report.summary.public_symbols == 2

    async def test_a_repository_with_no_tests_is_still_a_result(self, monkeypatch, no_cache, no_model):
        files = {"app/a.py": "def orphan():\n    return 1\n"}
        _use_client(monkeypatch, FakeClient(tree=_tree(*files), files=files))
        report = await gen_service.generate_tests_for_repository(
            USER_ID, "tok", ScmProvider.github, OWNER, REPO
        )
        assert report.targets[0].reason == "no_test_suite"
        assert report.framework == "unknown"

    async def test_a_file_that_cannot_be_read_is_recorded_not_fatal(
        self, monkeypatch, no_cache, no_model
    ):

        files = dict(SAMPLE_FILES)
        client = FakeClient(
            tree=_tree(*files),
            files=files,
            file_errors={"app/services/orphan.py": ScmAPIError(500, "boom", "server")},
        )
        _use_client(monkeypatch, client)
        report = await gen_service.generate_tests_for_repository(
            USER_ID, "tok", ScmProvider.github, OWNER, REPO
        )
        assert any("orphan.py" in error for error in report.errors)
        # The rest of the repository was still analysed.
        assert report.summary.public_symbols >= 1

    async def test_a_file_that_is_missing_is_not_an_error(self, monkeypatch, no_cache, no_model):
        files = dict(SAMPLE_FILES)
        client = FakeClient(
            tree=_tree(*files),
            files=files,
            file_errors={"app/services/orphan.py": ScmAPIError(404, "Not Found", "not_found")},
        )
        _use_client(monkeypatch, client)
        report = await gen_service.generate_tests_for_repository(
            USER_ID, "tok", ScmProvider.github, OWNER, REPO
        )
        assert report.errors == []

    async def test_a_provider_error_on_the_tree_stops_the_run(self, monkeypatch, no_cache, no_model):

        _use_client(
            monkeypatch, FakeClient(tree_error=ScmAPIError(404, "Not Found", "not_found"))
        )
        with pytest.raises(TestGenerationError, match="tree"):
            await gen_service.generate_tests_for_repository(
                USER_ID, "tok", ScmProvider.github, OWNER, REPO
            )

    async def test_an_unexpected_tree_error_stops_the_run(self, monkeypatch, no_cache, no_model):
        _use_client(monkeypatch, FakeClient(tree_error=RuntimeError("boom")))
        with pytest.raises(TestGenerationError):
            await gen_service.generate_tests_for_repository(
                USER_ID, "tok", ScmProvider.github, OWNER, REPO
            )

    async def test_an_empty_tree_is_an_error(self, monkeypatch, no_cache, no_model):
        _use_client(monkeypatch, FakeClient(tree=[]))
        with pytest.raises(TestGenerationError, match="empty"):
            await gen_service.generate_tests_for_repository(
                USER_ID, "tok", ScmProvider.github, OWNER, REPO
            )

    async def test_a_client_without_a_tree_method_is_rejected(self, monkeypatch, no_cache, no_model):
        class NoTree:
            async def get_file_content(self, *args, **kwargs):
                return None

        _use_client(monkeypatch, NoTree())
        with pytest.raises(TestGenerationError, match="tree"):
            await gen_service.generate_tests_for_repository(
                USER_ID, "tok", ScmProvider.github, OWNER, REPO
            )

    async def test_a_client_without_file_content_is_rejected(self, monkeypatch, no_cache, no_model):
        class NoFiles:
            async def get_repository_tree(self, *args, **kwargs):
                return {"tree": []}

        _use_client(monkeypatch, NoFiles())
        with pytest.raises(TestGenerationError, match="file content"):
            await gen_service.generate_tests_for_repository(
                USER_ID, "tok", ScmProvider.github, OWNER, REPO
            )

    async def test_the_ref_is_passed_through(self, monkeypatch, no_cache, no_model):
        client = _use_client(
            monkeypatch, FakeClient(tree=_tree(*SAMPLE_FILES), files=SAMPLE_FILES)
        )
        await gen_service.generate_tests_for_repository(
            USER_ID, "tok", ScmProvider.github, OWNER, REPO, ref="main"
        )
        assert client.tree_calls == [(OWNER, REPO, "main")]

    async def test_the_commit_sha_is_reported(self, monkeypatch, no_cache, no_model):
        _use_client(monkeypatch, FakeClient(tree=_tree(*SAMPLE_FILES), files=SAMPLE_FILES))
        report = await gen_service.generate_tests_for_repository(
            USER_ID, "tok", ScmProvider.github, OWNER, REPO
        )
        assert report.commit_sha == "abc123"

    async def test_max_targets_limits_the_proposals(self, monkeypatch, no_cache, no_model):
        files = {"app/a.py": "".join(f"def f{i}():\n    return {i}\n" for i in range(10))}
        _use_client(monkeypatch, FakeClient(tree=_tree(*files), files=files))
        report = await gen_service.generate_tests_for_repository(
            USER_ID, "tok", ScmProvider.github, OWNER, REPO, max_targets=2
        )
        assert len(report.targets) == 2
        assert report.truncated is True

    async def test_max_targets_cannot_exceed_the_schema_ceiling(self, monkeypatch, no_cache, no_model):
        files = {"app/a.py": "".join(f"def f{i}():\n    return {i}\n" for i in range(80))}
        _use_client(monkeypatch, FakeClient(tree=_tree(*files), files=files))
        report = await gen_service.generate_tests_for_repository(
            USER_ID, "tok", ScmProvider.github, OWNER, REPO, max_targets=10**6
        )
        assert len(report.targets) <= MAX_TARGETS

    async def test_the_file_cap_is_applied_before_generation(
        self, monkeypatch, no_cache, no_model
    ):
        """The cap bounds model spend, not just the size of the response.

        Generating 40 files and then discarding 28 would pay for 28 model calls
        whose answers are thrown away, so the plan is cut first.
        """
        files = {
            f"app/mod{i:02d}.py": f"def shared():\n    return {i}\n"
            for i in range(MAX_GENERATED_FILES + 8)
        }
        _use_client(monkeypatch, FakeClient(tree=_tree(*files), files=files))

        calls: list[str] = []
        real_generate = gen_service.generate_test_file

        async def _counting_generate(**kwargs):
            calls.append(kwargs["path"])
            return await real_generate(**kwargs)

        monkeypatch.setattr(gen_service, "generate_test_file", _counting_generate)

        report = await gen_service.generate_tests_for_repository(
            USER_ID, "tok", ScmProvider.github, OWNER, REPO
        )

        assert len(calls) <= MAX_GENERATED_FILES
        assert len(report.files) <= MAX_GENERATED_FILES
        assert report.truncated is True

    async def test_the_highest_priority_targets_are_the_ones_kept(
        self, monkeypatch, no_cache, no_model
    ):
        """The file cap must drop the least valuable work, not the largest file.

        Ranking by group size would generate the file with the most symbols
        first and drop a single, more valuable target; the parser already scored
        these from measured facts, so its verdict is what the cap must respect.
        """
        files = {
            f"app/mod{i:02d}.py": f"def filler{i}():\n    return {i}\n"
            for i in range(MAX_GENERATED_FILES + 2)
        }
        # Documented and branching, so the parser scores this well above the
        # undocumented one-line fillers above.
        files["app/security_gate.py"] = (
            'def authorise_request(token):\n'
            '    """Reject anything without a token."""\n'
            "    if not token:\n"
            "        return False\n"
            "    if token == 'expired':\n"
            "        return False\n"
            "    return True\n"
        )
        _use_client(monkeypatch, FakeClient(tree=_tree(*files), files=files))
        report = await gen_service.generate_tests_for_repository(
            USER_ID, "tok", ScmProvider.github, OWNER, REPO
        )

        assert len(report.files) <= MAX_GENERATED_FILES
        assert any("security_gate" in item.path for item in report.files), (
            "the highest-priority source was dropped while filler files were kept"
        )

    async def test_a_proposal_never_shadows_an_existing_test_file(
        self, monkeypatch, no_cache, no_model
    ):
        files = {
            "app/util.py": "def shared():\n    return 1\n",
            "app/other/util.py": "def other():\n    return 2\n",
            "tests/test_util.py": "def test_x():\n    assert True\n",
        }
        _use_client(monkeypatch, FakeClient(tree=_tree(*files), files=files))
        report = await gen_service.generate_tests_for_repository(
            USER_ID, "tok", ScmProvider.github, OWNER, REPO
        )
        proposed = {item.path for item in report.files}
        assert "tests/test_util.py" not in proposed
        assert proposed

    async def test_the_report_carries_its_own_methodology(self, monkeypatch, no_cache, no_model):
        _use_client(monkeypatch, FakeClient(tree=_tree(*SAMPLE_FILES), files=SAMPLE_FILES))
        report = await gen_service.generate_tests_for_repository(
            USER_ID, "tok", ScmProvider.github, OWNER, REPO
        )
        # The response must state what was measured so the page can say so.
        assert "No model is used to decide what to test" in report.summary.methodology
        assert "never written to the repository" in report.summary.methodology

    async def test_generation_is_a_preview(self, monkeypatch, no_cache, no_model):
        _use_client(monkeypatch, FakeClient(tree=_tree(*SAMPLE_FILES), files=SAMPLE_FILES))
        report = await gen_service.generate_tests_for_repository(
            USER_ID, "tok", ScmProvider.github, OWNER, REPO
        )
        # The contract has no field through which a write could be requested.
        assert set(TestGeneration.model_fields) == {
            "repository_id",
            "owner",
            "repository",
            "full_name",
            "provider",
            "ref",
            "commit_sha",
            "generated_at",
            "duration_ms",
            "framework",
            "test_directories",
            "existing_test_files",
            "targets",
            "files",
            "summary",
            "model",
            "unavailable_reason",
            "errors",
            "truncated",
        }

    async def test_the_scm_clients_expose_no_write_method(self):
        # A future change that adds one must update this test deliberately.
        from app.services.github_client import GitHubClient
        from app.services.gitlab_client import GitLabClient

        for client in (GitHubClient, GitLabClient):
            writable = [
                name
                for name in dir(client)
                if any(
                    name.startswith(prefix)
                    for prefix in ("create_", "update_", "put_", "post_", "delete_", "push_", "commit_")
                )
            ]
            assert writable == [], f"{client.__name__} exposes {writable}"

    async def test_the_model_is_used_when_configured(self, monkeypatch, no_cache):
        monkeypatch.setattr(test_generator.settings, "GEMINI_API_KEY", "key")
        monkeypatch.setattr(
            test_generator,
            "_generate_content_with_retry",
            lambda *a, **k: type("R", (), {"text": '{"tests": [{"name": "test_a", "body": "assert True"}]}'})(),
        )
        _use_client(monkeypatch, FakeClient(tree=_tree(*SAMPLE_FILES), files=SAMPLE_FILES))
        report = await gen_service.generate_tests_for_repository(
            USER_ID, "tok", ScmProvider.github, OWNER, REPO
        )
        assert report.model is not None
        assert report.unavailable_reason is None
        assert all(item.source == "gemini" for item in report.files)

    async def test_a_scaffold_run_explains_itself(self, monkeypatch, no_cache, no_model):
        _use_client(monkeypatch, FakeClient(tree=_tree(*SAMPLE_FILES), files=SAMPLE_FILES))
        report = await gen_service.generate_tests_for_repository(
            USER_ID, "tok", ScmProvider.github, OWNER, REPO
        )
        assert report.model is None
        assert "not configured" in report.unavailable_reason
        assert report.summary.rejected_files == len(report.files)


# --------------------------------------------------------------------------
# Caching
# --------------------------------------------------------------------------

@pytest.mark.asyncio
class TestCaching:
    async def test_a_cached_result_is_returned_without_reading_the_repository(
        self, monkeypatch
    ):
        cached = TestGeneration(
            repository_id="r",
            owner=OWNER,
            repository=REPO,
            full_name=f"{OWNER}/{REPO}",
            provider="github",
            generated_at="2026-01-01T00:00:00+00:00",
        )

        async def _cached(*args, **kwargs):
            # ``_read_cache`` returns the payload itself, already unwrapped from
            # the cache document.
            return cached.model_dump(mode="json")

        monkeypatch.setattr(gen_service, "_read_cache", _cached)
        client = FakeClient(tree=_tree(*SAMPLE_FILES), files=SAMPLE_FILES)
        _use_client(monkeypatch, client)
        report = await gen_service.generate_tests_for_repository(
            USER_ID, "tok", ScmProvider.github, OWNER, REPO
        )
        assert report.generated_at == "2026-01-01T00:00:00+00:00"
        assert client.tree_calls == []

    async def test_refresh_bypasses_the_cache(self, monkeypatch, no_cache, no_model):
        client = _use_client(
            monkeypatch, FakeClient(tree=_tree(*SAMPLE_FILES), files=SAMPLE_FILES)
        )
        report = await gen_service.generate_tests_for_repository(
            USER_ID, "tok", ScmProvider.github, OWNER, REPO, refresh=True
        )
        assert client.tree_calls
        assert report.targets

    async def test_an_unreadable_cache_entry_is_discarded(self, monkeypatch, no_model):
        async def _broken(*args, **kwargs):
            return {"not": "a test generation"}

        monkeypatch.setattr(gen_service, "_read_cache", _broken)
        _use_client(monkeypatch, FakeClient(tree=_tree(*SAMPLE_FILES), files=SAMPLE_FILES))
        report = await gen_service.generate_tests_for_repository(
            USER_ID, "tok", ScmProvider.github, OWNER, REPO
        )
        assert report.targets

    async def test_a_cache_read_failure_does_not_fail_the_run(self, monkeypatch, no_model):
        async def _explode(*args, **kwargs):
            raise RuntimeError("mongo down")

        # Fail the database, not the wrapper: the wrapper is where the
        # resilience lives, so replacing it would test nothing.
        monkeypatch.setattr(
            gen_service.repository_analysis_repository, "get_cached", _explode
        )
        _use_client(monkeypatch, FakeClient(tree=_tree(*SAMPLE_FILES), files=SAMPLE_FILES))
        report = await gen_service.generate_tests_for_repository(
            USER_ID, "tok", ScmProvider.github, OWNER, REPO
        )
        assert report.targets

    async def test_a_cache_write_failure_does_not_fail_the_run(self, monkeypatch, no_model):
        async def _explode(*args, **kwargs):
            raise RuntimeError("mongo down")

        monkeypatch.setattr(
            gen_service.repository_analysis_repository, "set_cached", _explode
        )
        _use_client(monkeypatch, FakeClient(tree=_tree(*SAMPLE_FILES), files=SAMPLE_FILES))
        report = await gen_service.generate_tests_for_repository(
            USER_ID, "tok", ScmProvider.github, OWNER, REPO
        )
        assert report.targets

    def test_the_analysis_kind_is_registered(self):
        assert "test_generation" in ANALYSIS_KINDS
        assert "test_generation" in DEFAULT_TTL_SECONDS


# --------------------------------------------------------------------------
# HTTP surface
# --------------------------------------------------------------------------

@pytest.mark.asyncio
class TestRoutes:
    async def test_the_proposal_is_returned_for_a_valid_request(
        self, client, auth_headers, monkeypatch, no_cache, no_model
    ):
        _use_client(monkeypatch, FakeClient(tree=_tree(*SAMPLE_FILES), files=SAMPLE_FILES))
        response = client.get(
            f"/test-generation/repositories/{OWNER}/{REPO}", headers=auth_headers
        )
        assert response.status_code == 200
        body = response.json()
        assert body["full_name"] == f"{OWNER}/{REPO}"
        assert body["targets"][0]["name"] == "orphan"
        assert body["summary"]["public_symbols"] == 2
        assert body["files"][0]["path"].startswith("tests/")

    async def test_the_api_prefixed_route_is_also_registered(
        self, client, auth_headers, monkeypatch, no_cache, no_model
    ):
        _use_client(monkeypatch, FakeClient(tree=_tree(*SAMPLE_FILES), files=SAMPLE_FILES))
        response = client.get(
            f"/api/test-generation/repositories/{OWNER}/{REPO}", headers=auth_headers
        )
        assert response.status_code == 200

    async def test_an_unauthenticated_request_is_rejected(self, client):
        response = client.get(f"/test-generation/repositories/{OWNER}/{REPO}")
        assert response.status_code in (401, 403)

    async def test_max_files_must_be_positive(self, client, auth_headers):
        response = client.get(
            f"/test-generation/repositories/{OWNER}/{REPO}?max_files=0", headers=auth_headers
        )
        assert response.status_code == 422

    async def test_max_targets_is_bounded(self, client, auth_headers):
        response = client.get(
            f"/test-generation/repositories/{OWNER}/{REPO}?max_targets={MAX_TARGETS + 1}",
            headers=auth_headers,
        )
        assert response.status_code == 422

    async def test_the_provider_is_validated(self, client, auth_headers):
        response = client.get(
            f"/test-generation/repositories/{OWNER}/{REPO}?provider=bitbucket",
            headers=auth_headers,
        )
        assert response.status_code == 422

    async def test_a_tree_failure_is_reported_as_a_bad_gateway(
        self, client, auth_headers, monkeypatch, no_cache
    ):

        _use_client(
            monkeypatch, FakeClient(tree_error=ScmAPIError(404, "Not Found", "not_found"))
        )
        response = client.get(
            f"/test-generation/repositories/{OWNER}/{REPO}", headers=auth_headers
        )
        assert response.status_code == 502

    async def test_there_is_no_write_route(self, client, auth_headers):
        """The preview-only guarantee: no route writes generated tests to the repository."""
        from app.main import app

        paths = {route.path for route in app.routes if "test-generation" in route.path}
        assert paths == {
            "/test-generation/repositories/{owner}/{repo}",
            "/api/test-generation/repositories/{owner}/{repo}",
            "/test-generation/repositories/{owner}/{repo}/validate",
            "/api/test-generation/repositories/{owner}/{repo}/validate",
            "/test-generation/repositories/{owner}/{repo}/regenerate",
            "/api/test-generation/repositories/{owner}/{repo}/regenerate",
        }
        # The preview-only guarantee is that generated tests are never written to
        # the repository. The validate/regenerate endpoints return content but
        # do not persist it; only the GET endpoints are cached and returned.
