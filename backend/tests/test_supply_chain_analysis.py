"""Tests for the deterministic supply-chain analysis.

The analysis layer owns the cross-file facts (which packages are transitive) and
the auditable hygiene score. These tests pin both, because both are the reason a
reader can trust the report.
"""

from __future__ import annotations

import pytest

from app.schemas.supply_chain import (
    CODE_DEPRECATED_PACKAGE,
    CODE_FLOATING_VERSION,
    CODE_MANIFEST_UNREADABLE,
    CODE_MISSING_VERSION,
    CODE_NO_LOCKFILE,
    CODE_NO_MANIFEST,
    CODE_PARSE_EMPTY,
    CODE_PROPRIETARY_LICENSE,
    CODE_STRONG_COPYLEFT,
    CODE_UNDECLARED_LICENSE,
    CODE_UNKNOWN_LICENSE,
    CODE_UNPINNED_DEPENDENCY,
    CODE_UNRESOLVED_TRANSITIVES,
    CODE_VCS_SOURCE,
    LIC_PERMISSIVE,
    LIC_PROPRIETARY,
    LIC_STRONG_COPYLEFT,
    LIC_UNKNOWN,
    ORIGIN_DIRECT,
    ORIGIN_TRANSITIVE,
    ROLE_LOCKFILE,
    ROLE_MANIFEST,
    SupplyChainDependency,
    SupplyChainManifest,
)
from app.services import supply_chain_analysis as analysis

PACKAGE_JSON = """{
  "name": "demo", "license": "MIT",
  "dependencies": {
    "express": "^4.17.21",
    "lodash": {"version": "4.17.21", "license": "MIT"},
    "app-lib": {"version": "2.0.0", "license": "GPL-3.0-only"},
    "quiet": {"version": "0.1.0"},
    "from-git": "git+https://github.com/o/r.git"
  }
}"""

PACKAGE_LOCK = """{"lockfileVersion": 3, "packages": {
  "": {"name": "demo"},
  "node_modules/express": {"version": "4.17.21", "license": "MIT"},
  "node_modules/body-parser": {"version": "1.20.0", "license": "MIT"},
  "node_modules/ms": {"version": "2.1.3", "license": "MIT"}}}"""


def dep(name, **kwargs):
    defaults = {
        "name": name,
        "version": "1.0.0",
        "ecosystem": "npm",
        "manifest": "package.json",
        "origin": ORIGIN_DIRECT,
        "pinned": True,
        "risks": [],
    }
    defaults.update(kwargs)
    return SupplyChainDependency(**defaults)


def manifest(path="package.json", role=ROLE_MANIFEST, found=True, **kwargs):
    defaults = {"path": path, "ecosystem": "npm", "role": role, "found": found}
    defaults.update(kwargs)
    return SupplyChainManifest(**defaults)


def codes(issues):
    return [issue.code for issue in issues]


# --------------------------------------------------------------------------
# Inventory reconciliation
# --------------------------------------------------------------------------


