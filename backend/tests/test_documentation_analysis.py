"""Tests for the deterministic documentation analysis.

The analysis is a pure function of its inputs, so these tests build assets and
coverage rows directly and assert the gaps and summary that result. They pin the
score arithmetic and the rule that a gap is only emitted with its evidence.
"""

from __future__ import annotations

from app.schemas.documentation_intelligence import (
    DocumentationAsset,
    DocumentationCoverage,
    DocumentationLink,
)
from app.services import documentation_analysis
from app.services.documentation_analysis import build_analysis


def _asset(path: str, kind: str, **kwargs) -> DocumentationAsset:
    return DocumentationAsset(path=path, kind=kind, **kwargs)  # type: ignore[arg-type]


def _coverage(path: str, public: int, documented: int, undocumented=None) -> DocumentationCoverage:
    return DocumentationCoverage(
        path=path,
        language="python",
        public_symbols=public,
        documented_symbols=documented,
        coverage=round(documented / public, 4) if public else 1.0,
        undocumented=undocumented if undocumented is not None else [],
    )


def _good_repo():
    assets = [
        _asset(
            "README.md",
            "readme",
            has_install=True,
            has_usage=True,
            has_examples=True,
            word_count=300,
            headings=[],
        ),
        _asset("LICENSE", "license"),
        _asset("CHANGELOG.md", "changelog"),
        _asset("CONTRIBUTING.md", "contributing"),
        _asset("SECURITY.md", "security_policy"),
        _asset("docs/guide.md", "guide"),
    ]
    return assets, []


def _kinds(gaps) -> set[str]:
    return {gap.kind for gap in gaps}


# --------------------------------------------------------------------------
# Empty repository
# --------------------------------------------------------------------------

class TestEmptyRepository:
    def test_every_canonical_file_is_reported_missing(self):
        gaps, summary = build_analysis([], [])
        assert _kinds(gaps) == {
            "missing_readme",
            "missing_license",
            "missing_changelog",
            "missing_contributing",
            "missing_security_policy",
        }
        assert set(summary.missing_canonical) == {
            "readme",
            "license",
            "changelog",
            "contributing",
            "security_policy",
        }

    def test_no_docs_directory_is_not_reported_for_an_empty_repository(self):
        # With no documentation at all, "no docs directory" would be noise on top
        # of "no README".
        gaps, _ = build_analysis([], [])
        assert "no_docs_directory" not in _kinds(gaps)

    def test_summary_reflects_the_empty_repository(self):
        _, summary = build_analysis([], [])
        assert summary.total_assets == 0
        assert summary.readme_present is False
        assert summary.gap_count == 5

    def test_the_score_is_the_documented_deductions(self):
        # 100 − 40 (no README) − 10 (no license) − 5 − 3 − 3 = 39.
        _, summary = build_analysis([], [])
        assert summary.coverage_score == 39


# --------------------------------------------------------------------------
# Complete repository
# --------------------------------------------------------------------------

class TestCompleteRepository:
    def test_a_complete_repository_has_no_gaps(self):
        assets, coverage = _good_repo()
        gaps, summary = build_analysis(assets, coverage, source_files=10)
        assert gaps == []
        assert summary.coverage_score == 100

    def test_the_summary_counts_both_kinds_of_file(self):
        assets, coverage = _good_repo()
        _, summary = build_analysis(assets, coverage, source_files=10)
        assert summary.documentation_files == 6
        assert summary.source_files == 10
        assert summary.documentation_ratio == round(6 / 16, 4)

    def test_no_docs_directory_is_reported_when_none_exists(self):
        gaps, _ = build_analysis(
            [_asset("README.md", "readme", has_install=True, has_usage=True, word_count=300)],
            [],
        )
        assert "no_docs_directory" in _kinds(gaps)


# --------------------------------------------------------------------------
# README structure
# --------------------------------------------------------------------------

class TestReadmeSections:
    def test_a_missing_install_section_is_reported_with_the_path(self):
        gaps, _ = build_analysis(
            [_asset("README.md", "readme", has_usage=True, word_count=300)], []
        )
        gap = next(g for g in gaps if g.kind == "missing_install_section")
        assert gap.paths == ["README.md"]
        assert gap.severity == "warning"

    def test_a_missing_usage_section_is_reported(self):
        gaps, _ = build_analysis(
            [_asset("README.md", "readme", has_install=True, word_count=300)], []
        )
        assert "missing_usage_section" in _kinds(gaps)

    def test_a_thin_readme_is_reported_with_its_evidence(self):
        gaps, _ = build_analysis(
            [_asset("README.md", "readme", has_install=True, has_usage=True, word_count=20)],
            [],
        )
        gap = next(g for g in gaps if g.kind == "thin_readme")
        assert "20 words" in gap.evidence


