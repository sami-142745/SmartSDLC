"""Deterministic analysis for the Dependency & Supply Chain engine.

Turns parsed manifests and an inventory into a prioritised issue list, a
licence rollup, and one hygiene score.

Three rules govern everything here
----------------------------------
1. **No model, no registry.** Every value comes from a file in the repository.
   Nothing is looked up, so nothing is claimed about a version's age, its known
   vulnerabilities, or whether a licence is currently maintained. Those belong
   to registries and advisory feeds, and the security engine already owns the
   advisory side.
2. **Cross-file facts live here, not in the parser.** A single-file parse cannot
   know that a lockfile entry is transitive; that needs the manifest next to
   it. Reconciliation therefore happens after every file has been read.
3. **The score is auditable.** Every deduction is recorded in
   ``summary.score_notes``, so a reader can see exactly why a repository scored
   what it scored and disagree with a specific line.
"""

from __future__ import annotations

from typing import Iterable

from app.schemas.supply_chain import (
    CODE_DEPRECATED_PACKAGE,
    CODE_FLOATING_VERSION,
    CODE_LOCAL_PATH_SOURCE,
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
    CODE_UNRESOLVABLE_VERSION,
    CODE_VCS_SOURCE,
    LIC_PROPRIETARY,
    LIC_STRONG_COPYLEFT,
    LIC_UNKNOWN,
    ORIGIN_DIRECT,
    ORIGIN_TRANSITIVE,
    ORIGIN_UNKNOWN,
    RISK_DEPRECATED,
    RISK_FLOATING_VERSION,
    RISK_GIT_SOURCE,
    RISK_LOCAL_PATH,
    RISK_MISSING_VERSION,
    RISK_UNPINNED,
    RISK_UNRESOLVABLE,
    ROLE_LOCKFILE,
    ROLE_MANIFEST,
    SCORE_BANDS,
    LicenseUse,
    SupplyChainDependency,
    SupplyChainIssue,
    SupplyChainManifest,
    SupplyChainSummary,
)

#: Evidence names attached to an issue. The true count is always available on
#: ``affected_count``, so capping the list never hides the size of a problem.
MAX_EVIDENCE = 10

#: Ceilings on the multi-instance penalties, so one pathological repository
#: cannot drive the score to zero and make every other deduction invisible.
CAP_UNPINNED_PENALTY = 20
CAP_VCS_PENALTY = 12
CAP_LOCAL_PATH_PENALTY = 9
CAP_DEPRECATED_PENALTY = 9
CAP_PARSE_PENALTY = 10
MAX_LICENSE_PENALTY = 20
STRONG_COPYLEFT_PENALTY = 10
PROPRIETARY_PENALTY = 4
NO_MANIFEST_PENALTY = 40
NO_LOCKFILE_PENALTY = 20

#: Dependency risk label -> issue code. The labels come from the shared
#: classifier, so a requirement is reported under the same code everywhere.
_RISK_TO_CODE = {
    RISK_UNPINNED: CODE_UNPINNED_DEPENDENCY,
    RISK_FLOATING_VERSION: CODE_FLOATING_VERSION,
    RISK_UNRESOLVABLE: CODE_UNRESOLVABLE_VERSION,
    RISK_MISSING_VERSION: CODE_MISSING_VERSION,
    RISK_GIT_SOURCE: CODE_VCS_SOURCE,
    RISK_LOCAL_PATH: CODE_LOCAL_PATH_SOURCE,
    RISK_DEPRECATED: CODE_DEPRECATED_PACKAGE,
}

