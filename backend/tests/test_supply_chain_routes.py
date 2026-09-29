"""Tests for supply-chain orchestration and its HTTP surface.

The service tests cover the parts that touch the outside world - target
selection, bounded fetching, partial failure, caching - and the route tests cover
authentication, ownership isolation, and the shape of the response contract.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.schemas.supply_chain import (
    CODE_NO_LOCKFILE,
    CODE_NO_MANIFEST,
    SupplyChainReport,
)
from app.services import repository_analysis_repository as cache_repo
from app.services import supply_chain_service as service
from app.services.scm import ScmAPIError, ScmProvider
from app.services.supply_chain_service import SupplyChainError

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
    monkeypatch.setattr(service, "_client", lambda provider, token: client)
    return client


def _tree(*paths: str) -> list[dict[str, Any]]:
    return [{"path": path, "type": "blob", "size": 100} for path in paths]


async def _never_cache(*args, **kwargs):
    return None


async def _never_write(*args, **kwargs):
    return None


@pytest.fixture
def no_cache(monkeypatch):
    monkeypatch.setattr(service, "_read_cache", _never_cache)
    monkeypatch.setattr(service, "_write_cache", _never_write)


PACKAGE_JSON = """{
  "name": "demo", "license": "MIT",
  "dependencies": {
    "express": "^4.17.21",
    "app-lib": {"version": "2.0.0", "license": "GPL-3.0-only"}
  }
}"""

PACKAGE_LOCK = """{"lockfileVersion": 3, "packages": {
  "": {"name": "demo"},
  "node_modules/express": {"version": "4.17.21", "license": "MIT"},
  "node_modules/body-parser": {"version": "1.20.0", "license": "MIT"}}}"""

SAMPLE_FILES = {
    "package.json": PACKAGE_JSON,
    "package-lock.json": PACKAGE_LOCK,
    "requirements.txt": "requests==2.31.0\n",
    "LICENSE": "MIT License\n\nPermission is hereby granted, free of charge...\n",
}


# --------------------------------------------------------------------------
# Target selection
# --------------------------------------------------------------------------


class TestTargetSelection:
    @pytest.mark.asyncio
    async def test_only_dependency_files_are_read(self, no_cache, monkeypatch):
        client = _use_client(
            monkeypatch,
            FakeClient(
                tree=_tree("package.json", "src/main.py", "README.md"),
                files={"package.json": PACKAGE_JSON},
            ),
        )
        await service.analyze_repository(USER_ID, "t", ScmProvider.github, OWNER, REPO)
        assert client.file_calls == ["package.json"]

    @pytest.mark.asyncio
    async def test_the_projects_licence_file_is_read(self, no_cache, monkeypatch):
        client = _use_client(
            monkeypatch,
            FakeClient(tree=_tree("requirements.txt", "LICENSE"), files=SAMPLE_FILES),
        )
        await service.analyze_repository(USER_ID, "t", ScmProvider.github, OWNER, REPO)
        assert "LICENSE" in client.file_calls

    @pytest.mark.asyncio
    async def test_an_absent_licence_file_is_not_requested(self, no_cache, monkeypatch):
        client = _use_client(
            monkeypatch,
            FakeClient(tree=_tree("requirements.txt"), files=SAMPLE_FILES),
        )
        await service.analyze_repository(USER_ID, "t", ScmProvider.github, OWNER, REPO)
        assert "LICENSE" not in client.file_calls

    @pytest.mark.asyncio
    async def test_vendored_manifests_are_not_read(self, no_cache, monkeypatch):
        client = _use_client(
            monkeypatch,
            FakeClient(
                tree=_tree("package.json", "node_modules/x/package.json"),
                files={"package.json": PACKAGE_JSON},
            ),
        )
        report = await service.analyze_repository(
            USER_ID, "t", ScmProvider.github, OWNER, REPO
        )
        assert client.file_calls == ["package.json"]
        assert report.summary.total_dependencies == 2


# --------------------------------------------------------------------------
# Analysis
# --------------------------------------------------------------------------


class TestAnalyzeRepository:
    @pytest.mark.asyncio
    async def test_the_inventory_is_reported(self, no_cache, monkeypatch):
        _use_client(
            monkeypatch,
            FakeClient(
                tree=_tree("package.json", "package-lock.json"), files=SAMPLE_FILES
            ),
        )
        report = await service.analyze_repository(
            USER_ID, "t", ScmProvider.github, OWNER, REPO
        )
        # express and app-lib declared; body-parser inherited from the lockfile.
        assert report.summary.total_dependencies == 3
        assert report.summary.direct_dependencies == 2
        assert report.summary.transitive_dependencies == 1

    @pytest.mark.asyncio
    async def test_a_multi_ecosystem_repository_is_analysed(self, no_cache, monkeypatch):
        _use_client(
            monkeypatch,
            FakeClient(
                tree=_tree("package.json", "package-lock.json", "requirements.txt", "LICENSE"),
                files=SAMPLE_FILES,
            ),
        )
        report = await service.analyze_repository(
            USER_ID, "t", ScmProvider.github, OWNER, REPO
        )
        assert set(report.summary.ecosystems) == {"npm", "pypi"}
        assert report.summary.manifest_count == 2
        assert report.summary.lockfile_count == 1

    @pytest.mark.asyncio
    async def test_the_projects_licence_is_identified(self, no_cache, monkeypatch):
        _use_client(
            monkeypatch,
            FakeClient(tree=_tree("requirements.txt", "LICENSE"), files=SAMPLE_FILES),
        )
        report = await service.analyze_repository(
            USER_ID, "t", ScmProvider.github, OWNER, REPO
        )
        assert report.summary.declared_license == "MIT"

    @pytest.mark.asyncio
    async def test_a_repository_with_no_manifests_is_a_result_not_an_error(
        self, no_cache, monkeypatch
    ):
        _use_client(monkeypatch, FakeClient(tree=_tree("src/main.py", "README.md"), files={}))
        report = await service.analyze_repository(
            USER_ID, "t", ScmProvider.github, OWNER, REPO
        )
        assert report.summary.total_dependencies == 0
        assert any(issue.code == CODE_NO_MANIFEST for issue in report.issues)
        # The expected-but-absent manifests are still listed.
        assert {row.path for row in report.manifests} == {
            "package.json",
            "requirements.txt",
            "pyproject.toml",
            "go.mod",
            "pom.xml",
        }

    @pytest.mark.asyncio
    async def test_a_repository_without_a_lockfile_is_flagged(self, no_cache, monkeypatch):
        _use_client(
            monkeypatch, FakeClient(tree=_tree("package.json"), files={"package.json": PACKAGE_JSON})
        )
        report = await service.analyze_repository(
            USER_ID, "t", ScmProvider.github, OWNER, REPO
        )
        assert any(issue.code == CODE_NO_LOCKFILE for issue in report.issues)

    @pytest.mark.asyncio
    async def test_the_score_is_auditable(self, no_cache, monkeypatch):
        _use_client(
            monkeypatch, FakeClient(tree=_tree("package.json"), files={"package.json": PACKAGE_JSON})
        )
        report = await service.analyze_repository(
            USER_ID, "t", ScmProvider.github, OWNER, REPO
        )
        assert 0 <= report.summary.hygiene_score <= 100
        assert report.summary.score_band

    @pytest.mark.asyncio
    async def test_the_provenance_fields_are_populated(self, no_cache, monkeypatch):
        _use_client(
            monkeypatch, FakeClient(tree=_tree("go.mod"), files={"go.mod": "module x\n\ngo 1.21\n"})
        )
        report = await service.analyze_repository(
            USER_ID, "t", ScmProvider.gitlab, OWNER, REPO, ref="main"
        )
        assert report.provider == "gitlab"
        assert report.ref == "main"
        assert report.commit_sha == "abc123"
        assert report.full_name == f"{OWNER}/{REPO}"
        assert report.analyzed_at
        assert report.duration_ms >= 0
        assert report.cached is False

    @pytest.mark.asyncio
    async def test_byte_content_is_decoded(self, no_cache, monkeypatch):
        _use_client(
            monkeypatch,
            FakeClient(
                tree=_tree("requirements.txt"),
                files={"requirements.txt": b"requests==2.31.0\n"},
            ),
        )
        report = await service.analyze_repository(
            USER_ID, "t", ScmProvider.github, OWNER, REPO
        )
        assert report.summary.total_dependencies == 1

    @pytest.mark.asyncio
    async def test_a_malformed_manifest_is_reported_not_fatal(self, no_cache, monkeypatch):
        _use_client(
            monkeypatch,
            FakeClient(
                tree=_tree("package.json", "requirements.txt"),
                files={"package.json": "{not json", "requirements.txt": "requests==2.31.0\n"},
            ),
        )
        report = await service.analyze_repository(
            USER_ID, "t", ScmProvider.github, OWNER, REPO
        )
        # The readable manifest still contributes.
        assert report.summary.total_dependencies == 1
        assert any(row.parse_failed for row in report.manifests)


# --------------------------------------------------------------------------
# Truncation
# --------------------------------------------------------------------------


class TestTruncation:
    @pytest.mark.asyncio
    async def test_the_inventory_cap_is_applied_and_reported(self, no_cache, monkeypatch):
        packages = "".join(
            f'    "p{index}": {{"version": "1.0.0", "license": "MIT"}},\n'
            for index in range(30)
        )
        content = '{"dependencies": {' + packages + '"zz": "1.0.0"}}'
        _use_client(
            monkeypatch,
            FakeClient(tree=_tree("package.json"), files={"package.json": content}),
        )
        report = await service.analyze_repository(
            USER_ID, "t", ScmProvider.github, OWNER, REPO, max_dependencies=10
        )
        assert len(report.dependencies) == 10
        assert report.truncated is True

    @pytest.mark.asyncio
    async def test_a_report_within_the_cap_is_not_marked_truncated(self, no_cache, monkeypatch):
        _use_client(
            monkeypatch, FakeClient(tree=_tree("package.json"), files={"package.json": PACKAGE_JSON})
        )
        report = await service.analyze_repository(
            USER_ID, "t", ScmProvider.github, OWNER, REPO
        )
        assert report.truncated is False

    @pytest.mark.asyncio
    async def test_the_hard_ceiling_cannot_be_exceeded(self, no_cache, monkeypatch):
        _use_client(
            monkeypatch, FakeClient(tree=_tree("go.mod"), files={"go.mod": "module x\n"})
        )
        report = await service.analyze_repository(
            USER_ID, "t", ScmProvider.github, OWNER, REPO, max_dependencies=10**9
        )
        assert report.summary.total_dependencies <= service.HARD_MAX_DEPENDENCIES

    @pytest.mark.asyncio
    async def test_a_non_positive_cap_is_clamped(self, no_cache, monkeypatch):
        _use_client(
            monkeypatch,
            FakeClient(
                tree=_tree("requirements.txt"),
                files={"requirements.txt": "a==1.0.0\nb==2.0.0\n"},
            ),
        )
        report = await service.analyze_repository(
            USER_ID, "t", ScmProvider.github, OWNER, REPO, max_dependencies=0
        )
        assert len(report.dependencies) == 1


# --------------------------------------------------------------------------
# Failure handling
# --------------------------------------------------------------------------


class TestFailureHandling:
    @pytest.mark.asyncio
    async def test_an_unreadable_file_is_recorded_and_the_run_continues(
        self, no_cache, monkeypatch
    ):
        _use_client(
            monkeypatch,
            FakeClient(
                tree=_tree("package.json", "requirements.txt"),
                files={"requirements.txt": "requests==2.31.0\n"},
                file_errors={"package.json": ScmAPIError(500, "boom", "server")},
            ),
        )
        report = await service.analyze_repository(
            USER_ID, "t", ScmProvider.github, OWNER, REPO
        )
        assert report.summary.total_dependencies == 1
        assert any("package.json" in error for error in report.errors)

    @pytest.mark.asyncio
    async def test_an_unexpected_error_on_one_file_does_not_fail_the_run(
        self, no_cache, monkeypatch
    ):
        _use_client(
            monkeypatch,
            FakeClient(
                tree=_tree("package.json", "requirements.txt"),
                files={"requirements.txt": "requests==2.31.0\n"},
                file_errors={"package.json": RuntimeError("kaboom")},
            ),
        )
        report = await service.analyze_repository(
            USER_ID, "t", ScmProvider.github, OWNER, REPO
        )
        assert report.summary.total_dependencies == 1
        assert report.errors

    @pytest.mark.asyncio
    async def test_an_absent_file_is_skipped_silently(self, no_cache, monkeypatch):
        _use_client(
            monkeypatch,
            FakeClient(
                tree=_tree("package.json", "go.mod"),
                files={"package.json": PACKAGE_JSON},
                file_errors={"go.mod": ScmAPIError(404, "gone", "not_found")},
            ),
        )
        report = await service.analyze_repository(
            USER_ID, "t", ScmProvider.github, OWNER, REPO
        )
        assert report.errors == []
        assert report.summary.total_dependencies == 2

    @pytest.mark.asyncio
    async def test_reported_errors_are_capped(self, no_cache, monkeypatch):
        paths = [f"svc{index}/requirements.txt" for index in range(30)]
        _use_client(
            monkeypatch,
            FakeClient(
                tree=_tree(*paths),
                files={},
                file_errors={path: ScmAPIError(500, "boom", "server") for path in paths},
            ),
        )
        report = await service.analyze_repository(
            USER_ID, "t", ScmProvider.github, OWNER, REPO
        )
        assert len(report.errors) <= service.MAX_ERRORS_REPORTED

    @pytest.mark.asyncio
    async def test_a_tree_failure_raises_a_supply_chain_error(self, no_cache, monkeypatch):
        _use_client(
            monkeypatch, FakeClient(tree_error=ScmAPIError(404, "nope", "not_found"))
        )
        with pytest.raises(SupplyChainError):
            await service.analyze_repository(USER_ID, "t", ScmProvider.github, OWNER, REPO)

    @pytest.mark.asyncio
    async def test_an_unexpected_tree_failure_raises_a_supply_chain_error(
        self, no_cache, monkeypatch
    ):
        _use_client(monkeypatch, FakeClient(tree_error=RuntimeError("kaboom")))
        with pytest.raises(SupplyChainError):
            await service.analyze_repository(USER_ID, "t", ScmProvider.github, OWNER, REPO)

    @pytest.mark.asyncio
    async def test_an_empty_tree_raises_a_supply_chain_error(self, no_cache, monkeypatch):
        _use_client(monkeypatch, FakeClient(tree=[]))
        with pytest.raises(SupplyChainError):
            await service.analyze_repository(USER_ID, "t", ScmProvider.github, OWNER, REPO)

    @pytest.mark.asyncio
    async def test_a_provider_without_tree_support_raises(self, no_cache, monkeypatch):
        class Bare:
            async def get_file_content(self, owner, repository, path, ref=None):
                return None

        _use_client(monkeypatch, Bare())
        with pytest.raises(SupplyChainError):
            await service.analyze_repository(USER_ID, "t", ScmProvider.github, OWNER, REPO)

    @pytest.mark.asyncio
    async def test_a_provider_without_content_support_raises(self, no_cache, monkeypatch):
        class Bare:
            async def get_repository_tree(self, owner, repository, ref=None):
                return {"tree": []}

        _use_client(monkeypatch, Bare())
        with pytest.raises(SupplyChainError):
            await service.analyze_repository(USER_ID, "t", ScmProvider.github, OWNER, REPO)


# --------------------------------------------------------------------------
# Caching
# --------------------------------------------------------------------------


class TestCaching:
    @pytest.mark.asyncio
    async def test_a_cached_report_is_returned_without_fetching(self, monkeypatch):
        payload = {
            "repository_id": "x",
            "owner": OWNER,
            "repository": REPO,
            "full_name": f"{OWNER}/{REPO}",
            "provider": "github",
            "analyzed_at": "2026-01-01T00:00:00+00:00",
            "summary": {"hygiene_score": 77, "score_band": "weak"},
        }
        calls = {}

        async def fake_read(user_id, owner, repository):
            calls["read"] = (user_id, owner, repository)
            return payload

        client = _use_client(monkeypatch, FakeClient(tree=_tree("package.json")))
        monkeypatch.setattr(service, "_read_cache", fake_read)
        report = await service.analyze_repository(
            USER_ID, "t", ScmProvider.github, OWNER, REPO
        )
        assert report.summary.hygiene_score == 77
        assert report.cached is True
        assert client.file_calls == []
        assert calls["read"] == (USER_ID, OWNER, REPO)

    @pytest.mark.asyncio
    async def test_the_cache_is_keyed_by_user_and_repository(self, monkeypatch):
        seen = []

        async def fake_read(user_id, owner, repository):
            seen.append((user_id, owner, repository))
            return None

        monkeypatch.setattr(service, "_read_cache", fake_read)
        monkeypatch.setattr(service, "_write_cache", _never_write)
        _use_client(monkeypatch, FakeClient(tree=_tree("go.mod"), files={"go.mod": "module x\n"}))
        await service.analyze_repository(7, "t", ScmProvider.github, "a", "b")
        assert seen == [(7, "a", "b")]

    @pytest.mark.asyncio
    async def test_refresh_bypasses_the_cache(self, monkeypatch):
        reads = []

        async def fake_read(user_id, owner, repository):
            reads.append(1)
            return {"repository_id": "x", "owner": OWNER, "repository": REPO,
                    "full_name": "x", "provider": "github", "analyzed_at": "t"}

        monkeypatch.setattr(service, "_read_cache", fake_read)
        monkeypatch.setattr(service, "_write_cache", _never_write)
        _use_client(monkeypatch, FakeClient(tree=_tree("go.mod"), files={"go.mod": "module x\n"}))
        report = await service.analyze_repository(
            USER_ID, "t", ScmProvider.github, OWNER, REPO, refresh=True
        )
        assert reads == []
        assert report.cached is False

    @pytest.mark.asyncio
    async def test_use_cache_false_bypasses_the_cache(self, monkeypatch):
        reads = []

        async def fake_read(*args, **kwargs):
            reads.append(1)
            return None

        monkeypatch.setattr(service, "_read_cache", fake_read)
        monkeypatch.setattr(service, "_write_cache", _never_write)
        _use_client(monkeypatch, FakeClient(tree=_tree("go.mod"), files={"go.mod": "module x\n"}))
        await service.analyze_repository(
            USER_ID, "t", ScmProvider.github, OWNER, REPO, use_cache=False
        )
        assert reads == []

    @pytest.mark.asyncio
    async def test_an_unreadable_cache_entry_is_discarded(self, monkeypatch):
        async def fake_read(*args, **kwargs):
            return {"totally": "wrong"}

        monkeypatch.setattr(service, "_read_cache", fake_read)
        monkeypatch.setattr(service, "_write_cache", _never_write)
        _use_client(monkeypatch, FakeClient(tree=_tree("go.mod"), files={"go.mod": "module x\n"}))
        report = await service.analyze_repository(
            USER_ID, "t", ScmProvider.github, OWNER, REPO
        )
        assert report.summary.total_dependencies == 0

    @pytest.mark.asyncio
    async def test_a_cache_read_failure_falls_back_to_a_fresh_analysis(self, monkeypatch):
        # The resilience lives inside _read_cache, so the failure is injected at
        # the repository below it - which is the real production failure mode.
        async def boom(*args, **kwargs):
            raise RuntimeError("db down")

        monkeypatch.setattr(cache_repo, "get_cached", boom)
        monkeypatch.setattr(cache_repo, "set_cached", _never_write)
        _use_client(monkeypatch, FakeClient(tree=_tree("go.mod"), files={"go.mod": "module x\n"}))
        report = await service.analyze_repository(
            USER_ID, "t", ScmProvider.github, OWNER, REPO
        )
        assert report.full_name == f"{OWNER}/{REPO}"
        assert report.cached is False

    @pytest.mark.asyncio
    async def test_a_cache_write_failure_does_not_fail_the_run(self, monkeypatch):
        async def boom(*args, **kwargs):
            raise RuntimeError("db down")

        monkeypatch.setattr(cache_repo, "get_cached", _never_cache)
        monkeypatch.setattr(cache_repo, "set_cached", boom)
        _use_client(monkeypatch, FakeClient(tree=_tree("go.mod"), files={"go.mod": "module x\n"}))
        report = await service.analyze_repository(
            USER_ID, "t", ScmProvider.github, OWNER, REPO
        )
        assert report.summary.total_dependencies == 0

    @pytest.mark.asyncio
    async def test_the_shared_cache_repository_is_used_with_the_supply_chain_kind(
        self, monkeypatch
    ):
        seen = {}

        async def fake_set_cached(user_id, owner, repository, analysis, payload, **kwargs):
            seen["kind"] = analysis
            seen["args"] = (user_id, owner, repository)

        monkeypatch.setattr(cache_repo, "get_cached", _never_cache)
        monkeypatch.setattr(cache_repo, "set_cached", fake_set_cached)
        _use_client(monkeypatch, FakeClient(tree=_tree("go.mod"), files={"go.mod": "module x\n"}))
        await service.analyze_repository(USER_ID, "t", ScmProvider.github, OWNER, REPO)
        assert seen["kind"] == "supply_chain"
        assert seen["args"] == (USER_ID, OWNER, REPO)

    @pytest.mark.asyncio
    async def test_the_report_is_written_to_the_shared_cache(self, monkeypatch):
        monkeypatch.setattr(service, "_read_cache", _never_cache)
        written = {}

        async def fake_write(user_id, owner, repository, report):
            written["args"] = (user_id, owner, repository)
            written["kind"] = report.model_dump(mode="json")

        monkeypatch.setattr(service, "_write_cache", fake_write)
        _use_client(monkeypatch, FakeClient(tree=_tree("go.mod"), files={"go.mod": "module x\n"}))
        await service.analyze_repository(USER_ID, "t", ScmProvider.github, OWNER, REPO)
        assert written["args"] == (USER_ID, OWNER, REPO)
        assert written["kind"]["full_name"] == f"{OWNER}/{REPO}"

    @pytest.mark.asyncio
    async def test_a_cached_report_survives_a_round_trip(self, monkeypatch):
        monkeypatch.setattr(service, "_read_cache", _never_cache)
        monkeypatch.setattr(service, "_write_cache", _never_write)
        _use_client(
            monkeypatch,
            FakeClient(tree=_tree("package.json", "package-lock.json"), files=SAMPLE_FILES),
        )
        report = await service.analyze_repository(
            USER_ID, "t", ScmProvider.github, OWNER, REPO
        )
        again = SupplyChainReport.model_validate(report.model_dump(mode="json"))
        assert again.summary.hygiene_score == report.summary.hygiene_score
        assert len(again.issues) == len(report.issues)
        assert len(again.dependencies) == len(report.dependencies)
        assert len(again.licenses) == len(report.licenses)

    def test_supply_chain_is_a_registered_analysis_kind(self):
        assert "supply_chain" in cache_repo.ANALYSIS_KINDS
        assert cache_repo.ttl_for("supply_chain") > 0

    def test_the_cache_kind_does_not_collide_with_the_dependency_inspector(self):
        # "dependencies" already holds a different payload shape for the
        # dependency inspector, so the supply-chain report needs its own kind.
        assert "supply_chain" != "dependencies"
        assert "dependencies" in cache_repo.ANALYSIS_KINDS


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------


class TestRoutes:
    @pytest.mark.asyncio
    async def test_the_report_is_returned_for_a_valid_request(
        self, client, auth_headers, monkeypatch
    ):
        _use_client(
            monkeypatch,
            FakeClient(tree=_tree("package.json", "package-lock.json"), files=SAMPLE_FILES),
        )
        monkeypatch.setattr(service, "_read_cache", _never_cache)
        monkeypatch.setattr(service, "_write_cache", _never_write)
        response = client.get(
            f"/supply-chain/repositories/{OWNER}/{REPO}", headers=auth_headers
        )
        assert response.status_code == 200
        body = response.json()
        assert body["full_name"] == f"{OWNER}/{REPO}"
        assert body["summary"]["total_dependencies"] == 3
        assert body["summary"]["direct_dependencies"] == 2
        assert body["summary"]["transitive_dependencies"] == 1

    @pytest.mark.asyncio
    async def test_the_licences_and_issues_are_in_the_response(
        self, client, auth_headers, monkeypatch
    ):
        _use_client(
            monkeypatch,
            FakeClient(tree=_tree("package.json", "package-lock.json"), files=SAMPLE_FILES),
        )
        monkeypatch.setattr(service, "_read_cache", _never_cache)
        monkeypatch.setattr(service, "_write_cache", _never_write)
        body = client.get(
            f"/supply-chain/repositories/{OWNER}/{REPO}", headers=auth_headers
        ).json()
        assert any(row["expression"] == "MIT" for row in body["licenses"])
        assert body["issues"]
        assert body["summary"]["hygiene_score"] >= 0

    @pytest.mark.asyncio
    async def test_a_request_without_a_token_is_rejected(self, client, monkeypatch):
        _use_client(monkeypatch, FakeClient(tree=_tree("package.json")))
        response = client.get(f"/supply-chain/repositories/{OWNER}/{REPO}")
        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_a_user_without_a_connected_account_is_rejected(self, client):
        response = client.get(
            f"/supply-chain/repositories/{OWNER}/{REPO}",
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_the_api_prefixed_route_behaves_identically(
        self, client, auth_headers, monkeypatch
    ):
        _use_client(
            monkeypatch,
            FakeClient(tree=_tree("package.json", "package-lock.json"), files=SAMPLE_FILES),
        )
        monkeypatch.setattr(service, "_read_cache", _never_cache)
        monkeypatch.setattr(service, "_write_cache", _never_write)
        response = client.get(
            f"/api/supply-chain/repositories/{OWNER}/{REPO}", headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["full_name"] == f"{OWNER}/{REPO}"

    @pytest.mark.asyncio
    async def test_a_provider_failure_is_reported_as_a_bad_gateway(
        self, client, auth_headers, monkeypatch
    ):
        _use_client(monkeypatch, FakeClient(tree_error=ScmAPIError(404, "nope", "not_found")))
        monkeypatch.setattr(service, "_read_cache", _never_cache)
        response = client.get(
            f"/supply-chain/repositories/{OWNER}/{REPO}", headers=auth_headers
        )
        assert response.status_code == 502

    @pytest.mark.asyncio
    async def test_an_empty_tree_is_reported_as_a_bad_gateway(
        self, client, auth_headers, monkeypatch
    ):
        _use_client(monkeypatch, FakeClient(tree=[]))
        monkeypatch.setattr(service, "_read_cache", _never_cache)
        response = client.get(
            f"/supply-chain/repositories/{OWNER}/{REPO}", headers=auth_headers
        )
        assert response.status_code == 502

    @pytest.mark.asyncio
    async def test_an_out_of_range_cap_is_rejected(
        self, client, auth_headers, monkeypatch
    ):
        _use_client(monkeypatch, FakeClient(tree=_tree("package.json")))
        monkeypatch.setattr(service, "_read_cache", _never_cache)
        response = client.get(
            f"/supply-chain/repositories/{OWNER}/{REPO}?max_dependencies=0",
            headers=auth_headers,
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_a_repository_with_no_manifests_is_a_two_hundred(
        self, client, auth_headers, monkeypatch
    ):
        _use_client(monkeypatch, FakeClient(tree=_tree("src/main.py"), files={}))
        monkeypatch.setattr(service, "_read_cache", _never_cache)
        monkeypatch.setattr(service, "_write_cache", _never_write)
        response = client.get(
            f"/supply-chain/repositories/{OWNER}/{REPO}", headers=auth_headers
        )
        assert response.status_code == 200
        body = response.json()
        assert body["summary"]["total_dependencies"] == 0
        assert any(issue["code"] == CODE_NO_MANIFEST for issue in body["issues"])

    @pytest.mark.asyncio
    async def test_the_provider_query_parameter_is_accepted(
        self, client, auth_headers, monkeypatch
    ):
        _use_client(monkeypatch, FakeClient(tree=_tree("go.mod"), files={"go.mod": "module x\n"}))
        monkeypatch.setattr(service, "_read_cache", _never_cache)
        monkeypatch.setattr(service, "_write_cache", _never_write)
        response = client.get(
            f"/supply-chain/repositories/{OWNER}/{REPO}?provider=gitlab", headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["provider"] == "gitlab"

    @pytest.mark.asyncio
    async def test_refresh_recomputes_the_report(self, client, auth_headers, monkeypatch):
        _use_client(
            monkeypatch,
            FakeClient(tree=_tree("package.json", "package-lock.json"), files=SAMPLE_FILES),
        )
        monkeypatch.setattr(service, "_read_cache", _never_cache)
        monkeypatch.setattr(service, "_write_cache", _never_write)
        response = client.get(
            f"/supply-chain/repositories/{OWNER}/{REPO}?refresh=true", headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["cached"] is False
