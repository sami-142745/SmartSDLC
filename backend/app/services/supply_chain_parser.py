"""Deterministic parsing for the Dependency & Supply Chain engine.

Responsibilities
----------------
1. Decide which files are dependency **manifests** (what a project asks for) and
   which are **lockfiles** (what a resolver chose). The second is the fact that
   makes a build reproducible, and the existing dependency inspector does not
   model it.
2. Reuse the dependency inspector's parsers for the inventory, so a requirement
   is labelled with the same risk vocabulary everywhere it appears.
3. Read *declared* licence expressions out of manifests and lockfiles.

Honesty boundaries
------------------
* Only a licence the repository actually declares is reported. Nothing is
  inferred from a package name, and a missing licence stays missing.
* The project may ship its own licence (``LICENSE``) which tells us what the
  project is, not what its dependencies are. Those are reported separately and
  never used to fill in a dependency's licence.
* A lockfile without licence fields yields an unknown-licence inventory. That is
  a true statement about the repository, not a defect of this parser, and the
  analysis layer reports it as such instead of guessing.
"""

from __future__ import annotations

import json
import re
import tomllib
from typing import Any, Iterable

from app.schemas.supply_chain import (
    LIC_PERMISSIVE,
    LIC_PROPRIETARY,
    LIC_PUBLIC_DOMAIN,
    LIC_STRONG_COPYLEFT,
    LIC_UNKNOWN,
    LIC_WEAK_COPYLEFT,
    ORIGIN_DIRECT,
    ORIGIN_TRANSITIVE,
    ORIGIN_UNKNOWN,
    ROLE_LOCKFILE,
    ROLE_MANIFEST,
    LicenseCategory,
    SupplyChainDependency,
    SupplyChainManifest,
)
from app.services import repository_dependency_service, repository_paths, security_sources
from app.services.repository_dependency_service import ECOSYSTEM_GO, ECOSYSTEM_NPM, ECOSYSTEM_PYPI
from app.services.security_dependency_scanner import parse_manifest as parse_security_manifest

#: Files that declare direct dependencies, with the ecosystem they belong to.
#:
#: Deliberately the same four the dependency inspector probes, so the two views
#: describe the same manifests. Adding a manifest here without adding it to
#: ``CANDIDATE_MANIFESTS`` would make this report disagree with the inspector.
MANIFEST_FILES: tuple[tuple[str, str], ...] = (
    ("package.json", ECOSYSTEM_NPM),
    ("requirements.txt", ECOSYSTEM_PYPI),
    ("pyproject.toml", ECOSYSTEM_PYPI),
    ("go.mod", ECOSYSTEM_GO),
    ("pom.xml", "maven"),
)

#: Files that record a resolved dependency graph.
#:
#: ``pom.xml`` is excluded because its ``<dependencyManagement>`` block is
#: version management, not a lockfile, and the project may legitimately pin
#: versions there without a resolver ever running.
LOCKFILE_FILES: tuple[tuple[str, str], ...] = (
    ("package-lock.json", ECOSYSTEM_NPM),
    ("npm-shrinkwrap.json", ECOSYSTEM_NPM),
    ("yarn.lock", ECOSYSTEM_NPM),
    ("pnpm-lock.yaml", ECOSYSTEM_NPM),
    ("poetry.lock", ECOSYSTEM_PYPI),
    ("uv.lock", ECOSYSTEM_PYPI),
    ("Pipfile.lock", ECOSYSTEM_PYPI),
    ("go.sum", ECOSYSTEM_GO),
    ("Cargo.lock", "cargo"),
    ("composer.lock", "packagist"),
)

MANIFEST_BASENAMES = frozenset(path for path, _ in MANIFEST_FILES)
LOCKFILE_BASENAMES = frozenset(path for path, _ in LOCKFILE_FILES)
DEPENDENCY_BASENAMES = MANIFEST_BASENAMES | LOCKFILE_BASENAMES

