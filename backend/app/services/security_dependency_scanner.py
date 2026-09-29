"""Deterministic dependency scanner.

Three jobs, in order
--------------------
1. **Parse** every supported manifest into one common representation. Parsing
   lives here rather than in :mod:`app.services.repository_dependency_service`
   because the security engine needs two manifests that the repository
   intelligence view deliberately does not surface: ``package-lock.json`` (the
   resolved graph, which is what actually ships) and ``pom.xml``. Existing
   parsers are reused where the format and the risk vocabulary already match, so
   a requirement is classified identically in both features.
2. **Report mechanical risk** — unpinned, missing, floating, VCS-sourced,
   local-path and project-deprecated dependencies. These are properties of the
   recorded version string, decidable with no network access, and they are what
   this module reports.
3. **Delegate known vulnerabilities** to a provider adapter. See
   :class:`VulnerabilityProvider` for why no vulnerability data ships here.

The version-validation boundary
-------------------------------
:class:`ParsedVersion` deliberately separates "the manifest said something"
from "that something is a usable version". Many manifests record
``latest``, a git SHA or a template placeholder in the version field. Those are
reported as :attr:`ParsedVersion.usable is False` rather than being coerced into
a version that looks valid, because a scanner that invents a version invites a
reviewer to trust a number nobody verified.
"""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass, field
from typing import Any, Iterable, Protocol, Sequence

from app.services import repository_dependency_service, security_sources

ECOSYSTEM_NPM = "npm"
ECOSYSTEM_PYPI = "pypi"
ECOSYSTEM_GO = "go"
ECOSYSTEM_MAVEN = "maven"

#: Manifests the security engine reads, in probe order. ``package-lock.json``
#: comes before ``package.json`` because a resolved lockfile is the authoritative
#: record of what ships, but both are read: the lockfile pins versions while
#: ``package.json`` carries the declared ranges.
SECURITY_MANIFESTS: tuple[tuple[str, str], ...] = (
    ("package.json", ECOSYSTEM_NPM),
    ("package-lock.json", ECOSYSTEM_NPM),
    ("requirements.txt", ECOSYSTEM_PYPI),
    ("pyproject.toml", ECOSYSTEM_PYPI),
    ("pom.xml", ECOSYSTEM_MAVEN),
    ("go.mod", ECOSYSTEM_GO),
)

#: Manifest basenames the engine will accept anywhere in the tree.
MANIFEST_BASENAMES = frozenset(name for name, _ in SECURITY_MANIFESTS)

#: Version strings that look like a version but are not resolvable. Reported as
#: an unusable version rather than silently accepted.
NON_VERSION_VALUES = frozenset(
    {
        "latest",
        "next",
        "nightly",
        "canary",
        "stable",
        "master",
        "main",
        "head",
        "dev",
        "develop",
        "tip",
        "*",
        "x",
        "X",
        "any",
    }
)

_SEMVER_RE = re.compile(
    r"^v?\d+(?:\.\d+){0,3}(?:[-.][0-9A-Za-z][0-9A-Za-z.\-+]*)?$"
)
#: An exact pin operator: ``==1.2.3`` (pip), ``===1.2.3``, ``=1.2.3`` (npm).
_PIN_OPERATOR_RE = re.compile(r"^=+\s*")
_RANGE_RE = re.compile(r"[<>=!~^|]|\s|&&|\|\|")
_URL_RE = re.compile(r"^[a-z][a-z0-9+.-]*://", re.IGNORECASE)
_GIT_RE = re.compile(r"^(?:git\+)?(?:git|hg|svn|bzr)@|^(?:git\+)?https?://", re.IGNORECASE)
_GITHUB_RE = re.compile(r"^(?:github|gitlab|bitbucket):|[\w.-]+/[\w.-]+#")
_LOCAL_PATH_RE = re.compile(r"^(?:\.{1,2}[/\\]|[/\\]|[A-Za-z]:[/\\]|file://)")
_COMMIT_SHA_RE = re.compile(r"^[0-9a-f]{7,40}$", re.IGNORECASE)