class TestMergeInventory:
    def test_a_package_in_both_files_is_counted_once(self):
        rows = [dep("express", version="^4.17.21", pinned=False),
                dep("express", version="4.17.21", manifest="package-lock.json", origin=ORIGIN_DIRECT)]
        merged = analysis.merge_inventory(
            rows, [manifest(), manifest("package-lock.json", ROLE_LOCKFILE)]
        )
        assert len(merged) == 1

    def test_the_resolved_version_wins_over_the_declared_range(self):
        # The manifest says "^4.17.21"; the lockfile says what actually ships.
        rows = [dep("express", version="^4.17.21", pinned=False),
                dep("express", version="4.17.21", manifest="package-lock.json")]
        merged = analysis.merge_inventory(
            rows, [manifest(), manifest("package-lock.json", ROLE_LOCKFILE)]
        )
        assert merged[0].version == "4.17.21"

    def test_the_declared_scope_survives_the_merge(self):
        # A lockfile does not record devDependencies, so the manifest row is the
        # base and only the version is taken from the lock.
        rows = [dep("jest", scope="development", version="^29.0.0", pinned=False),
                dep("jest", version="29.7.0", manifest="package-lock.json", scope="runtime")]
        merged = analysis.merge_inventory(
            rows, [manifest(), manifest("package-lock.json", ROLE_LOCKFILE)]
        )
        assert merged[0].scope == "development"
        assert merged[0].version == "29.7.0"

    def test_a_package_only_in_the_lockfile_is_transitive(self):
        rows = [dep("express", manifest="package.json"),
                dep("body-parser", manifest="package-lock.json")]
        merged = analysis.merge_inventory(
            rows, [manifest(), manifest("package-lock.json", ROLE_LOCKFILE)]
        )
        by_name = {row.name: row for row in merged}
        assert by_name["express"].origin == ORIGIN_DIRECT
        assert by_name["body-parser"].origin == ORIGIN_TRANSITIVE

    def test_a_licence_from_the_lockfile_fills_a_manifest_gap(self):
        rows = [dep("quiet", manifest="package.json"),
                dep("quiet", manifest="package-lock.json", license_expression="ISC",
                    license_category=LIC_PERMISSIVE)]
        merged = analysis.merge_inventory(
            rows, [manifest(), manifest("package-lock.json", ROLE_LOCKFILE)]
        )
        assert merged[0].license_expression == "ISC"

    def test_manifest_rows_are_not_overwritten_by_later_manifest_rows(self):
        rows = [dep("express", scope="runtime"), dep("express", scope="development")]
        merged = analysis.merge_inventory(rows, [manifest()])
        assert len(merged) == 1
        assert merged[0].scope == "runtime"

    def test_order_is_stable(self):
        rows = [dep("b"), dep("a")]
        merged = analysis.merge_inventory(rows, [manifest()])
        assert [row.name for row in merged] == ["b", "a"]


# --------------------------------------------------------------------------
# Licence rollup
# --------------------------------------------------------------------------


class TestBuildLicenses:
    def test_licences_are_grouped_by_expression(self):
        licenses = analysis.build_licenses(
            [
                dep("a", license_expression="MIT", license_category=LIC_PERMISSIVE),
                dep("b", license_expression="MIT", license_category=LIC_PERMISSIVE),
                dep("c", license_expression="GPL-3.0-only", license_category=LIC_STRONG_COPYLEFT),
            ]
        )
        by_expression = {row.expression: row for row in licenses}
        assert by_expression["MIT"].dependency_count == 2
        assert by_expression["GPL-3.0-only"].category == LIC_STRONG_COPYLEFT

    def test_undeclared_licences_are_collected_under_one_label(self):
        licenses = analysis.build_licenses([dep("a"), dep("b")])
        assert len(licenses) == 1
        assert licenses[0].expression == "Undeclared"
        assert licenses[0].category == LIC_UNKNOWN

    def test_the_most_used_licence_comes_first(self):
        licenses = analysis.build_licenses(
            [
                dep("a", license_expression="MIT", license_category=LIC_PERMISSIVE),
                dep("b", license_expression="ISC", license_category=LIC_PERMISSIVE),
                dep("c", license_expression="MIT", license_category=LIC_PERMISSIVE),
            ]
        )
        assert licenses[0].expression == "MIT"

    def test_direct_and_total_counts_are_both_reported(self):
        licenses = analysis.build_licenses(
            [
                dep("a", license_expression="MIT", license_category=LIC_PERMISSIVE),
                dep("b", license_expression="MIT", license_category=LIC_PERMISSIVE,
                    origin=ORIGIN_TRANSITIVE, manifest="package-lock.json"),
            ]
        )
        assert licenses[0].dependency_count == 2
        assert licenses[0].direct_dependency_count == 1

    def test_an_empty_inventory_yields_no_licences(self):
        assert analysis.build_licenses([]) == []


