"""Dependency inspection across common ecosystem manifests.

The parsers in this module are pure functions over manifest text: given a
string they return dependency records, with no I/O and no network. The
orchestrator is responsible for fetching manifest contents; keeping parsing
separate means manifest formats can be unit-tested exhaustively without a
provider token or a live repository.

Supported manifests
-------------------
======================  ==========  =========================================
Path                    Ecosystem   Parsed sections
======================  ==========  =========================================
``package.json``         npm         ``dependencies``, ``devDependencies``
``requirements.txt``     pypi        PEP 508 requirement lines
``pyproject.toml``       pypi        PEP 621 ``dependencies`` + extras, Poetry
``go.mod``               go          ``require`` directives, including blocks
======================  ==========  =========================================

Risk labels
-----------
Each label is a mechanical property of the recorded version string:

``missing_version``    the manifest lists the package with no version at all
``unpinned``           the version is a wildcard (``*``)
``floating_version``   the version is a range rather than an exact pin
``git_source``         the version points at a VCS or URL source
``local_path``         the version points at a local filesystem path
``deprecated_package`` the package name appears in :data:`DEPRECATED_PACKAGES`

:data:`DEPRECATED_PACKAGES` is a *static, reviewable project policy list* of
packages that their upstream registries mark as deprecated. It is deliberately
not a vulnerability database and carries no claim beyond "the registry says
this is deprecated"; extend it through normal code review.
"""

from __future__ import annotations

import re
import tomllib
from typing import Iterable

from app.schemas.repository_intelligence import (
    Dependency,
    DependencyManifest,
    DependencyReport,
)

ECOSYSTEM_NPM = "npm"
ECOSYSTEM_PYPI = "pypi"
ECOSYSTEM_GO = "go"

#: Manifest paths probed, in priority order. Missing manifests are reported with
#: ``found=False`` rather than being silently omitted.
CANDIDATE_MANIFESTS: tuple[tuple[str, str], ...] = (
    ("package.json", ECOSYSTEM_NPM),
    ("requirements.txt", ECOSYSTEM_PYPI),
    ("pyproject.toml", ECOSYSTEM_PYPI),
    ("go.mod", ECOSYSTEM_GO),
)

#: Packages upstream registries flag as deprecated. Static policy, see module docstring.
DEPRECATED_PACKAGES: frozenset[str] = frozenset(
    {
        # npm
        "request",
        "node-uuid",
        "left-pad",
        "event-stream",
        "flatmap-stream",
        # pypi
        "pycrypto",
        "nose",
        "imp",
        "sklearn",
        "beautifulsoup",
        # go
        "github.com/gopkg.in/yaml.v2",
    }
)

_EXACT_PIN_RE = re.compile(r"^\d+(?:\.\d+)*(?:[-+][0-9A-Za-z.\-+]+)?$")
_VERSION_OPERATOR_RE = re.compile(r"(===|==|>=|<=|~=|!=|>|<)\s*(.+)$")
_GO_REQUIRE_LINE_RE = re.compile(
    r"^(?P<module>[^\s]+)\s+(?P<version>v[^\s]+)(?P<rest>.*)$"
)
_GO_DIRECTIVE_RE = re.compile(r"^\s*(?P<directive>require|exclude|replace|retract)\b")

#: ``==``/``===`` (pip) and a bare ``=`` (npm) declare an *exact* version, which
#: is a pin. Everything here constrains a range and is therefore not a pin.
_PIN_OPERATOR_RE = re.compile(r"^=+\s*")
_RANGE_OPERATORS = ("<=", ">=", "~=", "!=", ">", "<", "^", "~", "||")
_LEADING_V_RE = re.compile(r"^v")


def _strip_comment(line: str) -> str:
    """Remove a trailing ``#`` comment that is not inside a URL fragment."""
    index = line.find("#")
    if index == -1:
        return line
    prefix = line[:index]
    if "://" in prefix and prefix.rfind("://") > prefix.rfind(" "):
        return line
    return prefix


def _normalize_pypi_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name.strip()).lower()