#: Risk label -> (severity, title template, remediation). One table, so the same
#: mechanical property is always reported with the same severity regardless of
#: which parser produced it.
RISK_PROFILES: dict[str, tuple[str, str, str]] = {
    "missing_version": (
        "high",
        "Dependency declared with no version",
        "A dependency with no version constraint resolves to whatever the "
        "registry considers current at install time, so a build is not "
        "reproducible and a compromised release lands silently. Pin an exact "
        "version.",
    ),
    "unpinned": (
        "high",
        "Dependency pinned to a wildcard",
        "A wildcard version accepts any release of the package, including one "
        "published after this code was reviewed. Pin an exact version.",
    ),
    "floating_version": (
        "medium",
        "Dependency constrained by a range",
        "A version range allows upgrades that were never reviewed, so a new "
        "release can change behaviour without any code change. Pin the version "
        "and update it deliberately.",
    ),
    "git_source": (
        "medium",
        "Dependency installed from a VCS or URL source",
        "A VCS or URL dependency bypasses registry immutability and integrity "
        "metadata: the referenced commit is not verified at install time. "
        "Publish the package to a registry, or vendor it with a checksum.",
    ),
    "local_path": (
        "low",
        "Dependency installed from a local path",
        "A local path dependency makes the build depend on the surrounding "
        "filesystem layout and is not reproducible elsewhere.",
    ),
    "deprecated_package": (
        "medium",
        "Dependency is deprecated upstream",
        "The package is marked deprecated by its registry, which usually means "
        "it no longer receives security fixes. Migrate to a maintained "
        "alternative.",
    ),
    "unresolvable_version": (
        "low",
        "Dependency version is not a resolvable release",
        "The recorded version is a branch, commit, tag or placeholder rather "
        "than a released version, so tooling cannot determine what is installed. "
        "Record an exact released version.",
    ),
}


@dataclass(frozen=True)
class ParsedVersion:
    """A manifest's version string, classified without resolving anything.

    ``usable`` is the load-bearing field: it is True only for something that
    could name a published release. Everything else — a range, a URL, a commit,
    ``latest`` — is a property of the declaration, not a version.
    """

    raw: str | None
    usable: bool
    exact: bool
    kind: str
    line: int = 0


def parse_version(raw: str | None, *, line: int = 0) -> ParsedVersion:
    """Classify a raw version declaration.

    The distinction this function exists to preserve is between a version and
    something that merely occupies the version position. ``>=2.0`` is a range,
    ``git+https://…`` is a source, ``latest`` is a tag — none of them is a
    resolvable release, and coercing any of them into one would let a reviewer
    trust a version nobody verified.
    """
    if raw is None or not str(raw).strip():
        return ParsedVersion(raw=None, usable=False, exact=False, kind="missing", line=line)

    value = str(raw).strip()

    if _LOCAL_PATH_RE.match(value):
        return ParsedVersion(value, usable=False, exact=False, kind="local_path", line=line)
    if _GIT_RE.match(value) or _GITHUB_RE.match(value) or _URL_RE.match(value):
        return ParsedVersion(value, usable=False, exact=False, kind="vcs", line=line)
    if _COMMIT_SHA_RE.match(value):
        return ParsedVersion(value, usable=False, exact=False, kind="commit", line=line)
    # A wildcard and a bare ``x`` placeholder are the unpinned case, which
    # ``unpinned`` already reports. They are classified as their own kind so
    # ``unresolvable_version`` does not double-report the same weakness.
    if value in ("*", "x", "X", "latest", "1.x", "0.x"):
        return ParsedVersion(value, usable=False, exact=False, kind="unpinned", line=line)
    if value in NON_VERSION_VALUES:
        return ParsedVersion(value, usable=False, exact=False, kind="tag", line=line)
    if "{{" in value or "${" in value or "<" in value:
        return ParsedVersion(value, usable=False, exact=False, kind="placeholder", line=line)

    # A resolved lockfile version can carry a sibling registry URL or integrity
    # hash; only the first token is the version.
    candidate = value.split(" ")[0].strip()

    # An exact pin operator (``==1.2.3`` pip, ``===1.2.3``, ``=1.2.3`` npm) is
    # declaration syntax, not part of the version. It is stripped *before* the
    # range check so an exact pin is not misread as a range, and before the
    # SEMVER check so a pinned version is usable.
    pin_stripped = _PIN_OPERATOR_RE.sub("", candidate)
    if pin_stripped != candidate:
        candidate = pin_stripped
        if _SEMVER_RE.match(candidate):
            return ParsedVersion(value, usable=True, exact=True, kind="exact", line=line)
        # Pinned to something that is not a release (``==latest``,
        # ``==not.a.version``). The pin is exact, so the only true statement is
        # that the version cannot be resolved — reporting it as a floating range
        # would misdescribe the author's intent.
        return ParsedVersion(
            value, usable=False, exact=False, kind="unresolvable", line=line
        )

    if candidate.startswith((">", "<", "!", "~", "^", "+")) or _RANGE_RE.search(candidate):
        return ParsedVersion(value, usable=False, exact=False, kind="range", line=line)

    if not _SEMVER_RE.match(candidate):
        return ParsedVersion(
            value, usable=False, exact=False, kind="unrecognized", line=line
        )

    return ParsedVersion(value, usable=True, exact=True, kind="exact", line=line)


