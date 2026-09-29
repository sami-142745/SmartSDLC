"""Contracts for the Dependency & Supply Chain Intelligence report.

Deliberate scope
----------------
This engine answers *supply-chain hygiene* questions that the existing
dependency inspector does not: which licences a project pulls in, whether a
build is reproducible, how much of the tree was transitively inherited, and
what to fix first.

It does **not** re-derive vulnerability findings. ``security_dependency_scanner``
already owns known-vulnerability matching, and duplicating it would produce two
findings for one weakness. This report is the companion view, not a rival.

Everything here is a measured fact or a stated derivation. No field is filled by
a language model, and no field asserts legal advice.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

#: How a file participates in dependency resolution.
#:
#: ``manifest`` declares what a project wants; ``lockfile`` records what a
#: resolver actually chose. The distinction drives reproducibility, so it is
#: modelled explicitly rather than inferred from the filename at read time.
ManifestRole = Literal["manifest", "lockfile"]

ROLE_MANIFEST: ManifestRole = "manifest"
ROLE_LOCKFILE: ManifestRole = "lockfile"

#: Where a dependency came from in the dependency graph.
#:
#: ``direct`` means the project named it. ``transitive`` means it arrived
#: through another package. ``unknown`` means the project declared a manifest
#: but no lockfile, so the graph was never materialised and the distinction
#: cannot be made from what is in the repository.
DependencyOrigin = Literal["direct", "transitive", "unknown"]

ORIGIN_DIRECT: DependencyOrigin = "direct"
ORIGIN_TRANSITIVE: DependencyOrigin = "transitive"
ORIGIN_UNKNOWN: DependencyOrigin = "unknown"

#: Coarse licence posture. A classification of the declared expression, not a
#: legal conclusion.
LicenseCategory = Literal[
    "public_domain",
    "permissive",
    "weak_copyleft",
    "strong_copyleft",
    "proprietary",
    "unknown",
]

LIC_PUBLIC_DOMAIN: LicenseCategory = "public_domain"
LIC_PERMISSIVE: LicenseCategory = "permissive"
LIC_WEAK_COPYLEFT: LicenseCategory = "weak_copyleft"
LIC_STRONG_COPYLEFT: LicenseCategory = "strong_copyleft"
LIC_PROPRIETARY: LicenseCategory = "proprietary"
LIC_UNKNOWN: LicenseCategory = "unknown"

LICENSE_CATEGORIES: tuple[str, ...] = (
    LIC_PUBLIC_DOMAIN,
    LIC_PERMISSIVE,
    LIC_WEAK_COPYLEFT,
    LIC_STRONG_COPYLEFT,
    LIC_PROPRIETARY,
    LIC_UNKNOWN,
)

#: Ordered worst-first, matching :data:`app.schemas.security.SEVERITIES`, so
#: "the most severe issue" is a minimum index and not a custom comparison.
SEVERITIES: tuple[str, ...] = ("critical", "high", "medium", "low", "info")

#: Issue codes. Stable strings: the frontend groups on them and tests assert on
#: them, so renaming one is an API change.
CODE_NO_MANIFEST = "no_manifest"
CODE_NO_LOCKFILE = "no_lockfile"
CODE_UNPINNED_DEPENDENCY = "unpinned_dependency"
CODE_FLOATING_VERSION = "floating_version"
CODE_UNRESOLVABLE_VERSION = "unresolvable_version"
CODE_VCS_SOURCE = "vcs_source"
CODE_LOCAL_PATH_SOURCE = "local_path_source"
CODE_MISSING_VERSION = "missing_version"
CODE_DEPRECATED_PACKAGE = "deprecated_package"
CODE_UNDECLARED_LICENSE = "undeclared_license"
CODE_UNKNOWN_LICENSE = "unknown_license"
CODE_STRONG_COPYLEFT = "strong_copyleft"
CODE_PROPRIETARY_LICENSE = "proprietary_license"
CODE_UNRESOLVED_TRANSITIVES = "unresolved_transitives"
CODE_MANIFEST_UNREADABLE = "manifest_unreadable"
CODE_PARSE_EMPTY = "parse_empty"

ISSUE_CODES: tuple[str, ...] = (
    CODE_NO_MANIFEST,
    CODE_NO_LOCKFILE,
    CODE_MANIFEST_UNREADABLE,
    CODE_PARSE_EMPTY,
    CODE_UNPINNED_DEPENDENCY,
    CODE_FLOATING_VERSION,
    CODE_UNRESOLVABLE_VERSION,
    CODE_MISSING_VERSION,
    CODE_VCS_SOURCE,
    CODE_LOCAL_PATH_SOURCE,
    CODE_DEPRECATED_PACKAGE,
    CODE_UNDECLARED_LICENSE,
    CODE_UNKNOWN_LICENSE,
    CODE_STRONG_COPYLEFT,
    CODE_PROPRIETARY_LICENSE,
    CODE_UNRESOLVED_TRANSITIVES,
)

#: Risk labels produced by ``repository_dependency_service._risk_flags``. Reused
#: verbatim so a requirement is labelled identically in the dependency inspector,
#: the security scan, and here.
RISK_UNPINNED = "unpinned"
RISK_FLOATING_VERSION = "floating_version"
RISK_MISSING_VERSION = "missing_version"
RISK_GIT_SOURCE = "git_source"
RISK_LOCAL_PATH = "local_path"
RISK_DEPRECATED = "deprecated_package"
RISK_UNRESOLVABLE = "unresolvable_version"

#: Reported hygiene bands, worst-first.
SCORE_BANDS: tuple[tuple[int, str], ...] = (
    (60, "critical"),
    (80, "weak"),
    (92, "fair"),
    (101, "strong"),
)

#: Hiding a large lockfile behind a cap would misreport reproducibility, so the
#: inventory is bounded rather than the file being skipped.
DEFAULT_MAX_DEPENDENCIES = 2000


class SupplyChainManifest(BaseModel):
    """One dependency-bearing file found (or expected) in the repository."""

    path: str
    ecosystem: str
    role: ManifestRole
    found: bool
    dependency_count: int = 0
    direct_count: int = 0
    transitive_count: int = 0
    parse_failed: bool = False
    note: str | None = None


class SupplyChainDependency(BaseModel):
    """One resolved dependency in the inventory."""

    name: str
    version: str | None = None
    ecosystem: str
    manifest: str
    scope: str = "runtime"
    origin: DependencyOrigin = ORIGIN_UNKNOWN
    pinned: bool = True
    risks: list[str] = Field(default_factory=list)
    license_expression: str | None = None
    license_category: LicenseCategory = LIC_UNKNOWN
    line: int = 0


class LicenseUse(BaseModel):
    """A licence expression and how much of the inventory carries it."""

    expression: str
    category: LicenseCategory
    dependency_count: int = 0
    direct_dependency_count: int = 0
    ecosystems: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)


class SupplyChainIssue(BaseModel):
    """One prioritised supply-chain finding with the evidence behind it."""

    code: str
    severity: str
    title: str
    detail: str
    remediation: str
    evidence: list[str] = Field(default_factory=list)
    affected_count: int = 0


class SupplyChainSummary(BaseModel):
    """Counts and the hygiene score."""

    manifest_count: int = 0
    lockfile_count: int = 0
    total_dependencies: int = 0
    direct_dependencies: int = 0
    transitive_dependencies: int = 0
    unknown_origin_dependencies: int = 0
    pinned_dependencies: int = 0
    unpinned_dependencies: int = 0
    pinned_ratio: float = 0.0
    licensed_dependencies: int = 0
    unknown_license_dependencies: int = 0
    declared_license_dependencies: int = 0
    license_coverage_ratio: float = 0.0
    declared_license: str | None = None
    license_categories: dict[str, int] = Field(default_factory=dict)
    ecosystems: list[str] = Field(default_factory=list)
    manifests_with_transitives: list[str] = Field(default_factory=list)
    hygiene_score: int = 0
    score_band: str = "critical"
    score_notes: list[str] = Field(default_factory=list)
    issue_count: int = 0
    issues_by_severity: dict[str, int] = Field(default_factory=dict)
    issues_by_code: dict[str, int] = Field(default_factory=dict)


class SupplyChainReport(BaseModel):
    """The full dependency & supply chain report for one repository."""

    repository_id: str
    owner: str
    repository: str
    full_name: str
    provider: str
    ref: str | None = None
    commit_sha: str | None = None
    analyzed_at: str
    duration_ms: int = 0
    manifests: list[SupplyChainManifest] = Field(default_factory=list)
    dependencies: list[SupplyChainDependency] = Field(default_factory=list)
    licenses: list[LicenseUse] = Field(default_factory=list)
    issues: list[SupplyChainIssue] = Field(default_factory=list)
    summary: SupplyChainSummary = Field(default_factory=SupplyChainSummary)
    errors: list[str] = Field(default_factory=list)
    truncated: bool = False
    cached: bool = False
