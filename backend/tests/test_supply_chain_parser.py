"""Tests for the deterministic supply-chain parser.

The parser's job is to report only what a repository actually declares. These
tests are therefore as much about the boundaries - what must *not* be inferred -
as about the happy paths.
"""

from __future__ import annotations

import pytest

from app.schemas.supply_chain import (
    LIC_PERMISSIVE,
    LIC_PROPRIETARY,
    LIC_PUBLIC_DOMAIN,
    LIC_STRONG_COPYLEFT,
    LIC_UNKNOWN,
    LIC_WEAK_COPYLEFT,
    ORIGIN_DIRECT,
    ORIGIN_TRANSITIVE,
    ROLE_LOCKFILE,
    ROLE_MANIFEST,
)
from app.services import supply_chain_parser as parser

PACKAGE_JSON = """{
  "name": "demo",
  "version": "1.0.0",
  "license": "MIT",
  "dependencies": {
    "express": "^4.17.21",
    "lodash": {"version": "4.17.21", "license": "MIT"},
    "app-lib": {"version": "2.0.0", "license": "GPL-3.0-only"},
    "quiet": {"version": "0.1.0"},
    "from-git": "git+https://github.com/o/r.git"
  },
  "devDependencies": {"jest": "29.7.0"}
}"""

PACKAGE_LOCK = """{
  "lockfileVersion": 3,
  "packages": {
    "": {"name": "demo"},
    "node_modules/express": {"version": "4.17.21", "license": "MIT"},
    "node_modules/body-parser": {"version": "1.20.0", "license": "MIT"},
    "node_modules/ms": {"version": "2.1.3", "license": "MIT"}
  }
}"""


# --------------------------------------------------------------------------
# Path classification
# --------------------------------------------------------------------------


class TestClassifyPath:
    @pytest.mark.parametrize(
        "path,ecosystem,role",
        [
            ("package.json", "npm", ROLE_MANIFEST),
            ("services/api/go.mod", "go", ROLE_MANIFEST),
            ("backend/pyproject.toml", "pypi", ROLE_MANIFEST),
            ("requirements.txt", "pypi", ROLE_MANIFEST),
            ("pom.xml", "maven", ROLE_MANIFEST),
            ("package-lock.json", "npm", ROLE_LOCKFILE),
            ("yarn.lock", "npm", ROLE_LOCKFILE),
            ("poetry.lock", "pypi", ROLE_LOCKFILE),
            ("go.sum", "go", ROLE_LOCKFILE),
            ("Cargo.lock", "cargo", ROLE_LOCKFILE),
        ],
    )
    def test_known_files_are_classified(self, path, ecosystem, role):
        assert parser.classify_path(path) == (ecosystem, role)

    def test_a_nested_manifest_is_classified(self):
        assert parser.classify_path("services/api/requirements.txt") == ("pypi", ROLE_MANIFEST)

    def test_unrelated_files_are_not_classified(self):
        assert parser.classify_path("src/main.py") is None
        assert parser.classify_path("README.md") is None

    def test_pom_is_a_manifest_not_a_lockfile(self):
        # <dependencyManagement> is version management, not a resolved graph.
        assert parser.classify_path("pom.xml")[1] == ROLE_MANIFEST


# --------------------------------------------------------------------------
# Target selection
# --------------------------------------------------------------------------


class TestSelectTargets:
    def test_dependency_files_are_selected(self):
        entries = [
            {"path": "package.json", "type": "blob"},
            {"path": "go.mod", "type": "blob"},
            {"path": "src/main.py", "type": "blob"},
        ]
        assert parser.select_targets(entries) == ["go.mod", "package.json"]

    def test_vendored_dependency_trees_are_excluded(self):
        entries = [
            {"path": "package.json", "type": "blob"},
            {"path": "node_modules/left-pad/package.json", "type": "blob"},
        ]
        assert parser.select_targets(entries) == ["package.json"]

    def test_directory_entries_are_ignored(self):
        entries = [{"path": "go.mod", "type": "tree"}]
        assert parser.select_targets(entries) == []

    def test_entries_without_a_path_are_ignored(self):
        assert parser.select_targets([{"type": "blob"}, "nonsense", None]) == []

    def test_selection_is_deterministic(self):
        entries = [
            {"path": "package.json", "type": "blob"},
            {"path": "go.mod", "type": "blob"},
            {"path": "requirements.txt", "type": "blob"},
        ]
        assert parser.select_targets(entries) == parser.select_targets(entries)

    def test_duplicates_collapse_to_one_entry(self):
        entries = [
            {"path": "package.json", "type": "blob"},
            {"path": "package.json", "type": "blob"},
        ]
        assert parser.select_targets(entries) == ["package.json"]