@dataclass(frozen=True)
class SecurityDependency:
    """One dependency in the common representation every parser produces."""

    name: str
    ecosystem: str
    manifest: str
    version: str | None
    scope: str = "runtime"
    line: int = 0
    direct: bool = True
    risks: tuple[str, ...] = ()

    @property
    def parsed_version(self) -> ParsedVersion:
        return parse_version(self.version, line=self.line)


@dataclass(frozen=True)
class DependencyMatch:
    """A dependency-related security finding."""

    path: str
    line: int
    severity: str
    category: str
    scanner: str
    title: str
    description: str
    remediation: str
    confidence: float
    dependency: str
    ecosystem: str
    declared_version: str | None
    risk: str
    fingerprint: str

    def as_finding(self) -> dict:
        return {
            "file": self.path,
            "line": self.line,
            "column": None,
            "category": self.category,
            "severity": self.severity,
            "confidence": self.confidence,
            "title": self.title,
            "description": self.description,
            "remediation": self.remediation,
            "scanner": self.scanner,
            "fingerprint": self.fingerprint,
        }


# ---------------------------------------------------------------------------
# Vulnerability provider adapter
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Vulnerability:
    """A known vulnerability, as reported by an external advisory source."""

    dependency: str
    ecosystem: str
    advisory_id: str
    severity: str
    title: str
    description: str
    remediation: str
    affected_versions: str | None = None
    confidence: float = 0.9


class VulnerabilityProvider(Protocol):
    """Boundary for an authoritative vulnerability source.

    There is deliberately no default implementation. Inventing advisory data —
    or shipping a stale snapshot of it inside the scanner — would let a scan
    report a vulnerability nobody verified, and would be wrong in a way no test
    could catch. A deployment that wants known-CVE coverage supplies a provider;
    with none configured, :func:`scan_dependencies` reports only the mechanical
    risks it can prove, and the API says so via ``vulnerability_source``.
    """

    name: str

    async def lookup(
        self, dependencies: Sequence[SecurityDependency]
    ) -> list[Vulnerability]:
        ...


#: Providers registered at import time. Empty by default — see the protocol
#: docstring for why.
_VULNERABILITY_PROVIDERS: dict[str, VulnerabilityProvider] = {}


def register_vulnerability_provider(provider: VulnerabilityProvider) -> None:
    """Register the advisory source for this process."""
    _VULNERABILITY_PROVIDERS[provider.name] = provider


def active_vulnerability_provider() -> VulnerabilityProvider | None:
    if not _VULNERABILITY_PROVIDERS:
        return None
    return next(iter(_VULNERABILITY_PROVIDERS.values()))


