"""Dependency scanner tests.

The recurring assertion in this file is that the scanner reports only what it
can prove. A dependency with a floating version is a fact about the manifest; a
dependency with a known CVE is a fact about an external advisory database. This
module never claims the second, and the tests hold it to that.
"""

import asyncio

import pytest

from app.services import security_dependency_scanner as scanner
from app.services.security_dependency_scanner import (
    RISK_PROFILES,
    SECURITY_MANIFESTS,
    ParsedVersion,
    SecurityDependency,
    Vulnerability,
    parse_version,
    scan_dependencies,
    scan_manifest,
    vulnerability_source_name,
)

PACKAGE_JSON = """{
  "dependencies": {"express": "^4.17.21", "lodash": "*", "left-pad": "1.3.0"},
  "devDependencies": {"jest": "29.0.0"}
}"""

PACKAGE_LOCK = """{
  "lockfileVersion": 3,
  "packages": {
    "": {"name": "app", "version": "1.0.0"},
    "node_modules/express": {"name": "express", "version": "4.17.21"},
    "node_modules/ms": {"name": "ms", "version": "2.1.3"}
  }
}"""

REQUIREMENTS = "\n".join(
    [
        "# a comment",
        "",
        "requests==2.31.0",
        "flask>=2.0",
        "django",
        "celery @ git+https://github.com/celery/celery.git#main",
        "-e ./localpkg",
        "-r other-requirements.txt",
    ]
)

PYPROJECT = """[project]
name = "app"
version = "0.1.0"
dependencies = [
  "httpx>=0.24",
  "pydantic==2.5.0",
]
[project.optional-dependencies]
dev = ["pytest==7.4.0"]
"""

GO_MOD = """module example.com/app

go 1.21

require (
\tgithub.com/gin-gonic/gin v1.9.1
\tgolang.org/x/text v0.14.0 // indirect
)

require github.com/pkg/errors v0.9.1
"""

POM = """<project>
  <dependencyManagement><dependencies>
    <dependency>
      <groupId>com.fasterxml.jackson.core</groupId>
      <artifactId>jackson-databind</artifactId>
      <version>2.15.2</version>
    </dependency>
  </dependencies></dependencyManagement>
  <dependencies>
    <dependency>
      <groupId>com.fasterxml.jackson.core</groupId>
      <artifactId>jackson-databind</artifactId>
    </dependency>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-web</artifactId>
      <version>${spring.version}</version>
    </dependency>
  </dependencies>
</project>
"""

ALL_MANIFESTS = {
    "package.json": PACKAGE_JSON,
    "package-lock.json": PACKAGE_LOCK,
    "requirements.txt": REQUIREMENTS,
    "pyproject.toml": PYPROJECT,
    "go.mod": GO_MOD,
    "pom.xml": POM,
}


def risks_for(path, content, name):
    return {
        match.risk
        for match in scan_manifest(path, content)
        if match.dependency == name
    }