#: Per-risk (severity, title, remediation, score cost per occurrence).
_RISK_PROFILE = {
    RISK_UNPINNED: (
        "medium",
        "Dependency is not pinned to an exact version",
        "Pin the requirement to an exact version so installs are reproducible.",
        2,
    ),
    RISK_FLOATING_VERSION: (
        "low",
        "Dependency uses a version range",
        "Pin the requirement, or commit a lockfile so the resolved set is fixed.",
        0,
    ),
    RISK_UNRESOLVABLE: (
        "medium",
        "Dependency version cannot be resolved",
        "Replace the version with a published release.",
        1,
    ),
    RISK_MISSING_VERSION: (
        "medium",
        "Dependency declares no version",
        "Declare a version constraint so resolution is deterministic.",
        1,
    ),
    RISK_GIT_SOURCE: (
        "high",
        "Dependency is pulled from a VCS URL",
        "Reference a released, immutable version instead of a branch or tag.",
        3,
    ),
    RISK_LOCAL_PATH: (
        "medium",
        "Dependency is a local path",
        "Confirm the local dependency is published to your registry.",
        3,
    ),
    RISK_DEPRECATED: (
        "medium",
        "Dependency is a known-deprecated package",
        "Replace the package with its maintained successor.",
        3,
    ),
}

_SEVERITY_ORDER = ("critical", "high", "medium", "low", "info")


def _sort_key(issue: SupplyChainIssue) -> tuple[int, int, str]:
    """Worst severity first, then the largest problem, then stable by code."""
    try:
        rank = _SEVERITY_ORDER.index(issue.severity)
    except ValueError:
        rank = len(_SEVERITY_ORDER)
    return (rank, -issue.affected_count, issue.code)


# ---------------------------------------------------------------------------
# Cross-file reconciliation
# ---------------------------------------------------------------------------


def _role_by_path(manifests: list[SupplyChainManifest]) -> dict[str, str]:
    return {row.path: row.role for row in manifests if row.found}


def merge_inventory(
    dependencies: list[SupplyChainDependency],
    manifest_rows: list[SupplyChainManifest],
) -> list[SupplyChainDependency]:
    """Collapse manifest and lockfile rows into one inventory.

    A project that ships both ``package.json`` and ``package-lock.json`` names
    the same package twice: once as a declared range, once as a resolved
    version. Reporting both would double the dependency count and make the
    direct/transitive split meaningless, so the inventory holds one row per
    ``(ecosystem, name)``.

    The manifest row is the base, because it carries the declared scope
    (``devDependencies`` versus runtime) that a lockfile does not. The lockfile
    then enriches it with what the resolver actually chose: a concrete version
    in place of a range, and a licence when the manifest omitted one.
    """
    roles = _role_by_path(manifest_rows)
    merged: dict[tuple[str, str], SupplyChainDependency] = {}
    order: list[tuple[str, str]] = []

    def key_of(row: SupplyChainDependency) -> tuple[str, str]:
        return (row.ecosystem, row.name)

    # Manifests first, so they establish the base rows.
    for row in dependencies:
        if roles.get(row.manifest) != ROLE_LOCKFILE:
            key = key_of(row)
            if key in merged:
                continue
            merged[key] = row
            order.append(key)

    for row in dependencies:
        if roles.get(row.manifest) != ROLE_LOCKFILE:
            continue
        key = key_of(row)
        base = merged.get(key)
        if base is None:
            # Present only in the lockfile, so it arrived indirectly.
            row.origin = ORIGIN_TRANSITIVE
            merged[key] = row
            order.append(key)
            continue
        # Present in both: the lockfile knows the version that actually ships.
        if row.version and (not base.version or not base.pinned):
            base.version = row.version
        if row.license_expression and not base.license_expression:
            base.license_expression = row.license_expression
            base.license_category = row.license_category
        if not base.line:
            base.line = row.line

    return [merged[key] for key in order]


# ---------------------------------------------------------------------------
# Licence rollup
# ---------------------------------------------------------------------------


def build_licenses(dependencies: Iterable[SupplyChainDependency]) -> list[LicenseUse]:
    """Roll the inventory up by licence expression, most widely used first."""
    grouped: dict[str, LicenseUse] = {}
    for row in dependencies:
        expression = row.license_expression or "Undeclared"
        entry = grouped.get(expression)
        if entry is None:
            entry = LicenseUse(
                expression=expression,
                category=row.license_category if row.license_expression else LIC_UNKNOWN,
            )
            grouped[expression] = entry
        entry.dependency_count += 1
        if row.origin == ORIGIN_DIRECT:
            entry.direct_dependency_count += 1
        if row.ecosystem not in entry.ecosystems:
            entry.ecosystems.append(row.ecosystem)
        if row.name not in entry.dependencies:
            entry.dependencies.append(row.name)
    for entry in grouped.values():
        entry.ecosystems.sort()
        entry.dependencies.sort()
    return sorted(
        grouped.values(),
        key=lambda item: (-item.dependency_count, item.expression.lower()),
    )