# --------------------------------------------------------------------------
# Canonical files
# --------------------------------------------------------------------------

class TestCanonicalFiles:
    def test_a_missing_license_is_reported_and_named(self):
        assets, coverage = _good_repo()
        assets = [asset for asset in assets if asset.kind != "license"]
        gaps, summary = build_analysis(assets, coverage)
        assert "missing_license" in _kinds(gaps)
        assert summary.missing_canonical == ["license"]

    def test_a_missing_changelog_is_informational(self):
        assets, coverage = _good_repo()
        assets = [asset for asset in assets if asset.kind != "changelog"]
        gaps, _ = build_analysis(assets, coverage)
        gap = next(g for g in gaps if g.kind == "missing_changelog")
        assert gap.severity == "info"


# --------------------------------------------------------------------------
# Links
# --------------------------------------------------------------------------

class TestLinks:
    def test_a_broken_relative_link_is_reported(self):
        asset = _asset(
            "README.md",
            "readme",
            has_install=True,
            has_usage=True,
            word_count=300,
            links=[
                DocumentationLink(text="dead", target="./gone.md", internal=True, resolved=False),
                DocumentationLink(text="ok", target="./there.md", internal=True, resolved=True),
            ],
        )
        gaps, summary = build_analysis([asset], [])
        gap = next(g for g in gaps if g.kind == "broken_relative_link")
        assert "./gone.md" in gap.evidence
        assert summary.broken_links == 1
        assert summary.total_links == 2

    def test_external_links_are_not_counted_as_internal(self):
        asset = _asset(
            "README.md",
            "readme",
            has_install=True,
            has_usage=True,
            word_count=300,
            links=[
                DocumentationLink(text="x", target="https://example.com", internal=False, resolved=None)
            ],
        )
        _, summary = build_analysis([asset], [])
        assert summary.total_links == 0
        assert summary.broken_links == 0


# --------------------------------------------------------------------------
# Docstring coverage
# --------------------------------------------------------------------------

class TestDocstringCoverage:
    def test_low_coverage_is_reported_for_a_file(self):
        row = _coverage("app/a.py", public=4, documented=0, undocumented=["a", "b", "c", "d"])
        gaps, _ = build_analysis([], [row])
        assert "low_docstring_coverage" in _kinds(gaps)

    def test_undocumented_public_api_is_reported_separately(self):
        row = _coverage("app/a.py", public=4, documented=0, undocumented=["a", "b", "c", "d"])
        gaps, _ = build_analysis([], [row])
        assert "undocumented_public_api" in _kinds(gaps)

    def test_a_fully_documented_file_is_not_flagged(self):
        row = _coverage("app/a.py", public=4, documented=4)
        gaps, _ = build_analysis([], [row])
        assert "low_docstring_coverage" not in _kinds(gaps)

    def test_the_aggregate_coverage_is_a_symbol_ratio(self):
        rows = [_coverage("app/a.py", public=2, documented=2), _coverage("app/b.py", public=2, documented=0)]
        _, summary = build_analysis([], rows)
        assert summary.public_symbols == 4
        assert summary.documented_symbols == 2
        assert summary.docstring_coverage == 0.5

    def test_low_coverage_lowers_the_score(self):
        _, high = build_analysis([], [_coverage("app/a.py", public=4, documented=4)])
        _, low = build_analysis([], [_coverage("app/a.py", public=4, documented=0, undocumented=["a", "b", "c", "d"])])
        assert low.coverage_score < high.coverage_score


# --------------------------------------------------------------------------
# Determinism and ordering
# --------------------------------------------------------------------------

class TestDeterminism:
    def test_the_same_inputs_produce_the_same_report(self):
        assets, coverage = _good_repo()
        first_gaps, first_summary = build_analysis(assets, coverage, source_files=5)
        second_gaps, second_summary = build_analysis(assets, coverage, source_files=5)
        assert first_gaps == second_gaps
        assert first_summary == second_summary

    def test_gaps_are_sorted_by_kind(self):
        assets, coverage = _good_repo()
        assets = [asset for asset in assets if asset.kind not in ("license", "changelog")]
        gaps, _ = build_analysis(assets, coverage)
        kinds = [gap.kind for gap in gaps]
        assert kinds == sorted(kinds)

    def test_asset_order_does_not_change_the_summary(self):
        assets, coverage = _good_repo()
        _, forward = build_analysis(assets, coverage, source_files=5)
        _, reversed_ = build_analysis(list(reversed(assets)), coverage, source_files=5)
        assert forward == reversed_


class TestMethodology:
    def test_the_summary_states_that_no_model_is_used(self):
        _, summary = build_analysis([], [])
        assert "No model" in summary.methodology
        assert summary.methodology == documentation_analysis.METHODOLOGY