# --------------------------------------------------------------------------
# Manifest-level issues
# --------------------------------------------------------------------------


class TestManifestIssues:
    def test_a_repository_with_no_manifests_is_reported(self):
        issues = analysis.build_issues([manifest(found=False)], [])
        assert CODE_NO_MANIFEST in codes(issues)

    def test_no_manifest_reports_the_expected_files_not_zero(self):
        issues = analysis.build_issues(
            [manifest("package.json", found=False), manifest("go.mod", found=False)], []
        )
        issue = next(row for row in issues if row.code == CODE_NO_MANIFEST)
        assert issue.affected_count == 2

    def test_a_lockfile_without_a_manifest_is_high(self):
        # The lockfile is present, so the resolved graph is real, but nothing in
        # the repository says which packages were chosen.
        issues = analysis.build_issues(
            [manifest("package-lock.json", ROLE_LOCKFILE, found=True, dependency_count=3)], []
        )
        issue = next(row for row in issues if row.code == CODE_NO_MANIFEST)
        assert issue.severity == "high"
        assert "lockfile is present" in issue.detail

    def test_manifests_without_a_lockfile_are_flagged_as_unreproducible(self):
        issues = analysis.build_issues([manifest()], [dep("express")])
        assert CODE_NO_LOCKFILE in codes(issues)
        issue = next(row for row in issues if row.code == CODE_NO_LOCKFILE)
        assert issue.severity == "high"

    def test_a_manifest_with_a_lockfile_has_no_lockfile_issue(self):
        issues = analysis.build_issues(
            [manifest(), manifest("package-lock.json", ROLE_LOCKFILE)], [dep("express")]
        )
        assert CODE_NO_LOCKFILE not in codes(issues)

    def test_a_parse_failure_is_reported(self):
        issues = analysis.build_issues(
            [manifest(parse_failed=True, note="Could not be parsed.")], []
        )
        assert CODE_MANIFEST_UNREADABLE in codes(issues)

    def test_a_lockfile_that_resolves_more_than_its_manifest_declares_is_reported(self):
        issues = analysis.build_issues(
            [
                manifest(dependency_count=0),
                manifest("package-lock.json", ROLE_LOCKFILE, dependency_count=3,
                         transitive_count=3),
            ],
            [dep("a", manifest="package-lock.json", origin=ORIGIN_TRANSITIVE)],
        )
        assert CODE_PARSE_EMPTY in codes(issues)

    def test_an_unexpanded_lockfile_is_reported_as_such(self):
        # yarn.lock records a graph this report does not enumerate. That is not
        # the same as having no lockfile, so it is a separate, lower-severity fact.
        issues = analysis.build_issues(
            [manifest(), manifest("yarn.lock", ROLE_LOCKFILE, dependency_count=0)], [dep("a")]
        )
        assert CODE_UNRESOLVED_TRANSITIVES in codes(issues)
        assert CODE_NO_LOCKFILE not in codes(issues)


# --------------------------------------------------------------------------
# Risk issues
# --------------------------------------------------------------------------