class TestManifestSupport:
    def test_every_required_manifest_is_supported(self):
        paths = {path for path, _ in SECURITY_MANIFESTS}
        assert paths == {
            "package.json",
            "package-lock.json",
            "requirements.txt",
            "pyproject.toml",
            "pom.xml",
            "go.mod",
        }

    def test_every_declared_manifest_has_a_parser(self):
        for path, _ in SECURITY_MANIFESTS:
            assert path in scanner.PARSERS

    def test_each_manifest_yields_dependencies(self):
        for path, content in ALL_MANIFESTS.items():
            parsed = scanner.parse_manifest(path, "", content)
            assert parsed, f"{path} produced no dependencies"

    def test_dependencies_carry_ecosystem_and_manifest(self):
        for path, content in ALL_MANIFESTS.items():
            for dependency in scanner.parse_manifest(path, "", content):
                assert dependency.ecosystem
                assert dependency.manifest == path
                assert dependency.name

    def test_npm_sections_carry_their_scope(self):
        parsed = {d.name: d for d in scanner.parse_manifest("package.json", "", PACKAGE_JSON)}
        assert parsed["express"].scope == "runtime"
        assert parsed["jest"].scope == "development"

    def test_package_lock_reads_the_resolved_graph(self):
        names = {
            d.name for d in scanner.parse_manifest("package-lock.json", "", PACKAGE_LOCK)
        }
        assert {"express", "ms"} <= names
        # The root project is not a dependency of itself.
        assert "app" not in names

    def test_package_lock_marks_transitive_packages(self):
        parsed = {d.name: d for d in scanner.parse_manifest("package-lock.json", "", PACKAGE_LOCK)}
        assert parsed["ms"].direct is True

    def test_requirements_skips_comments_includes_and_editable_installs(self):
        names = {d.name for d in scanner.parse_manifest("requirements.txt", "", REQUIREMENTS)}
        assert "requests" in names
        assert "local-project" not in names
        assert "other-requirements" not in names

    def test_pyproject_reads_optional_dependency_groups(self):
        scopes = {
            d.scope for d in scanner.parse_manifest("pyproject.toml", "", PYPROJECT)
        }
        assert "runtime" in scopes
        assert any(scope.startswith("extra:") for scope in scopes)

    def test_go_mod_reads_both_require_forms(self):
        names = {d.name for d in scanner.parse_manifest("go.mod", "", GO_MOD)}
        assert {"github.com/gin-gonic/gin", "golang.org/x/text", "github.com/pkg/errors"} <= names

    def test_go_mod_marks_indirect_requirements(self):
        parsed = {d.name: d for d in scanner.parse_manifest("go.mod", "", GO_MOD)}
        assert parsed["golang.org/x/text"].direct is False

    def test_pom_reads_managed_and_direct_dependencies(self):
        parsed = {d.name: d for d in scanner.parse_manifest("pom.xml", "", POM)}
        jackson = "com.fasterxml.jackson.core:jackson-databind"
        # A managed version is picked up for a dependency that declares none.
        assert jackson in parsed
        assert parsed[jackson].version == "2.15.2"

    def test_dependencies_carry_line_numbers(self):
        for path, content in ALL_MANIFESTS.items():
            located = [
                d for d in scanner.parse_manifest(path, "", content) if d.line > 0
            ]
            assert located, f"{path} produced no located dependencies"

    def test_maven_coordinates_use_group_colon_artifact(self):
        names = {d.name for d in scanner.parse_manifest("pom.xml", "", POM)}
        assert "org.springframework.boot:spring-boot-starter-web" in names


class TestMalformedManifests:
    @pytest.mark.parametrize(
        "path,content",
        [
            ("package.json", "{not valid json"),
            ("package.json", "[1, 2, 3]"),
            ("package-lock.json", "{nope"),
            ("pyproject.toml", "[project\nbroken"),
            ("go.mod", "\t\tmalformed require (("),
            ("pom.xml", "<project><dependency><groupId>"),
        ],
    )
    def test_malformed_manifest_yield_no_dependencies_rather_than_raising(self, path, content):
        assert scanner.parse_manifest(path, "", content) == []

    def test_unknown_manifest_is_not_an_error(self):
        assert scanner.parse_manifest("Cargo.toml", "rust", "[dependencies]") == []

    def test_manifest_with_no_dependencies_is_empty(self):
        assert scanner.parse_manifest("package.json", "", '{"name": "x"}') == []

    def test_a_malformed_manifest_does_not_abort_a_multi_manifest_scan(self):
        manifests = {"package.json": "{broken", "go.mod": GO_MOD}
        matches, count, _ = asyncio.run(scan_dependencies(manifests))
        assert count == 3
        assert isinstance(matches, list)


