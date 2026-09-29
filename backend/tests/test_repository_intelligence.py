"""Tests for the Repository Intelligence module.

Split into three concerns:

* pure service unit tests (health scoring, language folding, manifest parsing,
  README analysis, tree building) that need no I/O and no provider token;
* repository-level tests for the MongoDB cache, including TTL expiry;
* router tests that stub the SCM client and assert the HTTP contract.

Every test that touches the cache patches ``get_db`` on the new repository, so
no test can reach a real MongoDB.
"""

import asyncio
import datetime

import pytest

from app.services import (
    repository_analysis_repository,
    repository_dependency_service,
    repository_explorer_service,
    repository_health_service,
    repository_intelligence_service,
    repository_language_service,
    repository_readme_service,
)
from app.services.repository_intelligence_service import RepositoryIntelligenceError
from app.services.scm import ScmAPIError, ScmProvider
from app.services.jwt_service import create_access_token


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _utcnow():
    return datetime.datetime.now(datetime.timezone.utc)


def _profile(**overrides):
    payload = {
        "owner": "acme",
        "repository": "webapp",
        "name": "webapp",
        "full_name": "acme/webapp",
        "private": False,
        "description": "Customer-facing web application",
        "html_url": "https://github.com/acme/webapp",
        "default_branch": "main",
        "primary_language": "TypeScript",
        "stars": 240,
        "forks": 18,
        "watchers": 12,
        "open_issues": 7,
        "size_kb": 4096,
        "license_key": "mit",
        "license_name": "MIT License",
        "topics": ["react", "typescript"],
        "created_at": "2023-01-05T00:00:00Z",
        "updated_at": "2026-02-01T00:00:00Z",
        "pushed_at": "2026-02-20T00:00:00Z",
        "archived": False,
        "is_fork": False,
    }
    payload.update(overrides)
    return payload


README_SAMPLE = """# Webapp

[![build](https://img.shields.io/badge/build-passing-green)](https://example.com/ci)
[![license](https://img.shields.io/badge/license-MIT-blue)](https://example.com/license)

Webapp is the customer-facing application.

## Table of Contents

- [Install](#install)
- [Usage](#usage)

## Install

```bash
npm ci
```

Then run it.

## Usage

Open http://localhost:3000 and sign in.

```ts
const client = createClient();
```

## License

MIT
"""


@pytest.fixture(autouse=True)
def _isolate_cache(monkeypatch):
    """Point the analysis cache at a fresh in-memory fake for every test."""

    class _EmptyCollection:
        async def find_one(self, query=None, *args, **kwargs):
            return None

        async def update_one(self, *args, **kwargs):
            return None

        # Motor's find() is synchronous and returns a cursor; the fake mirrors
        # that so the repository code under test is exercised as written.
        def find(self, *args, **kwargs):
            return _EmptyCursor()

        async def delete_many(self, *args, **kwargs):
            class _Result:
                deleted_count = 0

            return _Result()

    class _EmptyCursor:
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise StopAsyncIteration

    class _EmptyDb:
        def __getitem__(self, name):
            return _EmptyCollection()

    monkeypatch.setattr(
        repository_analysis_repository, "get_db", lambda: _EmptyDb()
    )
    monkeypatch.setattr(
        repository_intelligence_service, "get_scm_client", lambda *a, **k: None
    )


# ---------------------------------------------------------------------------
# Health scoring
# ---------------------------------------------------------------------------