class TestRiskIssues:
    def test_each_risk_label_becomes_its_own_issue(self):
        issues = analysis.build_issues(
            [manifest()],
            [
                dep("a", risks=["unpinned"]),
                dep("b", risks=["floating_version"]),
                dep("c", risks=["git_source"]),
                dep("d", risks=["missing_version"]),
                dep("e", risks=["deprecated_package"]),
            ],
        )
        found = codes(issues)
        assert CODE_UNPINNED_DEPENDENCY in found
        assert CODE_FLOATING_VERSION in found
        assert CODE_VCS_SOURCE in found
        assert CODE_MISSING_VERSION in found
        assert CODE_DEPRECATED_PACKAGE in found

    def test_several_affected_dependencies_are_aggregated_into_one_issue(self):
        issues = analysis.build_issues(
            [manifest()], [dep("a", risks=["unpinned"]), dep("b", risks=["unpinned"])]
        )
        issue = next(row for row in issues if row.code == CODE_UNPINNED_DEPENDENCY)
        assert issue.affected_count == 2
        assert "2" in issue.title

    def test_a_vcs_source_is_high_severity(self):
        issues = analysis.build_issues([manifest()], [dep("a", risks=["git_source"])])
        issue = next(row for row in issues if row.code == CODE_VCS_SOURCE)
        assert issue.severity == "high"

    def test_evidence_names_the_manifest_and_line(self):
        issues = analysis.build_issues(
            [manifest()], [dep("a", risks=["unpinned"], line=7)]
        )
        issue = next(row for row in issues if row.code == CODE_UNPINNED_DEPENDENCY)
        assert "package.json:7" in issue.evidence[0]

    def test_evidence_is_capped_but_the_count_is_not(self):
        rows = [dep(f"p{index}", risks=["unpinned"]) for index in range(40)]
        issue = next(
            row for row in analysis.build_issues([manifest()], rows)
            if row.code == CODE_UNPINNED_DEPENDENCY
        )
        assert len(issue.evidence) == analysis.MAX_EVIDENCE
        assert issue.affected_count == 40

    def test_a_clean_dependency_set_raises_no_risk_issue(self):
        issues = analysis.build_issues([manifest()], [dep("a")])
        assert not [row for row in issues if row.code in
                    {CODE_UNPINNED_DEPENDENCY, CODE_VCS_SOURCE, CODE_FLOATING_VERSION}]


# --------------------------------------------------------------------------
# Licence issues
# --------------------------------------------------------------------------


class TestLicenseIssues:
    def test_strong_copyleft_is_reported(self):
        issues = analysis.build_issues(
            [manifest()],
            [dep("a", license_expression="GPL-3.0-only", license_category=LIC_STRONG_COPYLEFT)],
        )
        assert CODE_STRONG_COPYLEFT in codes(issues)

    def test_a_direct_strong_copyleft_dependency_is_called_out_separately(self):
        issues = analysis.build_issues(
            [manifest()],
            [dep("a", license_expression="GPL-3.0-only", license_category=LIC_STRONG_COPYLEFT)],
        )
        titles = [row.title for row in issues if row.code == CODE_STRONG_COPYLEFT]
        assert any("directly chosen" in title for title in titles)

    def test_permissive_licences_raise_no_licence_issue(self):
        issues = analysis.build_issues(
            [manifest()],
            [dep("a", license_expression="MIT", license_category=LIC_PERMISSIVE)],
        )
        assert not [
            row for row in issues
            if row.code in {CODE_STRONG_COPYLEFT, CODE_PROPRIETARY_LICENSE,
                            CODE_UNKNOWN_LICENSE, CODE_UNDECLARED_LICENSE}
        ]

    def test_proprietary_licences_are_reported(self):
        issues = analysis.build_issues(
            [manifest()],
            [dep("a", license_expression="UNLICENSED", license_category=LIC_PROPRIETARY)],
        )
        assert CODE_PROPRIETARY_LICENSE in codes(issues)

    def test_undeclared_licences_are_reported_with_a_share(self):
        issues = analysis.build_issues(
            [manifest()], [dep("a", license_expression="MIT", license_category=LIC_PERMISSIVE), dep("b")]
        )
        issue = next(row for row in issues if row.code == CODE_UNDECLARED_LICENSE)
        assert "1 of 2" in issue.detail

    def test_an_unrecognised_licence_is_unknown_not_permissive(self):
        issues = analysis.build_issues(
            [manifest()],
            [dep("a", license_expression="Acme-1.0", license_category=LIC_UNKNOWN)],
        )
        assert CODE_UNKNOWN_LICENSE in codes(issues)

    def test_a_licence_issue_escalates_when_most_packages_are_undeclared(self):
        issues = analysis.build_issues(
            [manifest()], [dep("a"), dep("b"), dep("c")]
        )
        issue = next(row for row in issues if row.code == CODE_UNDECLARED_LICENSE)
        assert issue.severity == "medium"

    def test_an_empty_inventory_raises_no_licence_issue(self):
        assert analysis.build_issues([manifest()], []) == [] or all(
            row.code != CODE_UNDECLARED_LICENSE for row in analysis.build_issues([manifest()], [])
        )