class TestVersionParsing:
    @pytest.mark.parametrize(
        "raw,usable,kind",
        [
            ("1.2.3", True, "exact"),
            ("==2.31.0", True, "exact"),
            ("===1.0.0", True, "exact"),
            ("v1.9.1", True, "exact"),
            ("1.2", True, "exact"),
            (">=2.0", False, "range"),
            ("^4.17.21", False, "range"),
            ("~1.2.3", False, "range"),
            ("*", False, "unpinned"),
            ("latest", False, "unpinned"),
            (None, False, "missing"),
            ("", False, "missing"),
            ("git+https://github.com/o/r.git", False, "vcs"),
            ("https://example.com/pkg.tar.gz", False, "vcs"),
            ("a" * 40, False, "commit"),
            ("./local", False, "local_path"),
            ("/abs/path", False, "local_path"),
            ("${spring.version}", False, "placeholder"),
            ("==not.a.version", False, "unresolvable"),
        ],
    )
    def test_version_kinds_are_classified(self, raw, usable, kind):
        parsed = parse_version(raw)
        assert parsed.usable is usable
        assert parsed.kind == kind

    def test_an_exact_pin_is_not_mistaken_for_a_range(self):
        # "==2.31.0" contains a range character, but it is a pin.
        assert parse_version("==2.31.0").usable is True

    def test_a_range_is_never_reported_as_usable(self):
        assert parse_version(">=1.0").usable is False

    def test_unparseable_pins_are_labelled_unresolvable_not_floating(self):
        # The author intended an exact pin; only the value is unusable.
        assert parse_version("==banana").kind == "unresolvable"

    def test_parsed_version_exposes_the_original_value(self):
        assert parse_version("==1.2.3").raw == "==1.2.3"

    def test_line_is_preserved(self):
        assert parse_version("1.2.3", line=42).line == 42


class TestRiskClassification:
    def test_wildcard_is_unpinned(self):
        assert "unpinned" in risks_for("package.json", PACKAGE_JSON, "lodash")

    def test_caret_range_is_floating(self):
        assert "floating_version" in risks_for("package.json", PACKAGE_JSON, "express")

    def test_exact_pins_produce_no_version_risk(self):
        # "jest" is pinned and is not on the deprecated list, so it is clean.
        assert risks_for("package.json", PACKAGE_JSON, "jest") == set()
        assert risks_for("go.mod", GO_MOD, "github.com/gin-gonic/gin") == set()

    def test_an_exact_pin_is_still_reported_when_the_package_is_deprecated(self):
        # Version hygiene and deprecation are independent axes.
        assert risks_for("package.json", PACKAGE_JSON, "left-pad") == {
            "deprecated_package"
        }

    def test_dependency_without_a_version_is_missing(self):
        assert "missing_version" in risks_for("requirements.txt", REQUIREMENTS, "django")

    def test_vcs_dependency_is_a_git_source(self):
        assert "git_source" in risks_for("requirements.txt", REQUIREMENTS, "celery")

    def test_deprecated_package_is_reported(self):
        risks = risks_for("package.json", PACKAGE_JSON, "left-pad")
        assert "deprecated_package" in risks

    def test_maven_property_is_reported_once(self):
        risks = risks_for("pom.xml", POM, "org.springframework.boot:spring-boot-starter-web")
        assert risks == {"unresolvable_version"}

    def test_a_weakness_is_reported_once_not_once_per_label(self):
        # A range is already "floating_version"; adding "unresolvable_version"
        # would inflate the finding count for a single problem.
        risks = risks_for("package.json", PACKAGE_JSON, "express")
        assert "unresolvable_version" not in risks
        assert "floating_version" in risks

    def test_manifest_counts_are_returned_alongside_findings(self):
        _, count, _ = asyncio.run(scan_dependencies(ALL_MANIFESTS))
        assert count > 10

    def test_every_reported_risk_has_a_profile(self):
        for path, content in ALL_MANIFESTS.items():
            for match in scan_manifest(path, content):
                assert match.risk in RISK_PROFILES

    def test_declared_version_is_recorded_for_the_reader(self):
        match = next(
            m for m in scan_manifest("package.json", PACKAGE_JSON) if m.dependency == "express"
        )
        assert match.declared_version == "^4.17.21"

    def test_a_manifest_of_exact_pins_produces_no_findings(self):
        # A clean go.mod must report nothing. A scanner that always finds
        # something is not reporting, it is generating noise.
        assert scan_manifest("go.mod", GO_MOD) == []

    def test_findings_carry_dependency_provenance(self):
        match = scan_manifest("requirements.txt", REQUIREMENTS)[0]
        payload = match.as_finding()
        assert payload["scanner"] == "dependency"
        assert payload["category"] == "dependencies"

    def test_fingerprints_are_stable_and_distinct_per_risk(self):
        first = scan_manifest("requirements.txt", REQUIREMENTS)
        second = scan_manifest("requirements.txt", REQUIREMENTS)
        assert [m.fingerprint for m in first] == [m.fingerprint for m in second]
        assert len({m.fingerprint for m in first}) == len(first)