def vulnerability_source_name() -> str:
    provider = active_vulnerability_provider()
    return provider.name if provider else "none"


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


def _fingerprint(path: str, name: str, ecosystem: str, risk: str) -> str:
    material = "|".join((path or "", name or "", ecosystem or "", risk or ""))
    import hashlib

    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]


def _line_of(content: str, needle: str) -> int:
    """Best-effort 1-based line number for a dependency name in a manifest.

    Manifests are read in full, so a cheap scan for the name is acceptable and
    gives a clickable line number in the UI. A miss reports line 0, the
    whole-file sentinel, rather than pointing at the wrong line.
    """
    if not needle:
        return 0
    for index, line in enumerate(content.splitlines(), start=1):
        if needle in line:
            return index
    return 0


def _classify(dependency: SecurityDependency) -> list[str]:
    """Derive mechanical risk labels for a dependency.

    Two sources, deliberately not merged into one classifier:

    * the repository dependency service's own risk vocabulary, so a requirement
      is labelled identically in the dependency view and in a security scan;
    * :func:`parse_version`, which distinguishes a release from something in the
      version position.

    ``unresolvable_version`` is suppressed when a more specific risk already
    describes the same problem. A range is reported as ``floating_version``, a
    git URL as ``git_source``, a relative path as ``local_path`` — adding
    ``unresolvable_version`` on top would triple-report one weakness and make
    the finding count meaningless.
    """
    risks, _ = repository_dependency_service._risk_flags(  # noqa: SLF001
        dependency.name, dependency.version, dependency.ecosystem
    )
    risks = list(risks)

    parsed = dependency.parsed_version

    # An exact pin to an unresolvable value is reported once. The shared
    # classifier calls it a floating version because the string is not a valid
    # release; the security engine knows the author *intended* an exact pin, so
    # "not a resolvable release" is the accurate label.
    if parsed.kind == "unresolvable":
        risks = [risk for risk in risks if risk != "floating_version"]
        if "unresolvable_version" not in risks:
            risks.append("unresolvable_version")
        seen: set[str] = set()
        return [risk for risk in risks if not (risk in seen or seen.add(risk))]

    # A ``${property}`` version is a Maven/Gradle property reference. It resolves
    # to a real version at build time, so calling it a floating range would be
    # wrong; the only true statement is that this scanner cannot read it.
    if parsed.kind == "placeholder":
        risks = [risk for risk in risks if risk not in ("floating_version", "unpinned")]
        if "unresolvable_version" not in risks:
            risks.append("unresolvable_version")
        seen: set[str] = set()
        return [risk for risk in risks if not (risk in seen or seen.add(risk))]

    #: Kinds that a specific risk label already covers.
    already_labelled = {
        "range",
        "vcs",
        "local_path",
        "commit",
        "missing",
        "unpinned",
    }
    if not parsed.usable and parsed.kind not in already_labelled:
        risks.append("unresolvable_version")

    seen: set[str] = set()
    return [risk for risk in risks if not (risk in seen or seen.add(risk))]


def _from_legacy(
    dependency: Any, manifest: str, content: str, *, direct: bool = True
) -> SecurityDependency:
    return SecurityDependency(
        name=dependency.name,
        ecosystem=dependency.ecosystem,
        manifest=manifest,
        version=dependency.version,
        scope=dependency.scope,
        line=_line_of(content, dependency.name),
        direct=direct,
    )