# ---------------------------------------------------------------------------
# Issues
# ---------------------------------------------------------------------------


def _issue(
    code: str,
    severity: str,
    title: str,
    detail: str,
    remediation: str,
    evidence: Iterable[str] = (),
) -> SupplyChainIssue:
    names = list(evidence)
    return SupplyChainIssue(
        code=code,
        severity=severity,
        title=title,
        detail=detail,
        remediation=remediation,
        evidence=names[:MAX_EVIDENCE],
        affected_count=len(names),
    )


def _risk_issues(dependencies: list[SupplyChainDependency]) -> list[SupplyChainIssue]:
    """One issue per risk label, aggregating the dependencies that carry it."""
    buckets: dict[str, list[SupplyChainDependency]] = {}
    for row in dependencies:
        for risk in row.risks:
            if risk in _RISK_PROFILE:
                buckets.setdefault(risk, []).append(row)

    issues: list[SupplyChainIssue] = []
    for risk, rows in buckets.items():
        severity, title, remediation, _cost = _RISK_PROFILE[risk]
        evidence = [
            f"{row.name} ({row.version or 'no version'}) in {row.manifest}:{row.line}"
            for row in rows
        ]
        issues.append(
            _issue(
                _RISK_TO_CODE[risk],
                severity,
                f"{title} ({len(rows)})",
                (
                    f"{len(rows)} dependenc{'y' if len(rows) == 1 else 'ies'} "
                    f"{'is' if len(rows) == 1 else 'are'} affected."
                ),
                remediation,
                evidence,
            )
        )
    return issues


def _manifest_issues(
    manifests: list[SupplyChainManifest],
    dependencies: list[SupplyChainDependency],
) -> list[SupplyChainIssue]:
    """Issues derived from which files exist, not from what they contain."""
    issues: list[SupplyChainIssue] = []
    found = [row for row in manifests if row.found]
    manifests_found = [row for row in found if row.role == ROLE_MANIFEST]
    lockfiles_found = [row for row in found if row.role == ROLE_LOCKFILE]

    if not manifests_found:
        # A lockfile without a manifest means the graph is real but the
        # intentions behind it are not in the repository.
        severity = "high" if lockfiles_found else "medium"
        # Evidence is the expected-but-absent manifests, so the count reflects
        # the opportunity being missed rather than reporting zero.
        evidence = [row.path for row in manifests if row.role == ROLE_MANIFEST] or [
            row.path for row in found
        ]
        issues.append(
            _issue(
                CODE_NO_MANIFEST,
                severity,
                "No dependency manifest found",
                (
                    "A lockfile is present but no manifest declares the direct "
                    "dependencies, so the graph cannot be traced to intent."
                    if lockfiles_found
                    else "No dependency manifest was found, so this project's "
                    "external dependencies are not declared in the repository."
                ),
                "Add the manifest for each ecosystem this project depends on.",
                evidence,
            )
        )

    if manifests_found and not lockfiles_found:
        issues.append(
            _issue(
                CODE_NO_LOCKFILE,
                "high",
                "No lockfile found",
                (
                    "No lockfile is committed, so installs resolve fresh versions "
                    "each time and the same commit can produce different builds."
                ),
                "Commit a lockfile for every ecosystem the project depends on.",
                [row.path for row in manifests_found],
            )
        )

    for row in found:
        if row.parse_failed:
            issues.append(
                _issue(
                    CODE_MANIFEST_UNREADABLE,
                    "medium",
                    f"Could not parse {row.path}",
                    "The file is present but is not a readable dependency manifest.",
                    "Fix the syntax so tooling can resolve the dependency set.",
                    [row.path],
                )
            )

    # A lockfile that resolved packages while its own manifest declares none
    # means the two files disagree about what the project depends on.
    for lockfile in lockfiles_found:
        if not lockfile.dependency_count:
            continue
        empty = [
            row.path
            for row in manifests_found
            if row.ecosystem == lockfile.ecosystem and row.dependency_count == 0
        ]
        if empty:
            issues.append(
                _issue(
                    CODE_PARSE_EMPTY,
                    "medium",
                    f"{lockfile.path} resolves packages that no manifest declares",
                    (
                        "The lockfile resolved dependencies while the manifest for "
                        "the same ecosystem declares none, so the manifest and the "
                        "lockfile disagree."
                    ),
                    "Regenerate the lockfile from the manifest.",
                    empty,
                )
            )

    # A lockfile can exist yet still not enumerate its resolved set, either
    # because its format is resolver-specific (yarn.lock, poetry.lock, go.sum)
    # or because it records no packages. The build is reproducible, but the
    # transitive tree is not auditable from this report.
    unexpanded = [
        row.path
        for row in lockfiles_found
        if row.dependency_count == 0
    ]
    if unexpanded:
        issues.append(
            _issue(
                CODE_UNRESOLVED_TRANSITIVES,
                "low",
                "A lockfile's resolved dependency set is not enumerated",
                (
                    "These lockfiles record a resolved graph, but their "
                    "resolver-specific format is not expanded by this report, so "
                    "the transitive dependency set is not shown here."
                ),
                "Read the lockfile directly, or publish a resolved graph in a "
                "machine-readable format.",
                unexpanded,
            )
        )
    return issues