class TestHealthScoring:
    def test_perfect_repository_scores_100(self):
        health = repository_health_service.compute_health(
            _profile(),
            has_readme=True,
            now=_utcnow(),
            owner="acme",
            repository="webapp",
        )
        # Maintenance decays with elapsed time, so pin the clock to the push.
        assert health.components[0].score == 100.0
        assert health.components[1].score == 100.0
        assert health.unavailable_signals == []
        assert health.measured_weight == pytest.approx(1.0)

    def test_fresh_push_scores_full_maintenance(self):
        now = _utcnow()
        health = repository_health_service.compute_health(
            _profile(pushed_at=now.isoformat().replace("+00:00", "Z")),
            has_readme=True,
            now=now,
        )
        maintenance = next(c for c in health.components if c.key == "maintenance")
        assert maintenance.score == 100.0
        assert "today" in maintenance.detail

    def test_stale_push_decays_maintenance(self):
        now = _utcnow()
        stale = (now - datetime.timedelta(days=400)).isoformat().replace("+00:00", "Z")
        health = repository_health_service.compute_health(
            _profile(pushed_at=stale), has_readme=True, now=now
        )
        maintenance = next(c for c in health.components if c.key == "maintenance")
        assert 0.0 < maintenance.score < 100.0
        assert "400 days ago" in maintenance.detail

    def test_very_stale_push_scores_zero(self):
        now = _utcnow()
        ancient = (now - datetime.timedelta(days=1200)).isoformat().replace("+00:00", "Z")
        health = repository_health_service.compute_health(
            _profile(pushed_at=ancient), has_readme=True, now=now
        )
        maintenance = next(c for c in health.components if c.key == "maintenance")
        assert maintenance.score == 0.0

    def test_missing_push_timestamp_is_unavailable_not_zero(self):
        health = repository_health_service.compute_health(
            _profile(pushed_at=None), has_readme=True, now=_utcnow()
        )
        maintenance = next(c for c in health.components if c.key == "maintenance")
        assert maintenance.score is None
        assert "maintenance" in health.unavailable_signals
        # Remaining weights are renormalized, so the average is still meaningful.
        assert health.measured_weight == pytest.approx(0.75)

    def test_missing_readme_is_unavailable_not_zero(self):
        health = repository_health_service.compute_health(
            _profile(), has_readme=None, now=_utcnow()
        )
        documentation = next(c for c in health.components if c.key == "documentation")
        assert documentation.score is None
        assert "documentation" in health.unavailable_signals

    def test_absent_readme_scores_zero_not_unavailable(self):
        health = repository_health_service.compute_health(
            _profile(), has_readme=False, now=_utcnow()
        )
        documentation = next(c for c in health.components if c.key == "documentation")
        assert documentation.score == 0.0
        assert "documentation" not in health.unavailable_signals

    def test_no_license_scores_zero(self):
        health = repository_health_service.compute_health(
            _profile(license_name=None, license_key=None), has_readme=True, now=_utcnow()
        )
        licensing = next(c for c in health.components if c.key == "licensing")
        assert licensing.score == 0.0

    def test_community_score_is_bounded_and_monotonic(self):
        small = repository_health_service.compute_health(
            _profile(stars=1, forks=0), has_readme=True, now=_utcnow()
        )
        large = repository_health_service.compute_health(
            _profile(stars=100_000, forks=50_000), has_readme=True, now=_utcnow()
        )
        small_community = next(c for c in small.components if c.key == "community")
        large_community = next(c for c in large.components if c.key == "community")
        assert 0.0 <= small_community.score < large_community.score <= 100.0

    def test_hygiene_flags_issue_overload(self):
        health = repository_health_service.compute_health(
            _profile(stars=0, forks=0, open_issues=900),
            has_readme=True,
            now=_utcnow(),
        )
        hygiene = next(c for c in health.components if c.key == "hygiene")
        assert hygiene.score == 0.0
        assert "overloaded" in hygiene.detail

    def test_no_profile_marks_every_signal_unavailable(self):
        health = repository_health_service.compute_health(
            None, owner="acme", repository="webapp"
        )
        assert health.score == 0.0
        assert set(health.unavailable_signals) == {
            "documentation",
            "licensing",
            "maintenance",
            "community",
            "hygiene",
        }
        assert health.measured_weight == 0.0

    @pytest.mark.parametrize(
        "score,grade",
        [(100, "A"), (90, "A"), (85, "B"), (75, "C"), (65, "D"), (10, "F")],
    )
    def test_grade_bands(self, score, grade):
        assert repository_health_service.grade_for(score) == grade

    def test_score_is_clamped_to_range(self):
        health = repository_health_service.compute_health(
            _profile(), has_readme=True, now=_utcnow()
        )
        assert 0.0 <= health.score <= 100.0

    def test_invalid_timestamp_is_treated_as_unavailable(self):
        health = repository_health_service.compute_health(
            _profile(pushed_at="not-a-date"), has_readme=True, now=_utcnow()
        )
        maintenance = next(c for c in health.components if c.key == "maintenance")
        assert maintenance.score is None


# ---------------------------------------------------------------------------
# Language breakdown
# ---------------------------------------------------------------------------


class TestLanguageBreakdown:
    def test_percentages_sum_to_one_hundred(self):
        breakdown = repository_language_service.build_language_breakdown(
            {"TypeScript": 6000, "Python": 3000, "CSS": 1000}
        )
        assert breakdown.total_bytes == 10_000
        assert sum(item.percent for item in breakdown.languages) == pytest.approx(100.0)

    def test_sorted_by_bytes_descending(self):
        breakdown = repository_language_service.build_language_breakdown(
            {"Python": 10, "TypeScript": 90, "CSS": 50}
        )
        assert [item.name for item in breakdown.languages] == [
            "TypeScript",
            "CSS",
            "Python",
        ]

    def test_ties_break_alphabetically(self):
        breakdown = repository_language_service.build_language_breakdown(
            {"Rust": 5, "Go": 5, "Zig": 5}
        )
        assert [item.name for item in breakdown.languages] == ["Go", "Rust", "Zig"]

    def test_extra_languages_fold_into_other(self):
        breakdown = repository_language_service.build_language_breakdown(
            {f"Lang{i}": 10 for i in range(12)}, top_n=5
        )
        names = [item.name for item in breakdown.languages]
        assert len(names) == 6
        assert names[-1] == "Other"
        assert breakdown.other_bytes == 70
        assert breakdown.truncated is True

    def test_no_languages_yields_empty_breakdown(self):
        breakdown = repository_language_service.build_language_breakdown({})
        assert breakdown.languages == []
        assert breakdown.total_bytes == 0
        assert breakdown.truncated is False

    def test_none_languages_yields_empty_breakdown(self):
        breakdown = repository_language_service.build_language_breakdown(None)
        assert breakdown.total_bytes == 0

    def test_zero_and_negative_counts_are_discarded(self):
        breakdown = repository_language_service.build_language_breakdown(
            {"Python": 100, "Ghost": 0, "Negative": -5}
        )
        assert [item.name for item in breakdown.languages] == ["Python"]


# ---------------------------------------------------------------------------
# Dependency inspection
# ---------------------------------------------------------------------------