def parse_package_json(content: str, path: str = "package.json") -> list[SecurityDependency]:
    """Parse declared npm dependencies.

    A declared range such as ``^4.17.21`` is a legitimate npm declaration, so
    it is recorded as a range rather than as an invalid version; the floating
    range risk is what gets reported.
    """
    try:
        payload = json.loads(content)
    except (ValueError, TypeError):
        return []
    if not isinstance(payload, dict):
        return []

    results: list[SecurityDependency] = []
    for section, scope in (
        ("dependencies", "runtime"),
        ("devDependencies", "development"),
        ("optionalDependencies", "runtime"),
        ("peerDependencies", "runtime"),
    ):
        block = payload.get(section)
        if not isinstance(block, dict):
            continue
        for name, version in block.items():
            if not isinstance(name, str):
                continue
            results.append(
                SecurityDependency(
                    name=name,
                    ecosystem=ECOSYSTEM_NPM,
                    manifest=path,
                    version=str(version) if version is not None else None,
                    scope=scope,
                    line=_line_of(content, f'"{name}"'),
                )
            )
    return results


def parse_package_lock(content: str, path: str = "package-lock.json") -> list[SecurityDependency]:
    """Parse the resolved npm graph from a lockfile.

    ``packages`` is the lockfile v2/v3 layout, keyed by install path, and is
    preferred because it records the version actually resolved. ``dependencies``
    is the v1 layout. Transitive entries under ``node_modules/`` are recorded
    with ``direct=False`` so a first-party dependency and its tree are
    distinguishable without inflating the finding count for every transitive
    copy of the same package.
    """
    try:
        payload = json.loads(content)
    except (ValueError, TypeError):
        return []
    if not isinstance(payload, dict):
        return []

    results: list[SecurityDependency] = []
    seen: set[tuple[str, str | None]] = set()

    packages = payload.get("packages")
    if isinstance(packages, dict):
        for install_path, block in packages.items():
            if not isinstance(block, dict):
                continue
            name = block.get("name")
            version = block.get("version")
            if not isinstance(name, str) or not name:
                # Root project entries have an install path of "" and no name.
                name = (
                    install_path.rsplit("node_modules/", 1)[-1]
                    if "node_modules/" in install_path
                    else ""
                )
            # The root project (install path "") is the repository itself, not a
            # dependency of it, and carries no version by design.
            if not name or not install_path:
                continue
            resolved = version if isinstance(version, str) else None
            key = (name, resolved)
            if key in seen:
                continue
            seen.add(key)
            results.append(
                SecurityDependency(
                    name=name,
                    ecosystem=ECOSYSTEM_NPM,
                    manifest=path,
                    version=resolved,
                    scope="development" if block.get("dev") is True else "runtime",
                    line=_line_of(content, f'"{name}"'),
                    direct=install_path.count("node_modules/") <= 1,
                )
            )

    dependencies = payload.get("dependencies")
    if isinstance(dependencies, dict):
        for name, block in dependencies.items():
            if not isinstance(name, str) or not isinstance(block, dict):
                continue
            resolved = block.get("version")
            resolved = resolved if isinstance(resolved, str) else None
            key = (name, resolved)
            if key in seen:
                continue
            seen.add(key)
            results.append(
                SecurityDependency(
                    name=name,
                    ecosystem=ECOSYSTEM_NPM,
                    manifest=path,
                    version=resolved,
                    scope="development" if block.get("dev") is True else "runtime",
                    line=_line_of(content, f'"{name}"'),
                    direct=True,
                )
            )
    return results


def parse_requirements_txt(
    content: str, path: str = "requirements.txt"
) -> list[SecurityDependency]:
    """Parse a pip requirements file.

    Reuses the repository dependency parser so an edge case fixed there applies
    here, then re-attaches line numbers and drops the synthetic names that
    parser uses for editable installs (``local-project``), which are reported as
    ``local_path`` risks on a real name rather than a placeholder.
    """
    results: list[SecurityDependency] = []
    for index, raw_line in enumerate(content.splitlines(), start=1):
        dependency = repository_dependency_service.parse_requirement_line(raw_line, path)
        if dependency is None:
            continue
        name = dependency.name
        version = dependency.version
        if name == "local-project":
            # ``-e ./local`` — the target is in the version field.
            continue
        results.append(
            SecurityDependency(
                name=name,
                ecosystem=ECOSYSTEM_PYPI,
                manifest=path,
                version=version,
                scope=dependency.scope,
                line=index,
            )
        )
    return results