# --------------------------------------------------------------------------
# Licence classification
# --------------------------------------------------------------------------


class TestClassifyLicense:
    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("MIT", LIC_PERMISSIVE),
            ("mit", LIC_PERMISSIVE),
            ("Apache-2.0", LIC_PERMISSIVE),
            ("BSD-3-Clause", LIC_PERMISSIVE),
            ("ISC", LIC_PERMISSIVE),
            ("0BSD", LIC_PERMISSIVE),
            ("CC0-1.0", LIC_PUBLIC_DOMAIN),
            ("Unlicense", LIC_PERMISSIVE),
            ("MPL-2.0", LIC_WEAK_COPYLEFT),
            ("LGPL-2.1", LIC_WEAK_COPYLEFT),
            ("LGPL-3.0-only", LIC_WEAK_COPYLEFT),
            ("EPL-2.0", LIC_WEAK_COPYLEFT),
            ("GPL-2.0", LIC_STRONG_COPYLEFT),
            ("GPL-3.0-only", LIC_STRONG_COPYLEFT),
            ("AGPL-3.0", LIC_STRONG_COPYLEFT),
            ("UNLICENSED", LIC_PROPRIETARY),
            ("SEE LICENSE IN LICENSE", LIC_PROPRIETARY),
            ("LicenseRef-Internal", LIC_PROPRIETARY),
        ],
    )
    def test_known_expressions_are_classified(self, expression, expected):
        assert parser.classify_license(expression) == expected

    @pytest.mark.parametrize(
        "expression",
        [None, "", "   ", "SEE LICENSE", "latest", "unknown", "TBD"],
    )
    def test_absent_or_unusable_expressions_are_unknown(self, expression):
        assert parser.classify_license(expression) == LIC_UNKNOWN

    def test_an_unrecognised_identifier_is_not_assumed_permissive(self):
        # The one mistake this report must not make: a licence nobody recognises
        # must not be folded into a permissive bucket.
        assert parser.classify_license("Acme-Corp-Internal-1.0") == LIC_UNKNOWN

    def test_an_exception_does_not_change_the_base_posture(self):
        assert parser.classify_license("Apache-2.0 WITH LLVM-exception") == LIC_PERMISSIVE

    def test_a_disjunction_takes_the_most_restrictive_term(self):
        # A user choosing between terms can only rely on the weaker grant.
        assert parser.classify_license("MIT OR GPL-3.0-only") == LIC_STRONG_COPYLEFT
        assert parser.classify_license("MIT OR Apache-2.0") == LIC_PERMISSIVE

    def test_a_json_blob_is_not_a_licence(self):
        assert parser.classify_license('{"type": "MIT"}') == LIC_UNKNOWN

    def test_an_over_long_string_is_not_a_licence(self):
        assert parser.classify_license("MIT " * 100) == LIC_UNKNOWN


# --------------------------------------------------------------------------
# Project licence
# --------------------------------------------------------------------------