PACKAGE_JSON = """{
  "name": "webapp",
  "dependencies": {
    "react": "18.2.0",
    "axios": "^1.7.7",
    "left-pad": "1.3.0",
    "wildcard": "*"
  },
  "devDependencies": {
    "typescript": "5.6.3",
    "vitest": "latest"
  }
}"""

REQUIREMENTS_TXT = """# runtime deps
fastapi==0.115.5
uvicorn[standard]==0.30.6
httpx>=0.27.2
-r dev-requirements.txt
pycrypto==2.6.1
requests @ https://github.com/psf/requests/archive/refs/heads/main.zip
"""

PYPROJECT_TOML = """[project]
name = "webapp"
dependencies = [
    "pydantic==2.9.2",
    "motor>=3.6.0",
    "requests",
]

[project.optional-dependencies]
dev = ["pytest==8.0.0"]

[tool.poetry.dependencies]
python = "^3.11"
httpx = "^0.27.2"
"""

GO_MOD = """module github.com/acme/webapp

go 1.22

require (
\tgithub.com/spf13/cobra v1.8.0
\tgithub.com/stretchr/testify v1.9.0 // indirect
)

require golang.org/x/sys v0.20.0

replace github.com/old/pkg => github.com/new/pkg v1.0.0
"""


class TestDependencyInspection:
    def test_package_json_runtime_and_dev_split(self):
        deps = repository_dependency_service.parse_package_json(PACKAGE_JSON)
        by_name = {dep.name: dep for dep in deps}
        assert by_name["react"].scope == "runtime"
        assert by_name["react"].pinned is True
        assert by_name["typescript"].scope == "development"
        assert len(deps) == 6

    def test_caret_range_is_floating(self):
        deps = {d.name: d for d in repository_dependency_service.parse_package_json(PACKAGE_JSON)}
        assert "floating_version" in deps["axios"].risks
        assert deps["axios"].pinned is False

    def test_wildcard_is_unpinned(self):
        deps = {d.name: d for d in repository_dependency_service.parse_package_json(PACKAGE_JSON)}
        assert "unpinned" in deps["wildcard"].risks
        assert deps["wildcard"].pinned is False

    def test_latest_tag_is_floating(self):
        deps = {d.name: d for d in repository_dependency_service.parse_package_json(PACKAGE_JSON)}
        assert "floating_version" in deps["vitest"].risks

    def test_deprecated_npm_package_is_flagged(self):
        deps = {d.name: d for d in repository_dependency_service.parse_package_json(PACKAGE_JSON)}
        assert "deprecated_package" in deps["left-pad"].risks

    def test_malformed_package_json_yields_no_dependencies(self):
        assert repository_dependency_service.parse_package_json("{not json") == []

    def test_package_json_wrong_type_yields_no_dependencies(self):
        assert repository_dependency_service.parse_package_json("[1, 2, 3]") == []

    def test_requirements_txt_parsing(self):
        deps = repository_dependency_service.parse_requirements_txt(REQUIREMENTS_TXT)
        by_name = {dep.name: dep for dep in deps}
        assert by_name["fastapi"].version == "==0.115.5"
        assert by_name["fastapi"].pinned is True
        assert by_name["httpx"].version == ">=0.27.2"
        assert "floating_version" in by_name["httpx"].risks
        # The -r include is not itself a dependency.
        assert "dev-requirements.txt" not in by_name
        assert "deprecated_package" in by_name["pycrypto"].risks

    def test_extras_are_stripped_from_name(self):
        deps = {d.name: d for d in repository_dependency_service.parse_requirements_txt(REQUIREMENTS_TXT)}
        assert "uvicorn" in deps
        assert "uvicorn[standard]" not in deps

    def test_pep508_direct_reference_is_a_git_source(self):
        deps = {d.name: d for d in repository_dependency_service.parse_requirements_txt(REQUIREMENTS_TXT)}
        assert "git_source" in deps["requests"].risks

    def test_editable_local_install_is_a_local_path(self):
        dep = repository_dependency_service.parse_requirement_line(
            "-e .", "requirements.txt"
        )
        assert dep is not None
        assert "local_path" in dep.risks

    def test_requirement_line_skips_noise(self):
        assert repository_dependency_service.parse_requirement_line("", "r.txt") is None
        assert repository_dependency_service.parse_requirement_line("   # c", "r.txt") is None
        assert repository_dependency_service.parse_requirement_line("--index-url x", "r.txt") is None

    def test_environment_marker_is_ignored(self):
        dep = repository_dependency_service.parse_requirement_line(
            'importlib-metadata==6.0; python_version < "3.9"', "r.txt"
        )
        assert dep is not None
        assert dep.version == "==6.0"

    def test_pyproject_pep621_and_poetry(self):
        deps = repository_dependency_service.parse_pyproject(PYPROJECT_TOML)
        by_name = {dep.name: dep for dep in deps}
        assert by_name["pydantic"].version == "==2.9.2"
        assert by_name["httpx"].version == "^0.27.2"
        assert "floating_version" in by_name["httpx"].risks
        # python itself is not a dependency.
        assert "python" not in by_name

    def test_pyproject_extras_get_their_own_scope(self):
        deps = repository_dependency_service.parse_pyproject(PYPROJECT_TOML)
        pytest_dep = next(dep for dep in deps if dep.name == "pytest")
        assert pytest_dep.scope == "extra:dev"

    def test_pyproject_bare_requirement_is_missing_version(self):
        deps = {d.name: d for d in repository_dependency_service.parse_pyproject(PYPROJECT_TOML)}
        assert "missing_version" in deps["requests"].risks
        assert deps["requests"].pinned is False

    def test_malformed_pyproject_yields_no_dependencies(self):
        assert repository_dependency_service.parse_pyproject("[[[") == []

    def test_go_mod_block_and_single_line(self):
        deps = {d.name: d for d in repository_dependency_service.parse_go_mod(GO_MOD)}
        assert deps["github.com/spf13/cobra"].version == "v1.8.0"
        assert deps["golang.org/x/sys"].version == "v0.20.0"
        assert len(deps) == 3

    def test_go_mod_indirect_scope(self):
        deps = {d.name: d for d in repository_dependency_service.parse_go_mod(GO_MOD)}
        testify = deps["github.com/stretchr/testify"]
        assert testify.scope == "indirect"

    def test_go_mod_replace_directive_is_ignored(self):
        names = {d.name for d in repository_dependency_service.parse_go_mod(GO_MOD)}
        assert "github.com/old/pkg" not in names
        assert "github.com/new/pkg" not in names

    def test_report_lists_found_and_missing_manifests(self):
        report = repository_dependency_service.build_dependency_report(
            {"package.json": PACKAGE_JSON}
        )
        found = {m.path: m.found for m in report.manifests}
        assert found["package.json"] is True
        assert found["go.mod"] is False
        assert report.total == 6
        assert report.flagged_count > 0
        assert report.ecosystems == ["npm"]

    def test_found_but_empty_manifest_is_distinguished_from_missing(self):
        report = repository_dependency_service.build_dependency_report(
            {"requirements.txt": "# nothing here\n"}
        )
        manifest = next(m for m in report.manifests if m.path == "requirements.txt")
        assert manifest.found is True
        assert "no dependencies" in (manifest.reason or "")
        assert report.total == 0

    def test_empty_report_lists_every_manifest_as_missing(self):
        report = repository_dependency_service.build_dependency_report(None)
        assert all(m.found is False for m in report.manifests)
        assert report.total == 0

    def test_report_is_sorted_deterministically(self):
        report = repository_dependency_service.build_dependency_report(
            {
                "package.json": PACKAGE_JSON,
                "requirements.txt": REQUIREMENTS_TXT,
                "go.mod": GO_MOD,
            }
        )
        keys = [(d.ecosystem, d.manifest, d.name) for d in report.dependencies]
        assert keys == sorted(keys)

    def test_summarize_risks_counts_each_label(self):
        report = repository_dependency_service.build_dependency_report(
            {"package.json": PACKAGE_JSON}
        )
        counts = repository_dependency_service.summarize_risks(report)
        assert counts["floating_version"] >= 2
        assert counts["unpinned"] == 1
        assert counts["deprecated_package"] == 1