# --------------------------------------------------------------------------
# Ordering
# --------------------------------------------------------------------------


class TestIssueOrdering:
    def test_issues_are_ordered_worst_severity_first(self):
        issues = analysis.build_issues(
            [manifest()],
            [
                dep("a", risks=["floating_version"]),
                dep("b", risks=["git_source"]),
                dep("c", risks=["unpinned"]),
            ],
        )
        severities = [row.severity for row in issues]
        rank = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        assert severities == sorted(severities, key=lambda value: rank[value])

    def test_ordering_is_deterministic(self):
        rows = [dep("a", risks=["unpinned"]), dep("b", risks=["git_source"])]
        first = codes(analysis.build_issues([manifest()], list(rows)))
        second = codes(analysis.build_issues([manifest()], list(rows)))
        assert first == second


# --------------------------------------------------------------------------
# Score
# --------------------------------------------------------------------------


class TestScore:
    def _score(self, manifests, rows, declared=None):
        _, issues, summary = analysis.build_analysis(manifests, rows, declared_license=declared)
        return summary

    def test_a_perfect_project_scores_one_hundred(self):
        manifests = [manifest(), manifest("package-lock.json", ROLE_LOCKFILE, dependency_count=1)]
        rows = [dep("express", license_expression="MIT", license_category=LIC_PERMISSIVE)]
        summary = self._score(manifests, rows)
        assert summary.hygiene_score == 100
        assert summary.score_band == "strong"
        assert summary.score_notes == []

    def test_every_deduction_is_itemised(self):
        summary = self._score([manifest()], [dep("a", risks=["git_source"])])
        assert summary.hygiene_score < 100
        assert any("VCS URL" in note for note in summary.score_notes)

    def test_the_score_never_falls_below_zero(self):
        rows = [dep(f"p{index}", risks=["unpinned", "git_source", "deprecated_package"])
                for index in range(60)]
        summary = self._score([manifest()], rows)
        assert summary.hygiene_score >= 0

    def test_a_missing_lockfile_costs_more_than_a_floating_range(self):
        with_lock = self._score(
            [manifest(), manifest("package-lock.json", ROLE_LOCKFILE)], [dep("a", pinned=False)]
        )
        without_lock = self._score(
            [manifest()],
            [dep("a", pinned=False)],
        )
        assert without_lock.hygiene_score < with_lock.hygiene_score

    def test_no_manifest_at_all_is_penalised(self):
        summary = self._score([manifest(found=False)], [])
        assert summary.hygiene_score < 100
        assert any("manifest" in note for note in summary.score_notes)

    def test_a_strong_copyleft_dependency_lowers_the_score(self):
        rows = [dep("a", license_expression="GPL-3.0-only", license_category=LIC_STRONG_COPYLEFT)]
        summary = self._score([manifest()], rows)
        assert any("copyleft" in note for note in summary.score_notes)

    def test_the_score_is_deterministic(self):
        rows = [dep("a", risks=["unpinned"]), dep("b")]
        assert self._score([manifest()], list(rows)).hygiene_score == (
            self._score([manifest()], list(rows)).hygiene_score
        )

    def test_a_vulnerability_is_not_double_counted(self):
        # Known CVEs belong to the security engine. The hygiene score must not
        # claim to account for them, or the two views would contradict.
        summary = self._score([manifest()], [dep("a")])
        assert not any("vulnerab" in note.lower() for note in summary.score_notes)

    @pytest.mark.parametrize(
        "score,band",
        [(100, "strong"), (95, "strong"), (92, "strong"), (91, "fair"),
         (80, "fair"), (79, "weak"), (60, "weak"), (59, "critical")],
    )
    def test_bands_are_reported(self, score, band):
        assert analysis._band(score) == band