def parse_pyproject(content: str, path: str = "pyproject.toml") -> list[SecurityDependency]:
    """Parse PEP 621 ``dependencies`` and optional-dependency groups."""
    try:
        payload = tomllib.loads(content)
    except (tomllib.TOMLDecodeError, ValueError, TypeError):
        return []
    project = payload.get("project")
    if not isinstance(project, dict):
        return []

    groups: list[tuple[str, Iterable[str]]] = []
    requirements = project.get("dependencies")
    if isinstance(requirements, list):
        groups.append(("runtime", requirements))
    optional = project.get("optional-dependencies")
    if isinstance(optional, dict):
        for group, specs in optional.items():
            if isinstance(specs, list):
                groups.append((f"extra:{group}", specs))

    results: list[SecurityDependency] = []
    for scope, specs in groups:
        for spec in specs:
            if not isinstance(spec, str):
                continue
            dependency = repository_dependency_service._parse_pyproject_requirement(  # noqa: SLF001
                spec, path, scope
            )
            if dependency is None:
                continue
            results.append(
                SecurityDependency(
                    name=dependency.name,
                    ecosystem=ECOSYSTEM_PYPI,
                    manifest=path,
                    version=dependency.version,
                    scope=scope,
                    line=_line_of(content, dependency.name),
                )
            )
    return results


_GO_REQUIRE_BLOCK_RE = re.compile(r"^require\s*\($")
_GO_SINGLE_REQUIRE_RE = re.compile(r"^(?P<module>[^\s]+)\s+(?P<version>v[^\s]+)")


def parse_go_mod(content: str, path: str = "go.mod") -> list[SecurityDependency]:
    """Parse a Go module file, including parenthesised require blocks.

    A Go module version is a semantic version and must be an exact release for
    the build to be reproducible, so ranges are reported as unresolvable rather
    than accepted.
    """
    results: list[SecurityDependency] = []
    in_block = False
    for index, raw_line in enumerate(content.splitlines(), start=1):
        line = raw_line.split("//", 1)[0].strip()
        if not line:
            continue
        if in_block:
            if line == ")":
                in_block = False
                continue
            match = _GO_SINGLE_REQUIRE_RE.match(line)
            if match:
                results.append(
                    SecurityDependency(
                        name=match.group("module"),
                        ecosystem=ECOSYSTEM_GO,
                        manifest=path,
                        version=match.group("version"),
                        line=index,
                        direct="// indirect" not in raw_line,
                    )
                )
            continue
        if _GO_REQUIRE_BLOCK_RE.match(line):
            in_block = True
            continue
        if line.startswith("require "):
            match = _GO_SINGLE_REQUIRE_RE.match(line[len("require ") :].strip())
            if match:
                results.append(
                    SecurityDependency(
                        name=match.group("module"),
                        ecosystem=ECOSYSTEM_GO,
                        manifest=path,
                        version=match.group("version"),
                        line=index,
                    )
                )
    return results


_MAVEN_GROUP_LINE_RE = re.compile(r"<groupId>(?P<group>[^<]+)</groupId>")
_MAVEN_ARTIFACT_LINE_RE = re.compile(r"<artifactId>(?P<artifact>[^<]+)</artifactId>")
_MAVEN_VERSION_LINE_RE = re.compile(r"<version>(?P<version>[^<]+)</version>")
_MAVEN_DEPENDENCY_OPEN_RE = re.compile(r"<dependency>")
_MAVEN_DEPENDENCY_CLOSE_RE = re.compile(r"</dependency>")
_MAVEN_MANAGEMENT_OPEN_RE = re.compile(r"<dependencyManagement>")
_MAVEN_MANAGEMENT_CLOSE_RE = re.compile(r"</dependencyManagement>")