def _classify_version(version: str | None) -> tuple[list[str], bool]:
    """Return ``(risks, pinned)`` for a raw version string.

    ``version`` of ``None`` or an empty string means the manifest recorded the
    package without any version constraint at all.
    """
    if version is None or not str(version).strip():
        return ["missing_version"], False

    raw = str(version).strip()

    if raw == "*":
        return ["unpinned"], False

    lowered = raw.lower()
    if lowered.startswith("git+") or lowered.startswith("github:") or lowered.endswith(".git"):
        return ["git_source"], False
    if "://" in raw:
        return ["git_source"], False
    if raw.startswith(("file:", "./", "../", "/", "~/")) or raw in (".", ".."):
        return ["local_path"], False

    if lowered in ("latest", "next", "canary", "nightly", "edge", "master", "main"):
        return ["floating_version"], False

    # A range operator means the declared version is not reproducible, so it is
    # never a pin. Checked before stripping, otherwise ``^1.2.3`` would reduce to
    # ``1.2.3`` and be mistaken for an exact pin.
    if any(operator in raw for operator in _RANGE_OPERATORS):
        return ["floating_version"], False

    # ``==0.1.2`` (pip), ``===0.1.2`` and ``=0.1.2`` (npm) all pin exactly.
    if "=" in raw:
        candidate = _PIN_OPERATOR_RE.sub("", raw).strip()
        return ([], True) if _EXACT_PIN_RE.match(candidate) else (["floating_version"], False)

    # A leading "v" is Go's version prefix, not a constraint.
    candidate = _LEADING_V_RE.sub("", raw)
    if _EXACT_PIN_RE.match(candidate):
        return [], True
    return ["floating_version"], False


def _risk_flags(name: str, version: str | None, ecosystem: str) -> tuple[list[str], bool]:
    risks, pinned = _classify_version(version)
    key = _normalize_pypi_name(name) if ecosystem == ECOSYSTEM_PYPI else name
    if key in DEPRECATED_PACKAGES or name in DEPRECATED_PACKAGES:
        if "deprecated_package" not in risks:
            risks.append("deprecated_package")
    return risks, pinned


def _make_dependency(
    name: str,
    version: str | None,
    *,
    ecosystem: str,
    manifest: str,
    scope: str = "runtime",
) -> Dependency:
    risks, pinned = _risk_flags(name, version, ecosystem)
    return Dependency(
        name=name,
        version=version,
        ecosystem=ecosystem,
        manifest=manifest,
        scope=scope,
        risks=risks,
        pinned=pinned,
    )


# ---------------------------------------------------------------------------
# npm: package.json
# ---------------------------------------------------------------------------


def parse_package_json(content: str, path: str = "package.json") -> list[Dependency]:
    """Parse npm ``dependencies`` and ``devDependencies`` sections.

    Malformed JSON yields an empty list rather than raising: a broken manifest
    should surface as "no dependencies found", not a 500 for the whole page.
    """
    import json

    try:
        payload = json.loads(content)
    except (ValueError, TypeError):
        return []
    if not isinstance(payload, dict):
        return []

    dependencies: list[Dependency] = []
    for section, scope in (("dependencies", "runtime"), ("devDependencies", "development")):
        block = payload.get(section)
        if not isinstance(block, dict):
            continue
        for name, version in block.items():
            if not isinstance(name, str):
                continue
            dependencies.append(
                _make_dependency(
                    name,
                    str(version) if version is not None else None,
                    ecosystem=ECOSYSTEM_NPM,
                    manifest=path,
                    scope=scope,
                )
            )
    return dependencies


# ---------------------------------------------------------------------------
# pypi: requirements.txt
# ---------------------------------------------------------------------------

_EDITABLE_RE = re.compile(r"^-(?:e|\-editable)\s+(?P<target>.+)$")
_INCLUDE_RE = re.compile(r"^-[rc]\s+")


