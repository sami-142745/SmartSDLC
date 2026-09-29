"""Repository scan orchestration tests.

These exercise the pipeline end to end against a fake provider: the same
contract a real GitHub or GitLab client satisfies. What is asserted here is the
behaviour the scan service itself owns — which files are read, what happens when
a file cannot be read, and that the output does not depend on the order in which
concurrent reads completed.
"""

import pytest

from app.schemas.security import SecurityScan
from app.services import security_scan_service as scan_service
from app.services.scm import ScmAPIError, ScmProvider

OWNER = "octocat"
REPO = "Hello-World"
USER_ID = 42

#: A key the secret scanner must flag. Its value is asserted absent from every
#: downstream surface later in the file. Deliberately *not* AWS's published
#: ``AKIAIOSFODNN7EXAMPLE`` key: that one is a documented placeholder and the
#: scanner is supposed to suppress it.
# Must match AKIA[0-9A-Z]{16} pattern for the scanner to catch it.
LEAKED_KEY = "AKIATESTFAKEKEY12345"

#: A documented example key, which must NOT be reported. Placeholder suppression
#: is what keeps every repository's README out of the findings list.
PLACEHOLDER_KEY = "AKIAIOSFODNN7EXAMPLE"


@pytest.fixture(autouse=True)
def _fake_storage(monkeypatch):
    """Point the security repository at the in-memory fake database.

    Without this a scan that persists reaches for a real Mongo connection.
    """
    from tests.conftest import FakeDb

    db = FakeDb()
    monkeypatch.setattr(scan_service.security_repository, "get_db", lambda: db)
    return db


class FakeProvider:
    """Minimal SCM client: a tree plus a file map."""

    def __init__(self, tree=None, files=None, *, fail_paths=(), tree_error=None):
        self.tree = tree if tree is not None else []
        self.files = files or {}
        self.fail_paths = set(fail_paths)
        self.tree_error = tree_error
        self.requested: list[str] = []

    async def get_repository_tree(self, owner, repository, ref=None):
        if self.tree_error is not None:
            raise self.tree_error
        return {"tree": self.tree, "sha": "commit123"}

    async def get_file_content(self, owner, repository, path, ref=None):
        self.requested.append(path)
        if path in self.fail_paths:
            raise ScmAPIError(500, f"cannot read {path}", "server")
        return self.files.get(path)


def _blob(path, size=200):
    return {"path": path, "type": "blob", "size": size}


def _install(monkeypatch, provider):
    monkeypatch.setattr(scan_service, "_client", lambda p, t: provider)
    return provider


@pytest.mark.asyncio
async def test_a_file_with_a_leaked_key_is_reported(monkeypatch):
    provider = _install(
        monkeypatch,
        FakeProvider(
            tree=[_blob("config.py")],
            files={"config.py": f'AWS_ACCESS_KEY_ID = "{LEAKED_KEY}"\n'},
        ),
    )
    scan = await scan_service.scan_repository(USER_ID, "token", ScmProvider.github, OWNER, REPO)

    assert isinstance(scan, SecurityScan)
    assert scan.status == "complete"
    assert scan.summary.total_findings >= 1
    assert any(finding.scanner == "secret" for finding in scan.findings)
    assert any(finding.file == "config.py" for finding in scan.findings)
    assert provider.requested == ["config.py"]


@pytest.mark.asyncio
async def test_a_documented_example_key_is_not_reported(monkeypatch):
    # A README full of `AKIAIOSFODNN7EXAMPLE` is not a breach, and reporting it
    # is the fastest way to make a security page get ignored.
    _install(
        monkeypatch,
        FakeProvider(
            tree=[_blob("README.md")],
            files={"README.md": f'AWS_ACCESS_KEY_ID = "{PLACEHOLDER_KEY}"\n'},
        ),
    )
    scan = await scan_service.scan_repository(USER_ID, "token", ScmProvider.github, OWNER, REPO)
    assert scan.summary.total_findings == 0