class TestProjectLicense:
    def test_package_json_licence_is_read(self):
        assert parser.project_license_expression("package.json", PACKAGE_JSON) == "MIT"

    def test_pyproject_licence_is_read(self):
        content = '[project]\nname = "x"\nlicense = "Apache-2.0"\n'
        assert parser.project_license_expression("pyproject.toml", content) == "Apache-2.0"

    def test_the_legacy_pyproject_licence_table_is_read(self):
        content = '[project]\nname = "x"\nlicense = {text = "BSD-3-Clause"}\n'
        assert parser.project_license_expression("pyproject.toml", content) == "BSD-3-Clause"

    def test_pom_licence_is_read(self):
        content = (
            "<project><licenses><license><name>MIT</name>"
            "</license></licenses></project>"
        )
        assert parser.project_license_expression("pom.xml", content) == "MIT"

    def test_the_licenses_array_form_is_read(self):
        content = '{"name": "x", "licenses": [{"type": "ISC"}]}'
        assert parser.project_license_expression("package.json", content) == "ISC"

    def test_a_generic_bsd_clause_is_not_guessed(self):
        # The 2-, 3- and 4-clause BSD texts and MIT all share this sentence, so
        # naming one of them would be an invention.
        text = "Redistribution and use in source and binary forms, with or without\nmodification, are permitted."
        assert parser.project_license_expression("LICENSE", text) is None

    def test_distinctive_licence_text_is_identified(self):
        assert (
            parser.project_license_expression(
                "LICENSE", "MIT License\n\nPermission is hereby granted, free of charge..."
            )
            == "MIT"
        )
        assert (
            parser.project_license_expression(
                "LICENSE", "Apache License\nVersion 2.0, January 2004"
            )
            == "Apache-2.0"
        )
        assert (
            parser.project_license_expression(
                "LICENSE", "GNU AFFERO GENERAL PUBLIC LICENSE\nVersion 3"
            )
            == "AGPL-3.0"
        )

    def test_creative_commons_by_is_not_treated_as_a_dedication(self):
        text = "Creative Commons Attribution 4.0 International"
        assert parser.project_license_expression("LICENSE", text) == "CC-BY-4.0"

    def test_custom_licence_text_stays_unknown(self):
        assert parser.project_license_expression("LICENSE", "Internal use only.") is None


# --------------------------------------------------------------------------
# Manifest parsing
# --------------------------------------------------------------------------


class TestParseManifest:
    def test_package_json_dependencies_are_direct(self):
        manifest, rows, declared = parser.parse_file("package.json", PACKAGE_JSON)
        assert manifest.found is True
        assert manifest.role == ROLE_MANIFEST
        assert manifest.parse_failed is False
        assert declared == "MIT"
        assert all(row.origin == ORIGIN_DIRECT for row in rows)
        assert {row.name for row in rows} == {
            "express",
            "lodash",
            "app-lib",
            "quiet",
            "from-git",
            "jest",
        }

    def test_dev_dependencies_are_scoped_as_development(self):
        _, rows, _ = parser.parse_file("package.json", PACKAGE_JSON)
        assert next(row for row in rows if row.name == "jest").scope == "development"

    def test_object_form_specs_yield_a_version_not_a_stringified_object(self):
        # npm allows {"version": "...", "license": "..."}. The shared parsers
        # stringify whatever sits in the version position, which would report an
        # unpinned floating dependency the repository never declared.
        _, rows, _ = parser.parse_file("package.json", PACKAGE_JSON)
        lodash = next(row for row in rows if row.name == "lodash")
        assert lodash.version == "4.17.21"
        assert lodash.pinned is True

    def test_an_object_spec_without_a_version_is_reported_as_floating(self):
        content = '{"dependencies": {"a": {"license": "MIT"}}}'
        _, rows, _ = parser.parse_file("package.json", content)
        assert rows[0].pinned is False

    def test_declared_licences_are_attached_to_the_right_packages(self):
        _, rows, _ = parser.parse_file("package.json", PACKAGE_JSON)
        by_name = {row.name: row for row in rows}
        assert by_name["lodash"].license_expression == "MIT"
        assert by_name["lodash"].license_category == LIC_PERMISSIVE
        assert by_name["app-lib"].license_category == LIC_STRONG_COPYLEFT
        # "quiet" declares no licence at all, which is not the same as unknown.
        assert by_name["quiet"].license_expression is None
        assert by_name["quiet"].license_category == LIC_UNKNOWN

    def test_the_projects_licence_is_never_attributed_to_a_dependency(self):
        # package.json declares the project's own MIT. That must not leak onto
        # every package as if each one had declared it.
        _, rows, _ = parser.parse_file("package.json", PACKAGE_JSON)
        assert next(row for row in rows if row.name == "quiet").license_expression is None

    def test_lockfile_licences_are_read(self):
        _, rows, _ = parser.parse_file("package-lock.json", PACKAGE_LOCK)
        assert all(row.license_expression == "MIT" for row in rows)

    def test_requirements_txt_is_parsed(self):
        content = "requests==2.31.0\nflask>=3.0\nsomepkg\n"
        manifest, rows, _ = parser.parse_file("requirements.txt", content)
        assert manifest.ecosystem == "pypi"
        assert {row.name for row in rows} == {"requests", "flask", "somepkg"}
        assert next(row for row in rows if row.name == "requests").pinned is True
        assert next(row for row in rows if row.name == "flask").pinned is False

    def test_go_mod_is_parsed(self):
        content = "module x\n\ngo 1.21\n\nrequire (\n\tgithub.com/gin-gonic/gin v1.9.1\n)\n"
        manifest, rows, _ = parser.parse_file("go.mod", content)
        assert manifest.ecosystem == "go"
        assert rows[0].name == "github.com/gin-gonic/gin"
        assert rows[0].pinned is True

    def test_a_vcs_sourced_dependency_is_flagged(self):
        _, rows, _ = parser.parse_file("package.json", PACKAGE_JSON)
        assert "git_source" in next(row for row in rows if row.name == "from-git").risks

    def test_an_unrelated_file_yields_nothing(self):
        manifest, rows, _ = parser.parse_file("src/main.py", "print(1)\n")
        assert rows == []
        assert manifest.found is False

    def test_a_missing_file_is_reported_as_absent_not_empty(self):
        manifest, rows, _ = parser.parse_file("go.mod", "", found=False)
        assert manifest.found is False
        assert rows == []
        assert "Not found" in manifest.note