def parse_requirement_line(line: str, manifest: str) -> Dependency | None:
    """Parse one PEP 508 requirement line into a dependency, or None to skip.

    ``None`` means "not a dependency": blank lines, comments, ``-r``/``-c``
    includes, options and malformed entries.
    """
    stripped = _strip_comment(line).strip()
    if not stripped:
        return None
    if _INCLUDE_RE.match(stripped):
        return None
    if stripped.startswith("-"):
        editable = _EDITABLE_RE.match(stripped)
        if editable:
            return _make_dependency(
                "local-project",
                editable.group("target").strip(),
                ecosystem=ECOSYSTEM_PYPI,
                manifest=manifest,
            )
        return None

    # Environment markers do not change the declared dependency.
    spec = stripped.split(";", 1)[0].strip()
    if not spec:
        return None

    # PEP 508 direct reference: "name @ https://..." / "name @ git+https://..."
    if " @ " in spec:
        name, _, reference = spec.partition(" @ ")
        return _make_dependency(
            name.strip(),
            reference.strip(),
            ecosystem=ECOSYSTEM_PYPI,
            manifest=manifest,
        )

    # Extras: "name[extra]>=1.0"
    name_part, bracket, extras = spec.partition("[")
    if bracket:
        del extras
        spec = f"{name_part}{spec.partition(']')[2]}"

    match = _VERSION_OPERATOR_RE.search(spec)
    if match:
        name = spec[: match.start()].strip()
        version = f"{match.group(1)}{match.group(2).strip()}"
    else:
        name = spec.strip()
        version = None

    if not name:
        return None
    return _make_dependency(name, version, ecosystem=ECOSYSTEM_PYPI, manifest=manifest)


def parse_requirements_txt(content: str, path: str = "requirements.txt") -> list[Dependency]:
    """Parse every requirement line in a pip requirements file."""
    dependencies: list[Dependency] = []
    for raw_line in content.splitlines():
        dependency = parse_requirement_line(raw_line, path)
        if dependency is not None:
            dependencies.append(dependency)
    return dependencies


# ---------------------------------------------------------------------------
# pypi: pyproject.toml
# ---------------------------------------------------------------------------


def _parse_pyproject_requirement(spec: str, manifest: str, scope: str) -> Dependency | None:
    """Parse one pyproject requirement, tagging it with its declaring scope."""
    dependency = parse_requirement_line(spec, manifest)
    if dependency is None:
        return None
    return dependency.model_copy(update={"scope": scope})


def parse_pyproject(content: str, path: str = "pyproject.toml") -> list[Dependency]:
    """Parse PEP 621 and Poetry dependency declarations.

    Only dependency declarations are read; build-system and tool configuration
    are ignored. Invalid TOML yields an empty list for the same reason as
    invalid JSON in :func:`parse_package_json`.
    """
    try:
        payload = tomllib.loads(content)
    except (tomllib.TOMLDecodeError, TypeError, ValueError):
        return []
    if not isinstance(payload, dict):
        return []

    dependencies: list[Dependency] = []

    project = payload.get("project")
    if isinstance(project, dict):
        for spec in project.get("dependencies") or []:
            if isinstance(spec, str):
                parsed = _parse_pyproject_requirement(spec, path, "runtime")
                if parsed is not None:
                    dependencies.append(parsed)
        optional = project.get("optional-dependencies")
        if isinstance(optional, dict):
            for group, specs in optional.items():
                if not isinstance(specs, list):
                    continue
                scope = f"extra:{group}"
                for spec in specs:
                    if isinstance(spec, str):
                        parsed = _parse_pyproject_requirement(spec, path, scope)
                        if parsed is not None:
                            dependencies.append(parsed)

    tool = payload.get("tool")
    if isinstance(tool, dict):
        poetry = tool.get("poetry")
        if isinstance(poetry, dict):
            for section, scope in (
                ("dependencies", "runtime"),
                ("dev-dependencies", "development"),
            ):
                block = poetry.get(section)
                if not isinstance(block, dict):
                    continue
                for name, constraint in block.items():
                    if str(name).lower() == "python":
                        continue
                    dependencies.append(
                        _make_dependency(
                            str(name),
                            str(constraint) if constraint is not None else None,
                            ecosystem=ECOSYSTEM_PYPI,
                            manifest=path,
                            scope=scope,
                        )
                    )
    return dependencies


# ---------------------------------------------------------------------------
# go: go.mod
# ---------------------------------------------------------------------------