#: Files that license the *project*. Read for context only.
PROJECT_LICENSE_FILES: tuple[str, ...] = (
    "LICENSE",
    "LICENSE.md",
    "LICENSE.txt",
    "LICENCE",
    "LICENCE.md",
    "LICENCE.txt",
    "COPYING",
    "COPYING.md",
)

# ---------------------------------------------------------------------------
# Licence classification
# ---------------------------------------------------------------------------

#: Exact SPDX expressions, lower-cased, grouped by posture.
_PERMISSIVE_EXPRESSIONS = frozenset(
    {
        "mit",
        "x11",
        "bsd-2-clause",
        "bsd-3-clause",
        "bsd-3-clause-clear",
        "bsd-4-clause",
        "0bsd",
        "isc",
        "apache-2.0",
        "zlib",
        "artistic-2.0",
        "python-2.0",
        "psf-2.0",
        "curl",
        "unlicense",
        "wtfpl",
        "mit-0",
        "blueoak-1.0.0",
    }
)

_PUBLIC_DOMAIN_EXPRESSIONS = frozenset(
    {
        "cc0-1.0",
        "cc0",
        "public-domain",
        "publicdomain",
        "pddl-1.0",
    }
)

_WEAK_COPYLEFT_EXPRESSIONS = frozenset(
    {
        "mpl-2.0",
        "mpl-1.1",
        "lgpl-2.0",
        "lgpl-2.1",
        "lgpl-3.0",
        "lgpl-2.0-only",
        "lgpl-2.1-only",
        "lgpl-3.0-only",
        "lgpl-2.0-or-later",
        "lgpl-2.1-or-later",
        "lgpl-3.0-or-later",
        "epl-1.0",
        "epl-2.0",
        "cddl-1.0",
        "cddl-1.1",
        "eupl-1.1",
        "eupl-1.2",
        "cpl-1.0",
        "ms-rl",
        "artistic-1.0",
    }
)

_STRONG_COPYLEFT_EXPRESSIONS = frozenset(
    {
        "gpl-1.0",
        "gpl-2.0",
        "gpl-3.0",
        "gpl-1.0-only",
        "gpl-2.0-only",
        "gpl-3.0-only",
        "gpl-1.0-or-later",
        "gpl-2.0-or-later",
        "gpl-3.0-or-later",
        "agpl-1.0",
        "agpl-3.0",
        "agpl-1.0-only",
        "agpl-3.0-only",
        "agpl-1.0-or-later",
        "agpl-3.0-or-later",
        "osl-3.0",
        "qpl-1.0",
        "sspl-1.0",
    }
)

#: SPDX requires the suffix, but manifests in the wild write bare ``GPL-3.0``.
_GPL_PREFIXES = ("gpl-", "agpl-", "lgpl-", "gfdl-")

#: Text a repository writes instead of a licence, and what it means.
_PROPRIETARY_MARKERS = frozenset(
    {
        "unlicensed",
        "proprietary",
        "commercial",
        "see license in license",
        "see licence in licence",
        "unlicensed-proprietary",
    }
)

#: A bare ``SEE LICENSE IN <file>`` means the licence is elsewhere in the repo.
_SEE_LICENSE_RE = re.compile(r"^see\s+licen[sc]e\s+in\s+\S+", re.IGNORECASE)

#: SPDX ``WITH`` exceptions do not change the posture of the base licence.
_WITH_EXCEPTION_RE = re.compile(r"\s+with\s+[\w.\-]+$", re.IGNORECASE)

#: npm's non-SPDX placeholder and a few common typos resolve to "not declared".
_UNRESOLVED_TOKENS = frozenset(
    {
        "see license",
        "see licence",
        "license",
        "licence",
        "none",
        "null",
        "n/a",
        "na",
        "unknown",
        "unspecified",
        "custom",
        "free",
        "freeware",
        "shareware",
        "public",
    }
)

_MAX_LICENSE_LENGTH = 120