def _license_issues(
    dependencies: list[SupplyChainDependency],
) -> list[SupplyChainIssue]:
    """Licence issues, aggregated rather than reported per dependency."""
    issues: list[SupplyChainIssue] = []
    total = len(dependencies)
    if not total:
        return issues

    strong = [row for row in dependencies if row.license_category == LIC_STRONG_COPYLEFT]
    proprietary = [row for row in dependencies if row.license_category == LIC_PROPRIETARY]
    undeclared = [row for row in dependencies if not row.license_expression]
    unknown = [
        row
        for row in dependencies
        if row.license_expression and row.license_category == LIC_UNKNOWN
    ]

    if strong:
        direct_strong = [row for row in strong if row.origin == ORIGIN_DIRECT]
        issues.append(
            _issue(
                CODE_STRONG_COPYLEFT,
                "medium",
                f"Strong copyleft licences in the dependency set ({len(strong)})",
                (
                    f"{len(strong)} dependenc{'y' if len(strong) == 1 else 'ies'} "
                    "declare a strong copyleft licence, which carries distribution "
                    "obligations when linked or bundled."
                ),
                "Have counsel review distribution obligations before shipping.",
                [f"{row.name}: {row.license_expression}" for row in strong],
            )
        )
        if direct_strong:
            issues.append(
                _issue(
                    CODE_STRONG_COPYLEFT,
                    "medium",
                    f"A directly chosen dependency is strong copyleft ({len(direct_strong)})",
                    (
                        "A dependency this project names directly carries a strong "
                        "copyleft licence."
                    ),
                    "Review the obligation, or choose an alternative dependency.",
                    [f"{row.name}: {row.license_expression}" for row in direct_strong],
                )
            )

    if proprietary:
        issues.append(
            _issue(
                CODE_PROPRIETARY_LICENSE,
                "medium",
                f"Custom or proprietary licences in the dependency set ({len(proprietary)})",
                (
                    f"{len(proprietary)} dependenc{'y' if len(proprietary) == 1 else 'ies'} "
                    "declare a licence this report cannot map to a standard set, so "
                    "their terms must be read directly."
                ),
                "Read the licence text for each package before redistribution.",
                [f"{row.name}: {row.license_expression}" for row in proprietary],
            )
        )

    if undeclared:
        share = len(undeclared) / total
        issues.append(
            _issue(
                CODE_UNDECLARED_LICENSE,
                "low" if share < 0.5 else "medium",
                f"Dependencies declare no licence ({len(undeclared)} of {total})",
                (
                    f"{len(undeclared)} of {total} dependencies "
                    f"({share:.0%}) carry no licence declaration in the repository. "
                    "Redistribution terms for these packages are not established here."
                ),
                "Check the licence of each package in its own repository or registry.",
                [row.name for row in undeclared],
            )
        )

    if unknown:
        issues.append(
            _issue(
                CODE_UNKNOWN_LICENSE,
                "low",
                f"Licence expressions that could not be classified ({len(unknown)})",
                (
                    f"{len(unknown)} dependenc{'y' if len(unknown) == 1 else 'ies'} "
                    "declare a licence this report does not recognise. It is reported "
                    "as unknown rather than assumed permissive."
                ),
                "Look the expression up against the SPDX list and confirm the terms.",
                [f"{row.name}: {row.license_expression}" for row in unknown],
            )
        )
    return issues