def parse_go_mod(content: str, path: str = "go.mod") -> list[Dependency]:
    """Parse ``require`` directives, both single-line and in ``()`` blocks.

    ``exclude``, ``replace`` and ``retract`` directives are ignored, and
    ``// indirect`` comments move the dependency to the ``indirect`` scope.
    """
    dependencies: list[Dependency] = []
    in_require_block = False

    for raw_line in content.splitlines():
        # The "// indirect" marker is meaningful here, so it is read before the
        # comment is stripped off the require line.
        indirect = "//" in raw_line and "indirect" in raw_line.split("//", 1)[1].lower()
        line = raw_line.split("//", 1)[0].strip()
        if not line:
            continue

        directive = _GO_DIRECTIVE_RE.match(line)
        if directive:
            in_require_block = directive.group("directive") == "require"
            remainder = line[directive.end() :].strip()
            if in_require_block and remainder.startswith("("):
                in_require_block = True
                continue
            if in_require_block and remainder:
                parsed = _parse_go_require(remainder, path, indirect=indirect)
                if parsed is not None:
                    dependencies.append(parsed)
            continue

        if in_require_block:
            if line == ")":
                in_require_block = False
                continue
            parsed = _parse_go_require(line, path, indirect=indirect)
            if parsed is not None:
                dependencies.append(parsed)

    return dependencies


def _parse_go_require(entry: str, manifest: str, *, indirect: bool = False) -> Dependency | None:
    body = entry.split("//", 1)[0].strip()
    match = _GO_REQUIRE_LINE_RE.match(body)
    if not match:
        return None
    return _make_dependency(
        match.group("module"),
        match.group("version"),
        ecosystem=ECOSYSTEM_GO,
        manifest=manifest,
        scope="indirect" if indirect else "runtime",
    )


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------

#: Manifest path to parser, for the two pypi formats.
_PYPI_PARSERS = {
    "requirements.txt": parse_requirements_txt,
    "pyproject.toml": parse_pyproject,
}


def parse_manifest(path: str, ecosystem: str, content: str) -> list[Dependency]:
    """Dispatch a manifest to the right parser based on path and ecosystem."""
    if ecosystem == ECOSYSTEM_PYPI:
        return _PYPI_PARSERS.get(path, parse_requirements_txt)(content, path)
    if ecosystem == ECOSYSTEM_NPM:
        return parse_package_json(content, path)
    if ecosystem == ECOSYSTEM_GO:
        return parse_go_mod(content, path)
    return []


def build_dependency_report(
    contents: dict[str, str] | None,
    *,
    owner: str = "",
    repository: str = "",
    cached: bool = False,
    candidates: Iterable[tuple[str, str]] = CANDIDATE_MANIFESTS,
) -> DependencyReport:
    """Assemble the inspector report from fetched manifest contents.

    ``contents`` maps manifest path to raw text. Every candidate manifest is
    reported, so a repository that ships no ``go.mod`` is visibly distinct from
    a repository whose ``go.mod`` exists but parsed empty.
    """
    contents = contents or {}
    manifests: list[DependencyManifest] = []
    dependencies: list[Dependency] = []

    for path, ecosystem in candidates:
        content = contents.get(path)
        if content is None:
            manifests.append(
                DependencyManifest(
                    path=path,
                    ecosystem=ecosystem,
                    found=False,
                    reason="Manifest not found in this repository.",
                )
            )
            continue

        parsed = parse_manifest(path, ecosystem, content)
        dependencies.extend(parsed)
        manifests.append(
            DependencyManifest(
                path=path,
                ecosystem=ecosystem,
                found=True,
                reason=(
                    f"Parsed {len(parsed)} dependencies."
                    if parsed
                    else "Manifest found but declared no dependencies."
                ),
            )
        )

    dependencies.sort(key=lambda item: (item.ecosystem, item.manifest, item.name))
    ecosystems = sorted({item.ecosystem for item in dependencies})
    flagged = [item for item in dependencies if item.risks]

    return DependencyReport(
        owner=owner,
        repository=repository,
        manifests=manifests,
        dependencies=dependencies,
        total=len(dependencies),
        direct_count=len(dependencies),
        flagged_count=len(flagged),
        ecosystems=ecosystems,
        cached=cached,
    )


def summarize_risks(report: DependencyReport) -> dict[str, int]:
    """Count dependencies per risk label for charting."""
    counts: dict[str, int] = {}
    for dependency in report.dependencies:
        for risk in dependency.risks:
            counts[risk] = counts.get(risk, 0) + 1
    return counts