def _normalise_expression(raw: str | None) -> str | None:
    """Reduce a declared licence string to a comparable form.

    Returns ``None`` when the repository declared nothing usable, so the caller
    can distinguish "no licence" from "a licence we cannot classify".
    """
    if not isinstance(raw, str):
        return None
    text = raw.strip().strip('"').strip("'")
    if not text:
        return None
    # A JSON blob or a sentence is not a licence expression.
    if len(text) > _MAX_LICENSE_LENGTH or text.startswith(("{", "[")):
        return None
    collapsed = re.sub(r"\s+", " ", text)
    if not collapsed:
        return None
    return collapsed


def classify_license(expression: str | None) -> LicenseCategory:
    """Classify a declared licence expression into a coarse posture.

    Unknown means "not classifiable from what the repository declared". It is
    never a guess: an unrecognised SPDX id is reported as unknown so a reader can
    look it up, rather than being folded into a permissive bucket that would
    understate the risk.
    """
    normalised = _normalise_expression(expression)
    if normalised is None:
        return LIC_UNKNOWN

    if _SEE_LICENSE_RE.match(normalised):
        return LIC_PROPRIETARY
    if normalised.lower() in _PROPRIETARY_MARKERS:
        return LIC_PROPRIETARY

    text = _WITH_EXCEPTION_RE.sub("", normalised)
    lowered = text.lower().strip()

    if lowered in _PUBLIC_DOMAIN_EXPRESSIONS:
        return LIC_PUBLIC_DOMAIN
    if lowered in _PERMISSIVE_EXPRESSIONS:
        return LIC_PERMISSIVE
    if lowered in _WEAK_COPYLEFT_EXPRESSIONS:
        return LIC_WEAK_COPYLEFT
    if lowered in _STRONG_COPYLEFT_EXPRESSIONS:
        return LIC_STRONG_COPYLEFT

    if lowered in _UNRESOLVED_TOKENS:
        return LIC_UNKNOWN
    if lowered.startswith(_GPL_PREFIXES):
        return LIC_STRONG_COPYLEFT
    # SPDX writes this "LicenseRef-", with no hyphen inside the word.
    if lowered.startswith(("licenseref-", "license-ref-")):
        return LIC_PROPRIETARY

    # ``MIT OR Apache-2.0`` and friends: classify on the most restrictive term,
    # because a user choosing between terms can only rely on the weakest grant.
    if " or " in lowered:
        parts = [part.strip() for part in lowered.split(" or ") if part.strip()]
        categories = {classify_license(part) for part in parts}
        if LIC_STRONG_COPYLEFT in categories:
            return LIC_STRONG_COPYLEFT
        if LIC_PROPRIETARY in categories:
            return LIC_PROPRIETARY
        if LIC_WEAK_COPYLEFT in categories:
            return LIC_WEAK_COPYLEFT
        if LIC_PUBLIC_DOMAIN in categories:
            return LIC_PUBLIC_DOMAIN
        if LIC_PERMISSIVE in categories:
            return LIC_PERMISSIVE
        return LIC_UNKNOWN

    return LIC_UNKNOWN


def project_license_category(expression: str | None) -> LicenseCategory:
    """Classify the repository's *own* licence.

    A project's licence is a distribution condition for the repository as a
    whole, which is a different question from what its dependencies allow. It is
    reported separately and never used to fill a dependency's licence.
    """
    return classify_license(expression)


# ---------------------------------------------------------------------------
# Manifest classification
# ---------------------------------------------------------------------------


def classify_path(path: str) -> tuple[str, str] | None:
    """Return ``(ecosystem, role)`` for a dependency-bearing file, or None.

    A basename match anywhere in the tree is accepted, so ``services/api/go.mod``
    is found. ``repository_paths`` already excludes vendored and build
    directories, so a checked-in ``vendor`` tree is not mistaken for the
    project's own dependency set.
    """
    basename = security_sources.basename(path).lower()
    for candidate, ecosystem in MANIFEST_FILES:
        if basename == candidate.lower():
            return ecosystem, ROLE_MANIFEST
    for candidate, ecosystem in LOCKFILE_FILES:
        if basename == candidate.lower():
            return ecosystem, ROLE_LOCKFILE
    return None