def build_issues(
    manifests: list[SupplyChainManifest],
    dependencies: list[SupplyChainDependency],
) -> list[SupplyChainIssue]:
    """Every supply-chain issue, most severe first."""
    issues = [
        *_manifest_issues(manifests, dependencies),
        *_risk_issues(dependencies),
        *_license_issues(dependencies),
    ]
    issues.sort(key=_sort_key)
    return issues


# ---------------------------------------------------------------------------
# Summary and score
# ---------------------------------------------------------------------------


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _band(score: int) -> str:
    for threshold, band in SCORE_BANDS:
        if score < threshold:
            return band
    return SCORE_BANDS[-1][1]


def _score(
    dependencies: list[SupplyChainDependency],
    manifests: list[SupplyChainManifest],
) -> tuple[int, list[str]]:
    """The hygiene score, with every deduction itemised.

    Starts at 100 for a perfectly declared, pinned, licensed, locked project and
    subtracts for measured weaknesses. It is a *hygiene* score, not a risk or
    vulnerability verdict: it never accounts for a known CVE, because that is the
    security engine's job and double-counting it would make both views harder to
    reason about.
    """
    score = 100
    notes: list[str] = []
    total = len(dependencies)

    def deduct(points: int, reason: str) -> None:
        nonlocal score
        if points <= 0:
            return
        score -= points
        notes.append(f"-{points}: {reason}")

    manifests_found = [row for row in manifests if row.found and row.role == ROLE_MANIFEST]
    lockfiles_found = [row for row in manifests if row.found and row.role == ROLE_LOCKFILE]

    if not manifests_found:
        deduct(NO_MANIFEST_PENALTY, "no dependency manifest declares the direct dependencies")
    elif not lockfiles_found:
        deduct(
            NO_LOCKFILE_PENALTY,
            "no lockfile, so installs are not reproducible",
        )

    parse_failures = [row for row in manifests if row.found and row.parse_failed]
    if parse_failures:
        deduct(
            min(CAP_PARSE_PENALTY, 5 * len(parse_failures)),
            f"{len(parse_failures)} manifest(s) could not be parsed",
        )

    def risk_rows(risk: str) -> list[SupplyChainDependency]:
        return [row for row in dependencies if risk in row.risks]

    unpinned = risk_rows(RISK_UNPINNED)
    if unpinned:
        deduct(
            min(CAP_UNPINNED_PENALTY, 2 * len(unpinned)),
            f"{len(unpinned)} dependenc(y/ies) not pinned to an exact version",
        )

    vcs = risk_rows(RISK_GIT_SOURCE)
    if vcs:
        deduct(
            min(CAP_VCS_PENALTY, 3 * len(vcs)),
            f"{len(vcs)} dependenc(y/ies) pulled from a VCS URL",
        )

    local = risk_rows(RISK_LOCAL_PATH)
    if local:
        deduct(
            min(CAP_LOCAL_PATH_PENALTY, 3 * len(local)),
            f"{len(local)} dependenc(y/ies) resolved from a local path",
        )

    deprecated = risk_rows(RISK_DEPRECATED)
    if deprecated:
        deduct(
            min(CAP_DEPRECATED_PENALTY, 3 * len(deprecated)),
            f"{len(deprecated)} known-deprecated package(s)",
        )

    unknown_or_missing = [
        row for row in dependencies if row.license_category == LIC_UNKNOWN
    ]
    if total:
        share = len(unknown_or_missing) / total
        if share:
            points = min(MAX_LICENSE_PENALTY, round(MAX_LICENSE_PENALTY * share))
            deduct(
                points,
                f"{len(unknown_or_missing)} of {total} dependencies "
                f"({share:.0%}) have no classifiable licence",
            )

    strong = [row for row in dependencies if row.license_category == LIC_STRONG_COPYLEFT]
    if strong:
        deduct(STRONG_COPYLEFT_PENALTY, f"{len(strong)} strong copyleft dependency(ies)")

    proprietary = [row for row in dependencies if row.license_category == LIC_PROPRIETARY]
    if proprietary:
        deduct(PROPRIETARY_PENALTY, f"{len(proprietary)} custom or proprietary licence(s)")

    score = max(0, min(100, score))
    return score, notes