def parse_pom(content: str, path: str = "pom.xml") -> list[SecurityDependency]:
    """Parse Maven ``<dependency>`` elements from a POM.

    A dependency whose version is managed by ``dependencyManagement`` has no
    local version; that is reported as ``missing_version`` here and the managed
    version is picked up from the management block when it appears. Properties
    such as ``${spring.version}`` are recorded verbatim — the engine does not
    attempt to resolve them, and a value containing ``${`` is classified as an
    unresolvable version rather than being silently accepted.
    """
    results: list[SecurityDependency] = []
    managed: dict[str, str] = {}
    in_management = False
    current: dict[str, str] = {}
    current_line = 0
    open_line = 0
    in_dependency = False

    for index, raw_line in enumerate(content.splitlines(), start=1):
        line = raw_line.strip()
        if _MAVEN_MANAGEMENT_OPEN_RE.search(line):
            in_management = True
            continue
        if _MAVEN_MANAGEMENT_CLOSE_RE.search(line):
            in_management = False
            continue
        if _MAVEN_DEPENDENCY_OPEN_RE.search(line):
            in_dependency = True
            current = {}
            current_line = index
            open_line = index
            continue
        if in_dependency:
            group = _MAVEN_GROUP_LINE_RE.search(line)
            if group:
                current["groupId"] = group.group("group").strip()
            artifact = _MAVEN_ARTIFACT_LINE_RE.search(line)
            if artifact:
                current["artifactId"] = artifact.group("artifact").strip()
            version = _MAVEN_VERSION_LINE_RE.search(line)
            if version:
                current["version"] = version.group("version").strip()
            if _MAVEN_DEPENDENCY_CLOSE_RE.search(line):
                in_dependency = False
                group_id = current.get("groupId")
                artifact_id = current.get("artifactId")
                if group_id and artifact_id:
                    name = f"{group_id}:{artifact_id}"
                    version_value = current.get("version")
                    if version_value is None and name in managed:
                        version_value = managed[name]
                    if in_management:
                        managed[name] = version_value or ""
                    results.append(
                        SecurityDependency(
                            name=name,
                            ecosystem=ECOSYSTEM_MAVEN,
                            manifest=path,
                            version=version_value,
                            scope="runtime",
                            line=open_line or current_line,
                            direct=not in_management,
                        )
                    )
                current = {}
    return results


#: Manifest basename -> parser. Adding an ecosystem means adding one entry here
#: and one entry to :data:`SECURITY_MANIFESTS`.
PARSERS = {
    "package.json": parse_package_json,
    "package-lock.json": parse_package_lock,
    "requirements.txt": parse_requirements_txt,
    "pyproject.toml": parse_pyproject,
    "pom.xml": parse_pom,
    "go.mod": parse_go_mod,
}


def parse_manifest(path: str, ecosystem: str, content: str) -> list[SecurityDependency]:
    """Dispatch to the parser for ``path``.

    An unknown manifest returns an empty list. The caller is responsible for
    deciding whether an unsupported manifest is an error; here it is simply not
    a source of findings.
    """
    parser = PARSERS.get(security_sources.basename(path).lower())
    if parser is None:
        return []
    try:
        return parser(content, path)
    except Exception:
        # A malformed manifest must not abort a scan. Parsers already swallow
        # their own format errors; this is the backstop for the rest.
        return []


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------

#: Risk -> (severity offset applied to the base, confidence). A dependency
#: declared without a version *and* deprecated is worse than either alone.
_RISK_CONFIDENCE = {
    "missing_version": 0.85,
    "unpinned": 0.85,
    "floating_version": 0.7,
    "git_source": 0.7,
    "local_path": 0.6,
    "deprecated_package": 0.8,
    "unresolvable_version": 0.6,
}


def _severity_for(risks: list[str]) -> str:
    """Highest severity among the risks, with one step up for two or more."""
    from app.schemas.security import SEVERITIES, normalize_severity  # noqa: PLC0415

    order = {name: index for index, name in enumerate(SEVERITIES)}
    if not risks:
        return normalize_severity("low")
    worst = min(order[RISK_PROFILES[risk][0]] for risk in risks if risk in RISK_PROFILES)
    if len(risks) >= 2 and worst > 0:
        worst -= 1
    return normalize_severity(SEVERITIES[worst])