# ---------------------------------------------------------------------------
# README intelligence
# ---------------------------------------------------------------------------


class TestReadmeIntelligence:
    def test_full_readme_analysis(self):
        report = repository_readme_service.build_readme_intelligence(README_SAMPLE)
        assert report.available is True
        assert report.has_toc is True
        assert report.has_install_section is True
        assert report.has_usage_section is True
        assert report.has_license_section is True
        assert report.code_blocks == 2
        assert report.badge_count == 2
        assert report.has_badges is True
        assert report.languages_used == ["bash", "ts"]

    def test_section_headings_and_levels(self):
        report = repository_readme_service.build_readme_intelligence(README_SAMPLE)
        headings = [(s.heading, s.level) for s in report.sections]
        assert ("Webapp", 1) in headings
        assert ("Install", 2) in headings
        assert ("License", 2) in headings

    def test_section_preview_excludes_the_next_heading(self):
        report = repository_readme_service.build_readme_intelligence(README_SAMPLE)
        install = next(s for s in report.sections if s.heading == "Install")
        assert "npm ci" in install.preview
        assert "Usage" not in install.preview

    def test_missing_readme_is_reported_not_fabricated(self):
        report = repository_readme_service.build_readme_intelligence(
            None, owner="acme", repository="webapp"
        )
        assert report.available is False
        assert report.reason
        assert report.sections == []
        assert report.word_count == 0
        assert report.raw is None

    def test_blank_readme_treated_as_missing(self):
        report = repository_readme_service.build_readme_intelligence("   \n  ")
        assert report.available is False

    def test_word_count_excludes_code_block_bodies(self):
        with_code = "# T\n\nhello world\n\n```\naaa bbb ccc ddd\n```\n"
        report = repository_readme_service.build_readme_intelligence(with_code)
        # "T" + "hello world" only; the fenced body is not prose.
        assert report.word_count == 3

    def test_setext_heading_is_detected(self):
        report = repository_readme_service.build_readme_intelligence(
            "Title\n=====\n\nbody\n"
        )
        assert any(s.heading == "Title" and s.level == 1 for s in report.sections)

    def test_no_sections_reports_all_section_flags_false(self):
        report = repository_readme_service.build_readme_intelligence("just prose here")
        assert report.sections == []
        assert report.has_install_section is False
        assert report.has_usage_section is False
        assert report.has_toc is False

    def test_unterminated_fence_still_counts(self):
        report = repository_readme_service.build_readme_intelligence(
            "# T\n\n```py\nx = 1\ny = 2\n"
        )
        assert report.code_blocks == 1

    def test_images_and_links_counted(self):
        report = repository_readme_service.build_readme_intelligence(
            "# T\n\n![logo](a.png)\n\n[docs](https://example.com)\n"
        )
        assert report.images >= 1
        assert report.links == 1

    def test_html_badge_is_detected(self):
        report = repository_readme_service.build_readme_intelligence(
            '<img src="https://img.shields.io/badge/x-y-blue" />'
        )
        assert report.has_badges is True
        assert report.badge_count == 1

    def test_non_badge_image_is_not_a_badge(self):
        report = repository_readme_service.build_readme_intelligence(
            '<img src="logo.png" />'
        )
        assert report.has_badges is False