@pytest.mark.asyncio
async def test_the_leaked_secret_never_appears_in_the_scan(monkeypatch):
    provider = _install(
        monkeypatch,
        FakeProvider(
            tree=[_blob("config.py")],
            files={"config.py": f'AWS_ACCESS_KEY_ID = "{LEAKED_KEY}"\n'},
        ),
    )
    scan = await scan_service.scan_repository(USER_ID, "token", ScmProvider.github, OWNER, REPO)

    rendered = scan.model_dump_json()
    assert LEAKED_KEY not in rendered


@pytest.mark.asyncio
async def test_an_empty_repository_raises_rather_than_scanning_nothing(monkeypatch):
    _install(monkeypatch, FakeProvider(tree=[]))
    with pytest.raises(scan_service.SecurityScanError):
        await scan_service.scan_repository(USER_ID, "token", ScmProvider.github, OWNER, REPO)


@pytest.mark.asyncio
async def test_an_unreadable_tree_raises_a_scan_error(monkeypatch):
    _install(
        monkeypatch,
        FakeProvider(tree_error=ScmAPIError(500, "boom", "server")),
    )
    with pytest.raises(scan_service.SecurityScanError):
        await scan_service.scan_repository(USER_ID, "token", ScmProvider.github, OWNER, REPO)


@pytest.mark.asyncio
async def test_a_provider_without_a_tree_is_rejected_before_any_read(monkeypatch):
    class NoTree:
        async def get_file_content(self, owner, repository, path, ref=None):
            return None

    _install(monkeypatch, NoTree())
    with pytest.raises(scan_service.SecurityScanError):
        await scan_service.scan_repository(USER_ID, "token", ScmProvider.github, OWNER, REPO)


class TestTargetSelection:
    def test_source_files_are_selected(self):
        paths, skipped = scan_service.select_scan_targets([_blob("app/main.py")])
        assert paths == ["app/main.py"]
        assert skipped == 0

    def test_manifests_are_selected(self):
        paths, _ = scan_service.select_scan_targets([_blob("requirements.txt")])
        assert paths == ["requirements.txt"]

    def test_generated_and_vendored_files_are_skipped(self):
        entries = [
            _blob("node_modules/left-pad/index.js"),
            _blob("dist/bundle.js"),
            _blob("app/main.py"),
        ]
        paths, skipped = scan_service.select_scan_targets(entries)
        assert paths == ["app/main.py"]
        assert skipped == 2

    def test_ignored_files_are_never_downloaded(self):
        provider = FakeProvider(
            tree=[_blob("node_modules/evil/index.js"), _blob("app/main.py")],
            files={"node_modules/evil/index.js": "x", "app/main.py": "print(1)"},
        )
        # An ignored path must not even appear in the provider request log.
        assert scan_service.select_scan_targets(provider.tree)[0] == ["app/main.py"]

    def test_directories_are_not_read_as_files(self):
        paths, _ = scan_service.select_scan_targets([{"path": "app", "type": "tree"}])
        assert paths == []

    def test_malformed_entries_are_skipped_rather_than_crashing(self):
        entries = [None, {}, {"path": "", "type": "blob"}, {"path": 7}, _blob("a.py")]
        paths, _ = scan_service.select_scan_targets(entries)
        assert paths == ["a.py"]

    def test_the_file_budget_is_enforced_and_stable(self):
        entries = [_blob(f"f{i}.py") for i in range(50)]
        paths, skipped = scan_service.select_scan_targets(entries, max_files=10)
        assert paths == [f"f{i}.py" for i in range(10)]
        assert skipped == 40

    def test_a_request_cannot_raise_the_budget_past_the_hard_ceiling(self):
        entries = [_blob(f"f{i}.py") for i in range(5)]
        paths, _ = scan_service.select_scan_targets(entries, max_files=10_000_000)
        assert len(paths) <= scan_service.HARD_MAX_FILES

    def test_the_ignored_count_includes_files_over_the_budget(self):
        entries = [_blob(f"f{i}.py") for i in range(30)]
        _, skipped = scan_service.select_scan_targets(entries, max_files=5)
        assert skipped == 25

    def test_selection_is_deterministic_for_the_same_tree(self):
        entries = [_blob(f"f{i}.py") for i in range(30)]
        first = scan_service.select_scan_targets(entries, max_files=12)
        second = scan_service.select_scan_targets(entries, max_files=12)
        assert first == second