# --------------------------------------------------------------------------
# Well-formedness
# --------------------------------------------------------------------------


class TestWellformed:
    def test_valid_json_is_wellformed(self):
        assert parser.is_wellformed("package.json", PACKAGE_JSON) is True

    def test_broken_json_is_not_wellformed(self):
        assert parser.is_wellformed("package.json", "{not json") is False

    def test_broken_toml_is_not_wellformed(self):
        assert parser.is_wellformed("pyproject.toml", "[project") is False

    def test_valid_toml_is_wellformed(self):
        assert parser.is_wellformed("pyproject.toml", '[project]\nname = "x"\n') is True

    def test_a_pom_without_a_project_root_is_not_wellformed(self):
        assert parser.is_wellformed("pom.xml", "not xml at all") is False

    def test_an_empty_but_valid_manifest_is_not_a_parse_failure(self):
        # A readable manifest that declares nothing is a state, not a defect.
        manifest, rows, _ = parser.parse_file("package.json", '{"name": "d", "dependencies": {}}')
        assert manifest.parse_failed is False
        assert rows == []
        assert "declares no dependencies" in manifest.note

    def test_broken_json_is_reported_as_a_parse_failure(self):
        manifest, rows, _ = parser.parse_file("package.json", "{not json")
        assert manifest.parse_failed is True
        assert rows == []
        assert "Could not be parsed" in manifest.note

    def test_an_unexpanded_lockfile_is_not_a_parse_failure(self):
        # yarn.lock is fine; this report simply does not expand it.
        manifest, rows, _ = parser.parse_file("yarn.lock", "# yarn lockfile v1\n")
        assert manifest.parse_failed is False
        assert rows == []
        assert "not expanded" in manifest.note

    def test_an_empty_file_is_not_a_parse_failure(self):
        manifest, _, _ = parser.parse_file("requirements.txt", "")
        assert manifest.parse_failed is False


# --------------------------------------------------------------------------
# Missing manifests
# --------------------------------------------------------------------------


class TestMissingManifest:
    def test_absent_candidates_are_reported(self):
        rows = parser.missing_manifest(parser.MANIFEST_FILES)
        assert {row.path for row in rows} == {
            "package.json",
            "requirements.txt",
            "pyproject.toml",
            "go.mod",
            "pom.xml",
        }
        assert all(row.found is False for row in rows)
        assert all(row.dependency_count == 0 for row in rows)

    def test_an_absent_manifest_is_distinct_from_an_empty_one(self):
        rows = {row.path: row for row in parser.missing_manifest(parser.MANIFEST_FILES)}
        assert "Not found" in rows["go.mod"].note
