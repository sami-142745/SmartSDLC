"""Deterministic documentation analysis.

Turns parsed documentation assets and source-coverage rows into gaps and a
summary. Nothing here calls a model or reads the network; every output is a
function of the inputs, sorted so the same repository always yields the same
report.

The guiding rule: a gap is an observed absence with the evidence that produced
it, never a judgement about writing quality.
"""

from __future__ import annotations

from typing import Iterable

from app.schemas.documentation_intelligence import (
    CANONICAL_FILES,
    LOW_DOCSTRING_COVERAGE,
    METHODOLOGY,
    THIN_README_WORDS,
    UNDOCUMENTED_SYMBOL_GAP_THRESHOLD,
    DocumentationAsset,
    DocumentationCoverage,
    DocumentationGap,
    DocumentationGapSeverity,
    DocumentationSummary,
)

#: Upper bound on per-file gaps of one kind, so a repository with thousands of
#: files cannot produce a report larger than the summary that describes it.
_MAX_PER_FILE_GAPS = 25

#: Documentation files every mature repository is expected to carry, mapped to
#: the asset kind that satisfies them.
_CANONICAL_KIND: dict[str, str] = {
    "readme": "readme",
    "license": "license",
    "changelog": "changelog",
    "contributing": "contributing",
    "security_policy": "security_policy",
}


def _gap(
    kind: str,
    severity: DocumentationGapSeverity,
    title: str,
    detail: str,
    evidence: str,
    paths: list[str] | None = None,
) -> DocumentationGap:
    return DocumentationGap(
        kind=kind,  # type: ignore[arg-type]
        severity=severity,
        title=title,
        detail=detail,
        evidence=evidence,
        paths=paths or [],
    )