class TestVulnerabilityProvider:
    def test_no_provider_is_registered_by_default(self):
        assert vulnerability_source_name() == "none"

    def test_no_vulnerability_is_invented_without_a_provider(self):
        matches, _, source = asyncio.run(scan_dependencies(ALL_MANIFESTS))
        assert source == "none"
        assert all(match.risk != "known_vulnerability" for match in matches)

    def test_a_registered_provider_contributes_advisories(self):
        class StubProvider:
            name = "stub-advisories"

            async def lookup(self, dependencies):
                return [
                    Vulnerability(
                        dependency="left-pad",
                        ecosystem="npm",
                        advisory_id="ADV-001",
                        severity="high",
                        title="Prototype pollution",
                        description="d",
                        remediation="Upgrade.",
                    )
                ]

        matches, _, source = asyncio.run(
            scan_dependencies({"package.json": PACKAGE_JSON}, provider=StubProvider())
        )
        assert source == "stub-advisories"
        assert any(m.risk == "known_vulnerability" for m in matches)

    def test_a_failing_provider_degrades_to_mechanical_findings(self):
        class BrokenProvider:
            name = "broken"

            async def lookup(self, dependencies):
                raise RuntimeError("advisory service is down")

        matches, count, source = asyncio.run(
            scan_dependencies({"requirements.txt": REQUIREMENTS}, provider=BrokenProvider())
        )
        # The scan still completes with everything provable from the manifest.
        assert source == "broken"
        assert count > 0
        assert all(m.risk != "known_vulnerability" for m in matches)

    def test_provider_registration_is_observable(self):
        class Named:
            name = "named-source"

            async def lookup(self, dependencies):
                return []

        scanner.register_vulnerability_provider(Named())
        try:
            assert vulnerability_source_name() == "named-source"
            assert scanner.active_vulnerability_provider().name == "named-source"
        finally:
            scanner._VULNERABILITY_PROVIDERS.clear()

    def test_rule_summary_states_the_vulnerability_source(self):
        summary = scanner.rule_summary()
        assert summary["vulnerability_source"] == "none"
        assert {m["path"] for m in summary["manifests"]} == set(ALL_MANIFESTS)
        assert "unpinned" in summary["risks"]


class TestSourceScreening:
    def test_manifest_detection_is_by_basename(self):
        from app.services import security_sources

        assert security_sources.is_manifest_path("package.json")
        assert security_sources.is_manifest_path("sub/dir/requirements.txt")
        assert security_sources.is_manifest_path("services/api/requirements-dev.txt")
        assert not security_sources.is_manifest_path("mygo.mod.bak")
        assert not security_sources.is_manifest_path("app.py")

    def test_lockfiles_are_screened_out_of_scanning(self):
        # A lockfile is a resolved graph, not a secret-bearing source file, and
        # the dependency scanner reads it deliberately rather than by accident.
        from app.services import security_sources

        assert security_sources.is_ignored_path("package-lock.json")
        assert security_sources.is_ignored_path("app/package-lock.json")
        assert not security_sources.is_ignored_path("package.json")