def build_summary(
    manifests: list[SupplyChainManifest],
    dependencies: list[SupplyChainDependency],
    issues: list[SupplyChainIssue],
    *,
    declared_license: str | None = None,
) -> SupplyChainSummary:
    """Counts, ratios, and the auditable hygiene score."""
    total = len(dependencies)
    direct = sum(1 for row in dependencies if row.origin == ORIGIN_DIRECT)
    transitive = sum(1 for row in dependencies if row.origin == ORIGIN_TRANSITIVE)
    unknown_origin = sum(1 for row in dependencies if row.origin == ORIGIN_UNKNOWN)
    pinned = sum(1 for row in dependencies if row.pinned)
    licensed = sum(1 for row in dependencies if row.license_expression)
    unknown_licence = sum(1 for row in dependencies if row.license_category == LIC_UNKNOWN)

    categories: dict[str, int] = {}
    for row in dependencies:
        key = row.license_category
        categories[key] = categories.get(key, 0) + 1

    ecosystems = sorted({row.ecosystem for row in dependencies if row.ecosystem})
    with_transitives = sorted(
        {row.manifest for row in dependencies if row.origin == ORIGIN_TRANSITIVE}
    )

    by_severity: dict[str, int] = {}
    by_code: dict[str, int] = {}
    for issue in issues:
        by_severity[issue.severity] = by_severity.get(issue.severity, 0) + 1
        by_code[issue.code] = by_code.get(issue.code, 0) + issue.affected_count

    score, notes = _score(dependencies, manifests)

    return SupplyChainSummary(
        manifest_count=sum(1 for row in manifests if row.found and row.role == ROLE_MANIFEST),
        lockfile_count=sum(1 for row in manifests if row.found and row.role == ROLE_LOCKFILE),
        total_dependencies=total,
        direct_dependencies=direct,
        transitive_dependencies=transitive,
        unknown_origin_dependencies=unknown_origin,
        pinned_dependencies=pinned,
        unpinned_dependencies=total - pinned,
        pinned_ratio=_ratio(pinned, total),
        licensed_dependencies=licensed,
        unknown_license_dependencies=unknown_licence,
        declared_license_dependencies=total - unknown_licence,
        license_coverage_ratio=_ratio(licensed, total),
        declared_license=declared_license,
        license_categories=dict(sorted(categories.items())),
        ecosystems=ecosystems,
        manifests_with_transitives=with_transitives,
        hygiene_score=score,
        score_band=_band(score),
        score_notes=notes,
        issue_count=len(issues),
        issues_by_severity=dict(sorted(by_severity.items())),
        issues_by_code=dict(sorted(by_code.items())),
    )


def build_analysis(
    manifests: list[SupplyChainManifest],
    dependencies: list[SupplyChainDependency],
    *,
    declared_license: str | None = None,
) -> tuple[list[LicenseUse], list[SupplyChainIssue], SupplyChainSummary]:
    """The full deterministic analysis for one repository.

    Reconciliation runs first because the issue list, the licence rollup, and the
    score all depend on knowing which dependencies the project actually chose
    and which arrived indirectly.
    """
    dependencies = merge_inventory(dependencies, manifests)
    licenses = build_licenses(dependencies)
    issues = build_issues(manifests, dependencies)
    summary = build_summary(manifests, dependencies, issues, declared_license=declared_license)
    return licenses, issues, summary