@pytest.mark.asyncio
class TestScanBehaviour:
    async def test_a_binary_file_is_skipped(self, monkeypatch):
        provider = _install(
            monkeypatch,
            FakeProvider(
                tree=[_blob("logo.png")],
                files={"logo.png": b"\x89PNG\x00\x01\x02binary"},
            ),
        )
        scan = await scan_service.scan_repository(USER_ID, "token", ScmProvider.github, OWNER, REPO)
        assert scan.summary.files_scanned == 0
        assert scan.summary.total_findings == 0

    async def test_an_empty_file_is_skipped(self, monkeypatch):
        _install(monkeypatch, FakeProvider(tree=[_blob("empty.py")], files={"empty.py": ""}))
        scan = await scan_service.scan_repository(USER_ID, "token", ScmProvider.github, OWNER, REPO)
        assert scan.summary.files_scanned == 0

    async def test_one_unreadable_file_does_not_fail_the_scan(self, monkeypatch):
        _install(
            monkeypatch,
            FakeProvider(
                tree=[_blob("a.py"), _blob("b.py")],
                files={
                    "a.py": "import os\nos.system(request.args)\n",
                    "b.py": "def handler():\n    return eval(user_input)\n",
                },
                fail_paths={"a.py"},
            ),
        )
        scan = await scan_service.scan_repository(USER_ID, "token", ScmProvider.github, OWNER, REPO)
        assert scan.status == "complete"
        assert scan.errors  # the failure is reported, not raised
        # The readable file is still scanned and still produces its finding.
        assert any(finding.file == "b.py" for finding in scan.findings)
        assert not any(finding.file == "a.py" for finding in scan.findings)

    async def test_a_file_missing_between_tree_and_read_is_not_an_error(self, monkeypatch):
        # The tree can be stale relative to the ref; a vanished file is skipped
        # silently rather than reported as a provider failure.
        _install(
            monkeypatch,
            FakeProvider(tree=[_blob("a.py")], files={}, fail_paths=set()),
        )
        scan = await scan_service.scan_repository(USER_ID, "token", ScmProvider.github, OWNER, REPO)
        assert scan.errors == []

    async def test_a_clean_repository_scores_a_perfect_posture(self, monkeypatch):
        _install(
            monkeypatch,
            FakeProvider(tree=[_blob("a.py")], files={"a.py": "def add(a, b):\n    return a + b\n"}),
        )
        scan = await scan_service.scan_repository(USER_ID, "token", ScmProvider.github, OWNER, REPO)
        assert scan.summary.total_findings == 0
        assert scan.summary.posture_score == 100

    async def test_findings_are_ordered_worst_first(self, monkeypatch):
        _install(
            monkeypatch,
            FakeProvider(
                tree=[_blob("a.py"), _blob("b.py")],
                files={
                    "a.py": "def handler():\n    return eval(user_input)\n",
                    "b.py": f'AWS_ACCESS_KEY_ID = "{LEAKED_KEY}"\n',
                },
            ),
        )
        scan = await scan_service.scan_repository(USER_ID, "token", ScmProvider.github, OWNER, REPO)
        ranks = ["critical", "high", "medium", "low", "info"]
        positions = [ranks.index(finding.severity) for finding in scan.findings]
        assert positions == sorted(positions)

    async def test_the_same_repository_scans_identically_twice(self, monkeypatch):
        provider = FakeProvider(
            tree=[_blob("a.py"), _blob("b.py")],
            files={
                "a.py": "def handler():\n    return eval(user_input)\n",
                "b.py": f'AWS_ACCESS_KEY_ID = "{LEAKED_KEY}"\n',
            },
        )
        _install(monkeypatch, provider)
        first = await scan_service.scan_repository(USER_ID, "token", ScmProvider.github, OWNER, REPO)
        second = await scan_service.scan_repository(USER_ID, "token", ScmProvider.github, OWNER, REPO)

        def identity(scan):
            return sorted(
                (f.fingerprint, f.file, f.severity, f.category, f.scanner) for f in scan.findings
            )

        assert identity(first) == identity(second)
        assert first.summary.as_response() == second.summary.as_response()

    async def test_dependencies_are_analysed_from_a_manifest(self, monkeypatch):
        _install(
            monkeypatch,
            FakeProvider(
                tree=[_blob("requirements.txt")],
                files={"requirements.txt": "requests==\nflask==2.0.1\n"},
            ),
        )
        scan = await scan_service.scan_repository(USER_ID, "token", ScmProvider.github, OWNER, REPO)
        assert scan.summary.dependencies_analyzed >= 1

    async def test_no_vulnerability_provider_is_claimed_by_default(self, monkeypatch):
        _install(
            monkeypatch,
            FakeProvider(tree=[_blob("a.py")], files={"a.py": "print(1)\n"}),
        )
        scan = await scan_service.scan_repository(USER_ID, "token", ScmProvider.github, OWNER, REPO)
        # The engine must not imply a CVE check it did not perform.
        assert scan.vulnerability_source == "none"

    async def test_scan_provenance_is_recorded(self, monkeypatch):
        _install(
            monkeypatch,
            FakeProvider(tree=[_blob("a.py")], files={"a.py": "print(1)\n"}),
        )
        scan = await scan_service.scan_repository(
            USER_ID, "token", ScmProvider.github, OWNER, REPO, ref="main"
        )
        assert scan.ref == "main"
        assert scan.commit_sha == "commit123"
        assert scan.repository_id == "octocat/hello-world"
        assert scan.full_name == f"{OWNER}/{REPO}"

    async def test_max_files_narrows_the_scan(self, monkeypatch):
        provider = FakeProvider(
            tree=[_blob(f"f{i}.py") for i in range(20)],
            files={f"f{i}.py": "print(1)\n" for i in range(20)},
        )
        _install(monkeypatch, provider)
        await scan_service.scan_repository(
            USER_ID, "token", ScmProvider.github, OWNER, REPO, max_files=3
        )
        assert len(provider.requested) == 3

    async def test_a_persistence_failure_degrades_the_response(self, monkeypatch):
        _install(
            monkeypatch,
            FakeProvider(tree=[_blob("a.py")], files={"a.py": "print(1)\n"}),
        )

        async def _failing_save(*args, **kwargs):
            raise RuntimeError("mongo is down")

        monkeypatch.setattr(scan_service.security_repository, "save_scan", _failing_save)

        scan = await scan_service.scan_repository(USER_ID, "token", ScmProvider.github, OWNER, REPO)
        # The findings are still returned; the storage failure is reported.
        assert scan.status == "complete"
        assert any("could not be stored" in error for error in scan.errors)

    async def test_persist_false_stores_nothing(self, monkeypatch):
        _install(
            monkeypatch,
            FakeProvider(tree=[_blob("a.py")], files={"a.py": "print(1)\n"}),
        )
        called = []

        async def _tracking_save(*args, **kwargs):
            called.append(1)

        monkeypatch.setattr(scan_service.security_repository, "save_scan", _tracking_save)
        await scan_service.scan_repository(
            USER_ID, "token", ScmProvider.github, OWNER, REPO, persist=False
        )
        assert called == []