# ---------------------------------------------------------------------------
# Explorer
# ---------------------------------------------------------------------------


TREE_PAYLOAD = {
    "truncated": False,
    "tree": [
        {"path": "src", "type": "tree", "sha": "a"},
        {"path": "src/index.ts", "type": "blob", "sha": "b", "size": 120},
        {"path": "README.md", "type": "blob", "sha": "c", "size": 340},
        {"path": "src/components", "type": "tree", "sha": "d"},
        {"path": "src/components/App.tsx", "type": "blob", "sha": "e", "size": 900},
        {"path": "docs", "type": "tree", "sha": "f"},
    ],
}


class TestExplorer:
    def test_tree_is_directory_first(self):
        tree = repository_explorer_service.build_tree(TREE_PAYLOAD)
        # Hierarchical order: every entry follows its parent, directories before
        # files at each level, so the flat list renders as a correct outline.
        assert [entry.path for entry in tree.entries] == [
            "docs",
            "src",
            "src/components",
            "src/components/App.tsx",
            "src/index.ts",
            "README.md",
        ]

    def test_tree_depth_is_computed_from_path(self):
        tree = repository_explorer_service.build_tree(TREE_PAYLOAD)
        depths = {entry.path: entry.depth for entry in tree.entries}
        assert depths["src"] == 0
        assert depths["src/index.ts"] == 1
        assert depths["src/components/App.tsx"] == 2

    def test_tree_totals(self):
        tree = repository_explorer_service.build_tree(TREE_PAYLOAD)
        assert tree.total_files == 3
        assert tree.total_directories == 3
        assert tree.total_bytes == 1360
        assert tree.truncated is False

    def test_duplicate_paths_are_deduplicated(self):
        payload = {
            "truncated": False,
            "tree": [
                {"path": "a.py", "type": "blob", "size": 1},
                {"path": "a.py", "type": "blob", "size": 1},
            ],
        }
        tree = repository_explorer_service.build_tree(payload)
        assert tree.total_files == 1

    def test_malformed_entries_are_skipped(self):
        payload = {
            "truncated": False,
            "tree": [
                {"path": "ok.py", "type": "blob", "size": 1},
                {"type": "blob"},
                {"path": "weird", "type": "symlink"},
                "not-a-dict",
            ],
        }
        tree = repository_explorer_service.build_tree(payload)
        assert [entry.path for entry in tree.entries] == ["ok.py"]

    def test_provider_truncation_is_surfaced(self):
        tree = repository_explorer_service.build_tree(
            {"truncated": True, "tree": [{"path": "a.py", "type": "blob"}]}
        )
        assert tree.truncated is True

    def test_entry_cap_marks_truncated(self):
        payload = {
            "truncated": False,
            "tree": [{"path": f"f{i}.py", "type": "blob", "size": 1} for i in range(20)],
        }
        tree = repository_explorer_service.build_tree(payload, max_entries=5)
        assert len(tree.entries) == 5
        assert tree.truncated is True

    def test_empty_tree_payload(self):
        tree = repository_explorer_service.build_tree(None)
        assert tree.entries == []
        assert tree.total_files == 0
        assert tree.truncated is False

    @pytest.mark.parametrize(
        "path,language",
        [
            ("src/index.ts", "typescript"),
            ("app.py", "python"),
            ("main.go", "go"),
            ("style.css", "css"),
            ("Dockerfile", "dockerfile"),
            ("notes.unknownext", None),
            ("LICENSE", None),
        ],
    )
    def test_language_detection(self, path, language):
        assert repository_explorer_service.language_for_path(path) == language

    def test_file_content_is_returned_verbatim(self):
        content = repository_explorer_service.build_file_content("print('hi')", "a.py")
        assert content.content == "print('hi')"
        assert content.binary is False
        assert content.truncated is False
        assert content.language == "python"

    def test_binary_file_is_flagged_and_content_withheld(self):
        content = repository_explorer_service.build_file_content(
            b"\x89PNG\x00\x01\x02", "logo.png"
        )
        assert content.binary is True
        assert content.content == ""
        assert content.size == 7

    def test_oversized_text_is_truncated(self):
        content = repository_explorer_service.build_file_content(
            "x" * 100, "big.txt", max_bytes=10
        )
        assert content.truncated is True
        assert len(content.content) == 10

    def test_none_content_yields_empty_file(self):
        content = repository_explorer_service.build_file_content(None, "gone.py")
        assert content.content == ""
        assert content.binary is False

    def test_file_extension(self):
        assert repository_explorer_service.file_extension("a/b/c.PY") == ".py"
        assert repository_explorer_service.file_extension("LICENSE") == ""