def build_analysis(
    assets: Iterable[DocumentationAsset],
    coverage: Iterable[DocumentationCoverage],
    *,
    source_files: int = 0,
) -> tuple[list[DocumentationGap], DocumentationSummary]:
    """Build the gap list and summary for one repository.

    ``source_files`` is the number of source files seen in the tree (not all are
    necessarily parsed for coverage). File-selection truncation is reported on the
    graph itself rather than folded into the summary.
    """
    asset_list = sorted(assets, key=lambda asset: asset.path)
    coverage_list = sorted(
        (row for row in coverage if row.path), key=lambda row: row.path
    )
    gaps: list[DocumentationGap] = []

    kinds_present = {asset.kind for asset in asset_list}
    readme = next((asset for asset in asset_list if asset.kind == "readme"), None)

    # -- Canonical files -----------------------------------------------------
    missing_canonical: list[str] = []
    for canonical in CANONICAL_FILES:
        if _CANONICAL_KIND[canonical] not in kinds_present:
            missing_canonical.append(canonical)

    if readme is None:
        gaps.append(
            _gap(
                "missing_readme",
                "warning",
                "No README",
                "The repository has no file named README, so there is no entry "
                "point explaining what the project is.",
                "No README.* file was found in the repository tree.",
            )
        )
    else:
        if not readme.has_install:
            gaps.append(
                _gap(
                    "missing_install_section",
                    "warning",
                    "README does not explain installation",
                    "A new contributor cannot tell how to get the project running.",
                    f"{readme.path} has no install/setup/getting-started heading.",
                    [readme.path],
                )
            )
        if not readme.has_usage:
            gaps.append(
                _gap(
                    "missing_usage_section",
                    "warning",
                    "README does not explain usage",
                    "The README does not show how the project is used.",
                    f"{readme.path} has no usage/example/API heading.",
                    [readme.path],
                )
            )
        if readme.word_count < THIN_README_WORDS:
            gaps.append(
                _gap(
                    "thin_readme",
                    "warning",
                    "README is very short",
                    "A short README usually omits the context a reader needs.",
                    f"{readme.path} contains {readme.word_count} words "
                    f"(fewer than {THIN_README_WORDS}).",
                    [readme.path],
                )
            )

    if "license" not in kinds_present:
        gaps.append(
            _gap(
                "missing_license",
                "warning",
                "No license file",
                "Without a license the terms under which the code may be used are "
                "undefined.",
                "No LICENSE/COPYING file was found in the repository tree.",
            )
        )
    if "changelog" not in kinds_present:
        gaps.append(
            _gap(
                "missing_changelog",
                "info",
                "No changelog",
                "The project keeps no record of changes between releases.",
                "No CHANGELOG/HISTORY file was found in the repository tree.",
            )
        )
    if "contributing" not in kinds_present:
        gaps.append(
            _gap(
                "missing_contributing",
                "info",
                "No contributing guide",
                "There is no stated process for contributing to the project.",
                "No CONTRIBUTING file was found in the repository tree.",
            )
        )
    if "security_policy" not in kinds_present:
        gaps.append(
            _gap(
                "missing_security_policy",
                "info",
                "No security policy",
                "There is no stated way to report a security issue.",
                "No SECURITY file was found in the repository tree.",
            )
        )

    has_docs_dir = any(asset.path.startswith("docs/") for asset in asset_list)
    if asset_list and not has_docs_dir:
        gaps.append(
            _gap(
                "no_docs_directory",
                "info",
                "No docs directory",
                "All documentation lives in top-level files rather than a docs tree.",
                "No documentation file lives under docs/.",
            )
        )

    # -- Links ---------------------------------------------------------------
    total_links = 0
    broken_by_asset: list[tuple[str, list[str]]] = []
    for asset in asset_list:
        for link in asset.links:
            if not link.internal:
                continue
            total_links += 1
            if link.resolved is False:
                broken_by_asset.append((asset.path, [link.target]))
    # Merge broken targets per asset, preserving deterministic order.
    merged_broken: dict[str, list[str]] = {}
    for path, targets in broken_by_asset:
        merged_broken.setdefault(path, []).extend(targets)
    for path in sorted(merged_broken)[:_MAX_PER_FILE_GAPS]:
        targets = sorted(set(merged_broken[path]))
        gaps.append(
            _gap(
                "broken_relative_link",
                "warning",
                "Broken relative link",
                "A link points at a path that does not exist in the repository.",
                f"{path} links to {', '.join(targets)} which could not be found.",
                [path],
            )
        )

    # -- Docstring coverage --------------------------------------------------
    public_symbols = sum(row.public_symbols for row in coverage_list)
    documented_symbols = sum(row.documented_symbols for row in coverage_list)
    docstring_coverage = documented_symbols / public_symbols if public_symbols else 1.0

    low_coverage = [
        row
        for row in coverage_list
        if row.public_symbols >= 3 and row.coverage < LOW_DOCSTRING_COVERAGE
    ]
    low_coverage.sort(key=lambda row: (row.coverage, row.path))
    for row in low_coverage[:_MAX_PER_FILE_GAPS]:
        gaps.append(
            _gap(
                "low_docstring_coverage",
                "warning",
                "Low docstring coverage",
                "Most public symbols in this file carry no docstring.",
                f"{row.path}: {row.documented_symbols}/{row.public_symbols} public "
                f"symbols documented ({row.coverage:.0%}).",
                [row.path],
            )
        )

    undocumented = [
        row
        for row in coverage_list
        if len(row.undocumented) >= UNDOCUMENTED_SYMBOL_GAP_THRESHOLD
    ]
    undocumented.sort(key=lambda row: (-len(row.undocumented), row.path))
    for row in undocumented[:_MAX_PER_FILE_GAPS]:
        names = ", ".join(row.undocumented[:5])
        gaps.append(
            _gap(
                "undocumented_public_api",
                "info",
                "Undocumented public API",
                "Public symbols are exposed without any documentation.",
                f"{row.path}: {len(row.undocumented)} undocumented "
                f"({names}{', …' if len(row.undocumented) > 5 else ''}).",
                [row.path],
            )
        )

    # Keep the list sorted by kind then path so it is stable across runs.
    gaps.sort(key=lambda gap: (gap.kind, gap.paths[0] if gap.paths else "", gap.title))

    documentation_files = len(asset_list)
    denominator = documentation_files + max(source_files, 0)
    documentation_ratio = documentation_files / denominator if denominator else 0.0

    summary = DocumentationSummary(
        total_assets=len(asset_list),
        documentation_files=documentation_files,
        source_files=max(source_files, 0),
        documentation_ratio=round(documentation_ratio, 4),
        readme_present=readme is not None,
        readme_word_count=readme.word_count if readme else 0,
        readme_sections=len(readme.headings) if readme else 0,
        missing_canonical=missing_canonical,
        total_links=total_links,
        broken_links=sum(len(targets) for targets in merged_broken.values()),
        public_symbols=public_symbols,
        documented_symbols=documented_symbols,
        docstring_coverage=round(docstring_coverage, 4),
        coverage_score=_coverage_score(
            readme=readme,
            missing_canonical=missing_canonical,
            docstring_coverage=docstring_coverage,
            broken_links=sum(len(targets) for targets in merged_broken.values()),
        ),
        gap_count=len(gaps),
        methodology=METHODOLOGY,
    )
    return gaps, summary


def _coverage_score(
    *,
    readme: DocumentationAsset | None,
    missing_canonical: list[str],
    docstring_coverage: float,
    broken_links: int,
) -> int:
    """A deterministic 0–100 documentation score.

    The deductions are fixed and published in the frontend, so the number is
    auditable rather than a black box. It measures presence and coverage of
    documented structure; it is not a judgement of the prose.
    """
    score = 100
    if readme is None:
        score -= 40
    else:
        if not readme.has_install:
            score -= 8
        if not readme.has_usage:
            score -= 8
        if not readme.has_examples:
            score -= 4
        if readme.word_count < THIN_README_WORDS:
            score -= 6
    if "license" in missing_canonical:
        score -= 10
    if "changelog" in missing_canonical:
        score -= 5
    if "contributing" in missing_canonical:
        score -= 3
    if "security_policy" in missing_canonical:
        score -= 3
    score -= round((1 - docstring_coverage) * 20)
    score -= min(broken_links * 2, 10)
    return max(0, min(100, score))