# --------------------------------------------------------------------------
# Summary counts
# --------------------------------------------------------------------------


class TestSummary:
    def test_counts_and_ratios_are_reported(self):
        manifests = [manifest(), manifest("package-lock.json", ROLE_LOCKFILE)]
        rows = [
            dep("a", license_expression="MIT", license_category=LIC_PERMISSIVE),
            dep("b", origin=ORIGIN_TRANSITIVE, manifest="package-lock.json"),
        ]
        _, _, summary = analysis.build_analysis(manifests, rows)
        assert summary.total_dependencies == 2
        assert summary.direct_dependencies == 1
        assert summary.transitive_dependencies == 1
        assert summary.manifest_count == 1
        assert summary.lockfile_count == 1
        assert summary.pinned_ratio == 1.0
        assert summary.license_coverage_ratio == 0.5

    def test_an_empty_inventory_does_not_divide_by_zero(self):
        _, _, summary = analysis.build_analysis([manifest(found=False)], [])
        assert summary.pinned_ratio == 0.0
        assert summary.license_coverage_ratio == 0.0
        assert summary.total_dependencies == 0

    def test_ecosystems_are_listed(self):
        _, _, summary = analysis.build_analysis(
            [manifest()], [dep("a"), dep("b", ecosystem="pypi")]
        )
        assert summary.ecosystems == ["npm", "pypi"]

    def test_licence_categories_are_counted(self):
        _, _, summary = analysis.build_analysis(
            [manifest()],
            [
                dep("a", license_expression="MIT", license_category=LIC_PERMISSIVE),
                dep("b", license_expression="MIT", license_category=LIC_PERMISSIVE),
                dep("c"),
            ],
        )
        assert summary.license_categories == {LIC_PERMISSIVE: 2, LIC_UNKNOWN: 1}

    def test_issues_are_counted_by_severity_and_code(self):
        _, _, summary = analysis.build_analysis(
            [manifest()], [dep("a", risks=["git_source"]), dep("b", risks=["git_source"])]
        )
        assert summary.issue_count >= 1
        assert summary.issues_by_severity
        assert summary.issues_by_code[CODE_VCS_SOURCE] == 2

    def test_the_declared_project_licence_is_carried_through(self):
        _, _, summary = analysis.build_analysis([manifest()], [dep("a")], declared_license="MIT")
        assert summary.declared_license == "MIT"

    def test_a_missing_project_licence_is_none_not_empty_string(self):
        _, _, summary = analysis.build_analysis([manifest()], [dep("a")])
        assert summary.declared_license is None


# --------------------------------------------------------------------------
# End to end over the analysis layer
# --------------------------------------------------------------------------


class TestBuildAnalysis:
    def test_a_manifest_and_its_lockfile_produce_one_inventory(self):
        from app.services import supply_chain_parser as parser

        manifests, rows, declared = [], [], None
        for path, text in (("package.json", PACKAGE_JSON), ("package-lock.json", PACKAGE_LOCK)):
            row_manifest, parsed, licence = parser.parse_file(path, text)
            manifests.append(row_manifest)
            rows.extend(parsed)
            if declared is None and licence:
                declared = licence
        licenses, issues, summary = analysis.build_analysis(
            manifests, rows, declared_license=declared
        )
        # express, lodash, app-lib, quiet, from-git declared; body-parser, ms inherited.
        assert summary.total_dependencies == 7
        assert summary.direct_dependencies == 5
        assert summary.transitive_dependencies == 2
        assert CODE_NO_LOCKFILE not in codes(issues)
        assert declared == "MIT"

    def test_a_repository_with_no_dependency_files_still_produces_a_report(self):
        _, issues, summary = analysis.build_analysis(
            [manifest(found=False)], []
        )
        assert summary.total_dependencies == 0
        assert CODE_NO_MANIFEST in codes(issues)