# ---------------------------------------------------------------------------
# Cache repository
# ---------------------------------------------------------------------------


class TestAnalysisCache:
    pytestmark = pytest.mark.asyncio

    async def test_set_then_get_round_trip(self, repository_analysis_db):
        await repository_analysis_repository.set_cached(
            42, "acme", "webapp", "health", {"score": 88.0}
        )
        doc = await repository_analysis_repository.get_cached(42, "acme", "webapp", "health")
        assert doc is not None
        assert doc["payload"] == {"score": 88.0}

    async def test_get_miss_returns_none(self, repository_analysis_db):
        assert await repository_analysis_repository.get_cached(42, "a", "b", "health") is None

    async def test_entries_are_scoped_per_user(self, repository_analysis_db):
        await repository_analysis_repository.set_cached(1, "a", "b", "health", {"x": 1})
        await repository_analysis_repository.set_cached(2, "a", "b", "health", {"x": 2})
        one = await repository_analysis_repository.get_cached(1, "a", "b", "health")
        two = await repository_analysis_repository.get_cached(2, "a", "b", "health")
        assert one["payload"] == {"x": 1}
        assert two["payload"] == {"x": 2}

    async def test_entries_are_scoped_per_analysis(self, repository_analysis_db):
        await repository_analysis_repository.set_cached(1, "a", "b", "health", {"x": 1})
        assert await repository_analysis_repository.get_cached(1, "a", "b", "tree") is None

    async def test_second_set_upserts_instead_of_duplicating(self, repository_analysis_db):
        await repository_analysis_repository.set_cached(1, "a", "b", "health", {"x": 1})
        await repository_analysis_repository.set_cached(1, "a", "b", "health", {"x": 2})
        doc = await repository_analysis_repository.get_cached(1, "a", "b", "health")
        assert doc["payload"] == {"x": 2}
        assert len(repository_analysis_db["repository_analysis"].docs) == 1

    async def test_expired_entry_is_not_returned(self, repository_analysis_db):
        await repository_analysis_repository.set_cached(
            1, "a", "b", "health", {"x": 1}, ttl_seconds=-10
        )
        assert await repository_analysis_repository.get_cached(1, "a", "b", "health") is None

    async def test_expiry_is_recorded(self, repository_analysis_db):
        doc = await repository_analysis_repository.set_cached(
            1, "a", "b", "health", {"x": 1}, ttl_seconds=60
        )
        assert doc["expires_at"] > doc["created_at"]
        assert doc["ttl_seconds"] == 60

    async def test_invalidate_removes_all_analyses_for_a_repo(self, repository_analysis_db):
        await repository_analysis_repository.set_cached(1, "a", "b", "health", {"x": 1})
        await repository_analysis_repository.set_cached(1, "a", "b", "tree", {"y": 1})
        await repository_analysis_repository.set_cached(1, "a", "other", "health", {"x": 9})

        await repository_analysis_repository.invalidate(1, "a", "b")

        assert await repository_analysis_repository.get_cached(1, "a", "b", "health") is None
        assert await repository_analysis_repository.get_cached(1, "a", "b", "tree") is None
        assert await repository_analysis_repository.get_cached(1, "a", "other", "health") is not None

    async def test_list_cached_repositories_dedupes(self, repository_analysis_db):
        await repository_analysis_repository.set_cached(1, "acme", "webapp", "health", {})
        await repository_analysis_repository.set_cached(1, "acme", "webapp", "tree", {})
        listed = await repository_analysis_repository.list_cached_repositories(1)
        assert [item["full_name"] for item in listed] == ["acme/webapp"]

    async def test_expired_entries_are_absent_from_listing(self, repository_analysis_db):
        await repository_analysis_repository.set_cached(
            1, "acme", "old", "health", {}, ttl_seconds=-1
        )
        assert await repository_analysis_repository.list_cached_repositories(1) == []

    async def test_ttl_defaults_are_defined_for_every_analysis(self):
        for analysis in repository_analysis_repository.ANALYSIS_KINDS:
            assert repository_analysis_repository.ttl_for(analysis) > 0


# ---------------------------------------------------------------------------
# Service orchestration
# ---------------------------------------------------------------------------


class FakeIntelligenceClient:
    """Minimal SCM client used to exercise the orchestration layer."""

    def __init__(self, profile=None, languages=None, readme=None, files=None, tree=None):
        self._profile = profile
        self._languages = languages
        self._readme = readme
        self._files = files or {}
        self._tree = tree or {"truncated": False, "tree": []}
        self.calls: list[str] = []

    async def get_repository_profile(self, owner, repo):
        self.calls.append("profile")
        if self._profile is None:
            raise ScmAPIError(status_code=404, message="Not Found", category="not_found")
        return self._profile

    async def get_repository_languages(self, owner, repo):
        self.calls.append("languages")
        return self._languages or {}

    async def get_readme(self, owner, repo, ref=None):
        self.calls.append("readme")
        if self._readme is None:
            raise ScmAPIError(status_code=404, message="Not Found", category="not_found")
        return self._readme

    async def get_file_content(self, owner, repo, path, ref=None):
        self.calls.append(f"file:{path}")
        if path not in self._files:
            raise ScmAPIError(status_code=404, message="Not Found", category="not_found")
        return self._files[path]

    async def get_repository_tree(self, owner, repo, ref=None):
        self.calls.append("tree")
        return self._tree