def select_targets(entries: Iterable[dict[str, Any]]) -> list[str]:
    """Pick dependency-bearing paths from a repository tree.

    A basename match anywhere in the tree is accepted, so ``services/api/go.mod``
    is found. ``repository_paths`` already excludes vendored and build
    directories, so a checked-in ``vendor`` tree or a ``node_modules`` snapshot
    is not mistaken for the project's own dependency set.
    """
    seen: set[str] = set()
    selected: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        raw = entry.get("path")
        if not isinstance(raw, str) or not raw:
            continue
        if entry.get("type") not in (None, "blob", "file"):
            continue
        path = repository_paths.normalise_path(raw)
        if not path or path in seen:
            continue
        if repository_paths.is_ignored_path(path):
            continue
        if classify_path(path) is None:
            continue
        seen.add(path)
        selected.append(path)
    return sorted(selected)


# ---------------------------------------------------------------------------
# Licence extraction
# ---------------------------------------------------------------------------


def _json_load(content: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(content)
    except (ValueError, TypeError):
        return None
    return payload if isinstance(payload, dict) else None


def _package_json_licenses(content: str) -> dict[str, str]:
    """npm ``license``/``licenses`` fields, keyed by package name.

    npm allows ``licenses`` to be an array of objects, so both shapes are
    handled. A package whose ``license`` is absent contributes no entry, which
    is what keeps "undeclared" distinguishable from "unknown".
    """
    payload = _json_load(content)
    if payload is None:
        return {}
    declared: dict[str, str] = {}
    for section in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies"):
        block = payload.get(section)
        if not isinstance(block, dict):
            continue
        for name, spec in block.items():
            if not isinstance(name, str) or not isinstance(spec, dict):
                continue
            value = _normalise_expression(spec.get("license"))
            if value is not None and name not in declared:
                declared[name] = value
    return declared


def _package_lock_licenses(content: str) -> dict[str, str]:
    """npm lockfile ``packages``/``dependencies`` licence fields."""
    payload = _json_load(content)
    if payload is None:
        return {}
    declared: dict[str, str] = {}

    packages = payload.get("packages")
    if isinstance(packages, dict):
        for key, spec in packages.items():
            if not isinstance(key, str) or not isinstance(spec, dict):
                continue
            # Keys look like ``node_modules/react`` or ``packages/a``.
            name = key.rsplit("node_modules/", 1)[-1] if "node_modules/" in key else key
            if not name or name == "":
                continue
            value = _normalise_expression(spec.get("license"))
            if value is not None and name not in declared:
                declared[name] = value
    dependencies = payload.get("dependencies")
    if isinstance(dependencies, dict):
        for name, spec in dependencies.items():
            if not isinstance(name, str) or not isinstance(spec, dict):
                continue
            value = _normalise_expression(spec.get("license"))
            if value is not None and name not in declared:
                declared[name] = value
    return declared


_PYPROJECT_LICENSE_RE = re.compile(r"^\s*license\s*=", re.IGNORECASE)
_POM_LICENSE_RE = re.compile(r"<licenses?>.*?</licenses?>", re.IGNORECASE | re.DOTALL)
_POM_LICENSE_NAME_RE = re.compile(r"<name>\s*(?P<value>[^<]+?)\s*</name>", re.IGNORECASE)
_GO_MODULE_RE = re.compile(r"^module\s+(?P<value>\S+)", re.MULTILINE)


def _pyproject_license(content: str) -> str | None:
    """The ``[project] license`` string.

    Both the SPDX-string form (``license = "MIT"``) and the legacy table form
    (``license = {text = "MIT"}``) appear in the wild; the table form is read by
    taking the text field when it is present on the same line.
    """
    for line in content.splitlines():
        match = _PYPROJECT_LICENSE_RE.match(line)
        if not match:
            continue
        remainder = line[match.end() :]
        inner = re.search(r"text\s*=\s*['\"](?P<value>[^'\"]+)['\"]", remainder)
        if inner:
            return _normalise_expression(inner.group("value"))
        stripped = remainder.strip().rstrip(",")
        if stripped.startswith(("{", "[")):
            continue
        value = stripped.strip('"').strip("'")
        return _normalise_expression(value)
    return None


def _pom_license(content: str) -> str | None:
    block = _POM_LICENSE_RE.search(content)
    if block is None:
        return None
    name = _POM_LICENSE_NAME_RE.search(block.group(0))
    if name is None:
        return None
    return _normalise_expression(name.group("value"))


def extract_licenses(path: str, content: str) -> dict[str, str]:
    """Declared licence expressions in one file, keyed by package name.

    A project-level ``license``/``licenses`` field describes the repository
    itself, so it is deliberately **not** returned here. Callers read it with
    :func:`project_license_expression` instead. Folding it into the dependency
    map would report the project's own licence as if a dependency declared it.
    """
    basename = security_sources.basename(path).lower()
    if basename == "package.json":
        return _package_json_licenses(content)
    if basename in {"package-lock.json", "npm-shrinkwrap.json"}:
        return _package_lock_licenses(content)
    return {}


def project_license_expression(path: str, content: str) -> str | None:
    """The licence a project declares for itself, from a manifest or LICENSE file.

    A ``LICENSE`` file is read as a permissive-style signal only when it
    literally names a known expression; free-form licence text is not guessed
    at, because mistaking custom terms for MIT would understate the condition.
    """
    basename = security_sources.basename(path).lower()
    if basename == "package.json":
        payload = _json_load(content)
        if payload is None:
            return None
        value = _normalise_expression(payload.get("license"))
        if value is not None:
            return value
        licenses = payload.get("licenses")
        if isinstance(licenses, list) and licenses:
            first = licenses[0]
            if isinstance(first, str):
                return _normalise_expression(first)
            if isinstance(first, dict):
                return _normalise_expression(first.get("type"))
        return None
    if basename == "pyproject.toml":
        return _pyproject_license(content)
    if basename == "pom.xml":
        return _pom_license(content)
    if basename in {"license", "license.md", "licence", "licence.md", "copying"}:
        return _license_file_expression(content)
    return None


#: Distinctive markers that let a free-form LICENSE file be identified without
#: being read as a whole. Each entry needs a marker specific enough that it
#: cannot appear in a different licence.
#:
#: A clause such as "redistribution and use in source and binary forms" is
#: deliberately absent: it is shared by the 2-, 3- and 4-clause BSD texts and
#: by MIT, so matching it would mean picking a licence the repository did not
#: name. Such a file stays unknown.
_LICENSE_FILE_MARKERS: tuple[tuple[str, str], ...] = (
    ("mozilla public license", "MPL-2.0"),
    ("gnu affero general public license", "AGPL-3.0"),
    ("gnu lesser general public license", "LGPL-2.1-or-later"),
    ("gnu general public license", "GPL-3.0"),
    ("cc0 1.0 universal", "CC0-1.0"),
    ("creative commons zero", "CC0-1.0"),
    ("creative commons attribution", "CC-BY-4.0"),
    ("apache license", "Apache-2.0"),
    ("mit license", "MIT"),
    ("permission is hereby granted, free of charge", "MIT"),
    ("all rights reserved", "Proprietary"),
)


def _license_file_expression(content: str) -> str | None:
    """Best-effort SPDX id for a free-form LICENSE file.

    Returns ``None`` when no marker is distinctive enough. Guessing here would
    silently understate a copyleft obligation, which is the one mistake this
    report must not make.
    """
    lowered = content.lower()
    for marker, expression in _LICENSE_FILE_MARKERS:
        if marker in lowered:
            return expression
    return None


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------


def _line_of(content: str, needle: str) -> int:
    """1-based line of the first occurrence, or 0 when absent."""
    if not needle:
        return 0
    for index, line in enumerate(content.splitlines(), start=1):
        if needle in line:
            return index
    return 0


def _classified(dependency: Any) -> tuple[list[str], bool]:
    """Risk labels and pinned-ness from the shared dependency classifier.

    Delegates to ``repository_dependency_service._risk_flags`` rather than
    re-deriving the rules, so a requirement carries the same labels in the
    dependency inspector, the security scan, and this report. Calling it
    directly is the same trade ``security_dependency_scanner._classify`` makes.
    """
    risks, pinned = repository_dependency_service._risk_flags(  # noqa: SLF001
        dependency.name, dependency.version, dependency.ecosystem
    )
    return list(risks), pinned


def _normalised_package_json(content: str) -> str:
    """Return ``content`` with npm object-form specs reduced to their version.

    npm allows a dependency spec to be an object::

        "lodash": {"version": "4.17.21", "license": "MIT"}

    The shared dependency parsers stringify whatever they find in the version
    position, so the object would land in this report as the version
    ``"{'version': '4.17.21', ...}"`` - an unpinned, floating dependency that
    the repository never declared. Reducing the object to the version it
    contains before parsing keeps the inventory truthful.

    An object with no ``version`` key means the range is unstated, which is
    reported as ``*``: floating, and honestly so.
    """
    payload = _json_load(content)
    if payload is None:
        return content
    changed = False
    for section in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies"):
        block = payload.get(section)
        if not isinstance(block, dict):
            continue
        for name, spec in list(block.items()):
            if not isinstance(spec, dict):
                continue
            version = spec.get("version")
            block[name] = version if isinstance(version, str) and version else "*"
            changed = True
    if not changed:
        return content
    try:
        return json.dumps(payload)
    except (TypeError, ValueError):
        return content


def _rows_from_manifest(
    path: str,
    ecosystem: str,
    content: str,
    *,
    origin: str,
) -> list[SupplyChainDependency]:
    """Parse a manifest or lockfile into inventory rows.

    ``security_dependency_scanner.parse_manifest`` is used for dispatch because
    it is the only parser set that covers every manifest this engine claims,
    including ``pom.xml``, and it already resolves the direct/transitive flag
    and the source line. Risk labels come from the shared classifier so they
    match the rest of the product.
    """
    basename = security_sources.basename(path).lower()
    if basename == "package.json":
        content = _normalised_package_json(content)
    from_lockfile = basename in LOCKFILE_BASENAMES
    rows: list[SupplyChainDependency] = []
    for entry in parse_security_manifest(path, ecosystem, content):
        risks, pinned = _classified(entry)
        # A lockfile's own direct/transitive split is more accurate than
        # "everything came from a lockfile". Computed per row, because a
        # lockfile interleaves direct and transitive packages.
        row_origin = origin
        if from_lockfile:
            row_origin = ORIGIN_DIRECT if entry.direct else ORIGIN_TRANSITIVE
        rows.append(
            SupplyChainDependency(
                name=entry.name,
                version=entry.version,
                ecosystem=entry.ecosystem,
                manifest=path,
                scope=entry.scope,
                origin=row_origin,
                pinned=pinned,
                risks=risks,
                line=entry.line,
            )
        )
    return rows


def parse_manifest(
    path: str,
    content: str,
    *,
    licenses: dict[str, str] | None = None,
) -> list[SupplyChainDependency]:
    """Parse one file into inventory rows.

    A manifest yields ``direct`` rows; a lockfile yields the direct/transitive
    split its format actually records. A parse failure yields an empty list
    rather than raising, so one unreadable manifest cannot abort a report - the
    caller records the failure from :func:`parse_file` instead.
    """
    classification = classify_path(path)
    if classification is None:
        return []
    ecosystem, role = classification
    license_map = licenses or {}

    default_origin = ORIGIN_TRANSITIVE if role == ROLE_LOCKFILE else ORIGIN_DIRECT
    rows = _rows_from_manifest(path, ecosystem, content, origin=default_origin)

    for row in rows:
        expression = license_map.get(row.name)
        if expression is not None:
            row.license_expression = expression
            row.license_category = classify_license(expression)
        if not row.line:
            row.line = _line_of(content, f'"{row.name}"') or _line_of(content, row.name)
    return rows


def _licensable(path: str) -> bool:
    """Only some formats carry licence fields worth extracting."""
    return security_sources.basename(path).lower() in {
        "package.json",
        "package-lock.json",
        "npm-shrinkwrap.json",
    }


#: Formats with a container grammar that can be validated directly, so a
#: malformed file is distinguishable from a readable one that declares nothing.
_JSON_FORMATS = frozenset(
    {"package.json", "package-lock.json", "npm-shrinkwrap.json"}
)
_TOML_FORMATS = frozenset({"pyproject.toml"})
#: Line-oriented formats: one requirement per line, so a file that yields no
#: dependencies is empty rather than broken.
_LINE_FORMATS = frozenset({"requirements.txt", "go.mod", "pom.xml"})


def is_wellformed(path: str, content: str) -> bool:
    """Whether ``content`` is a readable file in this format's grammar.

    Distinguishes the two states a dependency parser cannot tell apart by
    looking at its own output: a malformed file and a valid file that declares
    nothing. Both yield zero dependencies, but only one of them is a defect the
    project should fix.
    """
    basename = security_sources.basename(path).lower()
    if basename in _JSON_FORMATS:
        return _json_load(content) is not None
    if basename in _TOML_FORMATS:
        try:
            tomllib.loads(content)
        except Exception:  # noqa: BLE001 - any TOML error means unreadable
            return False
        return True
    if basename in _LINE_FORMATS:
        # A pom.xml must actually contain a project root to be a pom at all.
        if basename == "pom.xml":
            return "<project" in content.lower()
        return True
    return True


def parse_file(
    path: str,
    content: str,
    *,
    found: bool = True,
) -> tuple[SupplyChainManifest, list[SupplyChainDependency], str | None]:
    """Parse one dependency-bearing file.

    Returns ``(manifest, dependencies, project_license)``. The manifest row is
    always produced, even when the file is missing, so a repository that ships
    no ``go.mod`` is visibly different from one whose ``go.mod`` parsed empty.
    """
    classification = classify_path(path)
    if classification is None:
        return (
            SupplyChainManifest(path=path, ecosystem="unknown", role=ROLE_MANIFEST, found=False),
            [],
            None,
        )
    ecosystem, role = classification

    if not found:
        return (
            SupplyChainManifest(
                path=path,
                ecosystem=ecosystem,
                role=role,
                found=False,
                note="Not found in this repository.",
            ),
            [],
            None,
        )

    licenses = extract_licenses(path, content) if _licensable(path) else {}
    dependencies = parse_manifest(path, content, licenses=licenses)

    # A file that fails its own grammar is a defect; a readable file that
    # declares nothing is not.
    parse_failed = bool(content.strip()) and not is_wellformed(path, content)
    if parse_failed:
        note = "Could not be parsed as a dependency manifest."
    elif role == ROLE_LOCKFILE and not dependencies:
        note = (
            "Lockfile present; its resolver-specific format is not expanded by "
            "this report."
        )
    elif not dependencies:
        # An empty but readable manifest is a real, reportable state.
        note = "Present but declares no dependencies."
    else:
        note = f"Resolved {len(dependencies)} dependencies."

    direct = sum(1 for row in dependencies if row.origin == ORIGIN_DIRECT)
    transitive = sum(1 for row in dependencies if row.origin == ORIGIN_TRANSITIVE)

    manifest = SupplyChainManifest(
        path=path,
        ecosystem=ecosystem,
        role=role,
        found=True,
        dependency_count=len(dependencies),
        direct_count=direct,
        transitive_count=transitive,
        parse_failed=parse_failed,
        note=note,
    )
    return manifest, dependencies, project_license_expression(path, content)


def missing_manifest(candidates: Iterable[tuple[str, str]]) -> list[SupplyChainManifest]:
    """Rows for expected files that are absent, for a complete picture."""
    rows: list[SupplyChainManifest] = []
    for path, ecosystem in candidates:
        rows.append(
            SupplyChainManifest(
                path=path,
                ecosystem=ecosystem,
                role=ROLE_MANIFEST,
                found=False,
                note="Not found in this repository.",
            )
        )
    return rows