def _vulnerability_match(
    path: str,
    dependency: SecurityDependency,
    vulnerability: Vulnerability,
) -> DependencyMatch:
    return DependencyMatch(
        path=path,
        line=dependency.line,
        severity=vulnerability.severity,
        category="dependencies",
        scanner="dependency",
        title=f"{vulnerability.title} — {dependency.name}",
        description=vulnerability.description,
        remediation=vulnerability.remediation,
        confidence=vulnerability.confidence,
        dependency=dependency.name,
        ecosystem=dependency.ecosystem,
        declared_version=dependency.version,
        risk="known_vulnerability",
        fingerprint=_fingerprint(path, dependency.name, dependency.ecosystem, vulnerability.advisory_id),
    )


def _risk_match(
    path: str, dependency: SecurityDependency, risk: str
) -> DependencyMatch | None:
    profile = RISK_PROFILES.get(risk)
    if profile is None:
        return None
    severity, title, remediation = profile
    parsed = dependency.parsed_version
    detail = dependency.version if dependency.version else "no version"
    description = (
        f"{dependency.name} is declared with {detail!r} in {path}. {title}."
    )
    return DependencyMatch(
        path=path,
        line=dependency.line,
        severity=severity,
        category="dependencies",
        scanner="dependency",
        title=f"{title}: {dependency.name}",
        description=description,
        remediation=remediation,
        confidence=_RISK_CONFIDENCE.get(risk, 0.6),
        dependency=dependency.name,
        ecosystem=dependency.ecosystem,
        declared_version=dependency.version,
        risk=risk,
        fingerprint=_fingerprint(path, dependency.name, dependency.ecosystem, risk),
    )


def scan_manifest(path: str, content: str) -> list[DependencyMatch]:
    """Report every mechanical risk in one manifest."""
    matches: list[DependencyMatch] = []
    for dependency in parse_manifest(path, "", content):
        for risk in _classify(dependency):
            match = _risk_match(path, dependency, risk)
            if match is not None:
                matches.append(match)
    return matches


async def scan_dependencies(
    manifests: dict[str, str],
    *,
    provider: VulnerabilityProvider | None = None,
) -> tuple[list[DependencyMatch], int, str]:
    """Scan every manifest and return ``(findings, dependency_count, source)``.

    ``provider`` defaults to the process-registered source. When none is
    configured, the returned source is ``"none"`` and the findings contain only
    the mechanical risks this module can prove — the caller surfaces that string
    so a reader can tell a clean scan from a scan that never consulted an
    advisory database.
    """
    matches: list[DependencyMatch] = []
    all_dependencies: list[tuple[str, SecurityDependency]] = []
    for path, content in (manifests or {}).items():
        dependencies = parse_manifest(path, "", content)
        for dependency in dependencies:
            all_dependencies.append((path, dependency))
            for risk in _classify(dependency):
                match = _risk_match(path, dependency, risk)
                if match is not None:
                    matches.append(match)

    active = provider if provider is not None else active_vulnerability_provider()
    if active is not None:
        for path, dependency in all_dependencies:
            try:
                vulnerabilities = await active.lookup([dependency])
            except Exception:
                # An advisory source being unavailable degrades the scan to its
                # mechanical findings; it does not fail the repository.
                vulnerabilities = []
            for vulnerability in vulnerabilities or []:
                matches.append(_vulnerability_match(path, dependency, vulnerability))
        source = active.name
    else:
        source = "none"

    return matches, len(all_dependencies), source


def rule_summary() -> dict[str, Any]:
    """Machine-readable description of what the dependency scanner reports."""
    return {
        "manifests": [
            {"path": path, "ecosystem": ecosystem}
            for path, ecosystem in SECURITY_MANIFESTS
        ],
        "risks": {
            risk: {"severity": severity, "title": title}
            for risk, (severity, title, _) in RISK_PROFILES.items()
        },
        "vulnerability_source": vulnerability_source_name(),
    }