def _install_client(monkeypatch, client):
    monkeypatch.setattr(
        repository_intelligence_service, "get_scm_client", lambda *a, **k: client
    )


class TestOrchestration:
    pytestmark = pytest.mark.asyncio

    async def test_profile_returns_model(self, monkeypatch):
        _install_client(monkeypatch, FakeIntelligenceClient(profile=_profile()))
        result = await repository_intelligence_service.get_profile(
            42, "token", ScmProvider.github, "acme", "webapp"
        )
        assert result.full_name == "acme/webapp"
        assert result.stars == 240

    async def test_missing_profile_raises(self, monkeypatch):
        _install_client(monkeypatch, FakeIntelligenceClient(profile=None))
        with pytest.raises(RepositoryIntelligenceError):
            await repository_intelligence_service.get_profile(
                42, "token", ScmProvider.github, "acme", "webapp"
            )

    async def test_readme_absence_is_data_not_failure(self, monkeypatch):
        _install_client(monkeypatch, FakeIntelligenceClient(readme=None))
        result = await repository_intelligence_service.get_readme(
            42, "token", ScmProvider.github, "acme", "webapp"
        )
        assert result.available is False
        assert result.reason

    async def test_health_uses_readme_presence(self, monkeypatch):
        _install_client(
            monkeypatch,
            FakeIntelligenceClient(profile=_profile(), readme=README_SAMPLE),
        )
        result = await repository_intelligence_service.get_health(
            42, "token", ScmProvider.github, "acme", "webapp"
        )
        documentation = next(c for c in result.components if c.key == "documentation")
        assert documentation.score == 100.0

    async def test_health_degrades_when_profile_unavailable(self, monkeypatch):
        _install_client(monkeypatch, FakeIntelligenceClient(profile=None, readme="# hi"))
        result = await repository_intelligence_service.get_health(
            42, "token", ScmProvider.github, "acme", "webapp"
        )
        assert result.score == 0.0
        assert set(result.unavailable_signals) >= {"licensing", "maintenance"}

    async def test_languages_are_fetched(self, monkeypatch):
        _install_client(
            monkeypatch, FakeIntelligenceClient(languages={"Python": 10, "Go": 30})
        )
        result = await repository_intelligence_service.get_languages(
            42, "token", ScmProvider.github, "acme", "webapp"
        )
        assert result.total_bytes == 40
        assert result.languages[0].name == "Go"

    async def test_dependencies_probe_every_candidate_manifest(self, monkeypatch):
        client = FakeIntelligenceClient(files={"package.json": PACKAGE_JSON})
        _install_client(monkeypatch, client)
        result = await repository_intelligence_service.get_dependencies(
            42, "token", ScmProvider.github, "acme", "webapp"
        )
        assert result.total == 6
        assert {c for c in client.calls if c.startswith("file:")} == {
            "file:package.json",
            "file:requirements.txt",
            "file:pyproject.toml",
            "file:go.mod",
        }

    async def test_file_read_uses_language_hint(self, monkeypatch):
        _install_client(
            monkeypatch, FakeIntelligenceClient(files={"a.py": "print(1)"})
        )
        result = await repository_intelligence_service.get_file(
            42, "token", ScmProvider.github, "acme", "webapp", "a.py"
        )
        assert result.language == "python"
        assert result.content == "print(1)"

    async def test_missing_file_raises(self, monkeypatch):
        _install_client(monkeypatch, FakeIntelligenceClient(files={}))
        with pytest.raises(RepositoryIntelligenceError):
            await repository_intelligence_service.get_file(
                42, "token", ScmProvider.github, "acme", "webapp", "gone.py"
            )

    async def test_provider_without_tree_capability_returns_empty_tree(self, monkeypatch):
        class Bare:
            pass

        _install_client(monkeypatch, Bare())
        result = await repository_intelligence_service.get_tree(
            42, "token", ScmProvider.github, "acme", "webapp"
        )
        assert result.entries == []

    async def test_dashboard_composes_all_components(self, monkeypatch):
        _install_client(
            monkeypatch,
            FakeIntelligenceClient(
                profile=_profile(),
                languages={"TypeScript": 80, "CSS": 20},
                readme=README_SAMPLE,
                files={"package.json": PACKAGE_JSON},
            ),
        )
        result = await repository_intelligence_service.get_dashboard(
            42, "token", ScmProvider.github, "acme", "webapp"
        )
        assert result.profile.full_name == "acme/webapp"
        assert result.health.score > 0
        assert result.languages.total_bytes == 100
        assert result.dependencies.total == 6
        assert result.readme.available is True
        assert result.generated_at

    async def test_dashboard_survives_a_failing_component(self, monkeypatch):
        class Partial(FakeIntelligenceClient):
            async def get_repository_languages(self, owner, repo):
                raise ScmAPIError(status_code=500, message="boom", category="server")

        _install_client(monkeypatch, Partial(profile=_profile(), readme=README_SAMPLE))
        result = await repository_intelligence_service.get_dashboard(
            42, "token", ScmProvider.github, "acme", "webapp"
        )
        assert result.languages.total_bytes == 0
        assert result.profile.full_name == "acme/webapp"
        assert result.readme.available is True

    async def test_dashboard_without_profile_still_responds(self, monkeypatch):
        _install_client(monkeypatch, FakeIntelligenceClient(profile=None))
        result = await repository_intelligence_service.get_dashboard(
            42, "token", ScmProvider.github, "acme", "webapp"
        )
        assert result.profile.name == "webapp"
        assert result.health.score == 0.0


# ---------------------------------------------------------------------------
# Router contract
# ---------------------------------------------------------------------------


class RouteIntelligenceClient(FakeIntelligenceClient):
    pass


@pytest.fixture
def intelligence_client(monkeypatch):
    client = RouteIntelligenceClient(
        profile=_profile(),
        languages={"TypeScript": 900, "CSS": 100},
        readme=README_SAMPLE,
        files={"package.json": PACKAGE_JSON, "src/index.ts": "export const a = 1;\n"},
        tree=TREE_PAYLOAD,
    )
    _install_client(monkeypatch, client)
    return client


@pytest.fixture
def intelligence_auth(monkeypatch):
    async def known_user(github_id):
        return {
            "_id": "1" * 24,
            "github_id": 42,
            "login": "octocat",
            "name": "Octo Cat",
            "github_access_token": "gho_secret",
        }

    monkeypatch.setattr("app.services.security.get_user_by_github_id", known_user)
    token = create_access_token({"sub": "42", "login": "octocat"})
    return {"Authorization": f"Bearer {token}"}


class TestRepositoryIntelligenceRoutes:
    def test_requires_authentication(self, client):
        response = client.get("/repository-intelligence/repositories/acme/webapp/dashboard")
        assert response.status_code == 401

    def test_dashboard_endpoint(self, client, intelligence_auth, intelligence_client):
        response = client.get(
            "/repository-intelligence/repositories/acme/webapp/dashboard",
            headers=intelligence_auth,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["owner"] == "acme"
        assert body["repository"] == "webapp"
        assert body["profile"]["full_name"] == "acme/webapp"
        assert body["languages"]["total_bytes"] == 1000
        assert body["dependencies"]["total"] == 6
        assert body["readme"]["available"] is True

    def test_health_endpoint(self, client, intelligence_auth, intelligence_client):
        response = client.get(
            "/repository-intelligence/repositories/acme/webapp/health",
            headers=intelligence_auth,
        )
        assert response.status_code == 200
        body = response.json()
        assert 0 <= body["score"] <= 100
        assert len(body["components"]) == 5
        assert body["method"] == "weighted-average"

    def test_languages_endpoint(self, client, intelligence_auth, intelligence_client):
        response = client.get(
            "/repository-intelligence/repositories/acme/webapp/languages",
            headers=intelligence_auth,
        )
        assert response.status_code == 200
        assert response.json()["languages"][0]["name"] == "TypeScript"

    def test_dependencies_endpoint(self, client, intelligence_auth, intelligence_client):
        response = client.get(
            "/repository-intelligence/repositories/acme/webapp/dependencies",
            headers=intelligence_auth,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 6
        assert body["flagged_count"] > 0

    def test_readme_endpoint(self, client, intelligence_auth, intelligence_client):
        response = client.get(
            "/repository-intelligence/repositories/acme/webapp/readme",
            headers=intelligence_auth,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["available"] is True
        assert body["has_install_section"] is True

    def test_tree_endpoint(self, client, intelligence_auth, intelligence_client):
        response = client.get(
            "/repository-intelligence/repositories/acme/webapp/tree",
            headers=intelligence_auth,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["total_files"] == 3
        assert body["entries"][0]["path"] == "docs"
    def test_file_endpoint(self, client, intelligence_auth, intelligence_client):
        response = client.get(
            "/repository-intelligence/repositories/acme/webapp/file",
            params={"path": "src/index.ts"},
            headers=intelligence_auth,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["language"] == "typescript"
        assert "export const a = 1;" in body["content"]

    def test_file_endpoint_requires_path(self, client, intelligence_auth, intelligence_client):
        response = client.get(
            "/repository-intelligence/repositories/acme/webapp/file",
            headers=intelligence_auth,
        )
        assert response.status_code == 422

    def test_missing_file_returns_404(self, client, intelligence_auth, intelligence_client):
        response = client.get(
            "/repository-intelligence/repositories/acme/webapp/file",
            params={"path": "nope.py"},
            headers=intelligence_auth,
        )
        assert response.status_code == 404

    def test_cache_invalidation_endpoint(self, client, intelligence_auth, intelligence_client):
        response = client.delete(
            "/repository-intelligence/repositories/acme/webapp/cache",
            headers=intelligence_auth,
        )
        assert response.status_code == 200
        assert response.json()["repository"] == "webapp"

    def test_cached_repository_listing_endpoint(self, client, intelligence_auth, intelligence_client):
        response = client.get(
            "/repository-intelligence/repositories",
            headers=intelligence_auth,
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_provider_error_is_mapped(self, client, monkeypatch):
        class Failing(RouteIntelligenceClient):
            async def get_repository_profile(self, owner, repo):
                raise ScmAPIError(status_code=403, message="Forbidden", category="authentication")

        _install_client(monkeypatch, Failing())

        async def known_user(github_id):
            return {
                "_id": "1" * 24,
                "github_id": 42,
                "login": "octocat",
                "github_access_token": "gho_secret",
            }

        monkeypatch.setattr("app.services.security.get_user_by_github_id", known_user)
        token = create_access_token({"sub": "42", "login": "octocat"})

        response = client.get(
            "/repository-intelligence/repositories/acme/webapp/dashboard",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401
