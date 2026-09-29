"""Contracts for the Documentation Intelligence Engine.

This is a deterministic analysis of how well a repository documents itself. It is
deliberately separate from :mod:`app.schemas.documentation`, which describes
*generated* prose documentation: that is an artifact produced by a model, while
everything here is measured from the repository's own files and source.

The distinction that matters throughout: a gap is an observed fact about the
repository ("no LICENSE file is present", "14 of 40 public functions have no
docstring"), never a qualitative judgement about the writing. Every gap carries
the evidence that produced it so a reviewer can check it.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

#: What a documentation file is. ``other`` covers a real markdown/text file that
#: matches no stronger rule — an observation, not a placeholder.
DocumentationAssetKind = Literal[
    "readme",
    "changelog",
    "contributing",
    "license",
    "security_policy",
    "code_of_conduct",
    "api_reference",
    "adr",
    "guide",
    "documentation",
    "other",
]

#: A documentation gap. Each is measured, not inferred.
DocumentationGapKind = Literal[
    "missing_readme",
    "missing_install_section",
    "missing_usage_section",
    "missing_license",
    "missing_changelog",
    "missing_contributing",
    "missing_security_policy",
    "thin_readme",
    "no_docs_directory",
    "broken_relative_link",
    "low_docstring_coverage",
    "undocumented_public_api",
]

#: ``info`` marks an observation, ``warning`` a gap worth acting on. There is no
#: ``critical``: absent documentation does not break a build, and inflating it to
#: the severity scale used by security findings would distort both.
DocumentationGapSeverity = Literal["info", "warning"]

#: Documentation languages this engine parses structurally.
DocumentationLanguage = Literal["markdown", "rst", "asciidoc", "text", "python", "javascript", "typescript"]

#: Canonical files a mature repository is expected to carry. Presence is checked
#: case-insensitively against these names; absence is reported as a gap.
CANONICAL_FILES: dict[str, str] = {
    "readme": "README",
    "license": "LICENSE",
    "changelog": "CHANGELOG",
    "contributing": "CONTRIBUTING",
    "security_policy": "SECURITY",
}

#: Section headings that indicate a README explains how to install the project.
INSTALL_HEADINGS = frozenset(
    {
        "install",
        "installation",
        "installing",
        "getting started",
        "get started",
        "setup",
        "set up",
        "quickstart",
        "quick start",
        "requirements",
        "dependencies",
    }
)

#: Section headings that indicate a README explains how to use the project.
USAGE_HEADINGS = frozenset(
    {
        "usage",
        "using",
        "use",
        "how to use",
        "example",
        "examples",
        "documentation",
        "api",
        "commands",
        "configuration",
        "config",
    }
)

#: README word count below which the file is reported as thin.
THIN_README_WORDS = 120

#: Docstring coverage below which a language is flagged.
LOW_DOCSTRING_COVERAGE = 0.5

#: A public module with more than this many undocumented symbols is called out
#: directly, so the gap names a location rather than only an aggregate.
UNDOCUMENTED_SYMBOL_GAP_THRESHOLD = 3

METHODOLOGY = (
    "No model is used. Documentation coverage is measured from the repository's "
    "own files: canonical files are detected by path, README structure is parsed "
    "from its headings, relative links are checked against files that exist in "
    "the tree, and docstring coverage counts public symbols whose definition is "
    "preceded by a docstring or documentation comment."
)


class DocumentationHeading(BaseModel):
    """One heading in a documentation file."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    level: int
    text: str
    line: int


class DocumentationLink(BaseModel):
    """One link found in a documentation file.

    ``internal`` is true for a repository-relative target. ``resolved`` is
    ``None`` for an external link (never fetched, so never judged) and a boolean
    for an internal one.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    text: str
    target: str
    internal: bool
    resolved: bool | None = None


class DocumentationAsset(BaseModel):
    """One documentation file, with the structure measured from its content."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    kind: DocumentationAssetKind
    language: DocumentationLanguage | None = None
    size_bytes: int = 0
    line_count: int = 0
    word_count: int = 0
    headings: list[DocumentationHeading] = Field(default_factory=list, max_length=500)
    has_toc: bool = False
    has_install: bool = False
    has_usage: bool = False
    has_examples: bool = False
    has_license: bool = False
    has_contributing: bool = False
    code_blocks: int = 0
    images: int = 0
    badges: int = 0
    links: list[DocumentationLink] = Field(default_factory=list, max_length=500)


class DocumentedSymbol(BaseModel):
    """A public symbol and whether it carries documentation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    kind: Literal["function", "class", "method", "interface", "type", "const"]
    documented: bool


class DocumentationCoverage(BaseModel):
    """Docstring coverage for one source file."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    language: Literal["python", "javascript", "typescript"]
    public_symbols: int
    documented_symbols: int
    coverage: float
    undocumented: list[str] = Field(default_factory=list, max_length=100)


class DocumentationGap(BaseModel):
    """One measured documentation gap."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: DocumentationGapKind
    severity: DocumentationGapSeverity
    title: str
    detail: str
    evidence: str
    paths: list[str] = Field(default_factory=list, max_length=50)


class DocumentationSummary(BaseModel):
    """Aggregate documentation health for the repository."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    total_assets: int = 0
    documentation_files: int = 0
    source_files: int = 0
    documentation_ratio: float = 0.0
    readme_present: bool = False
    readme_word_count: int = 0
    readme_sections: int = 0
    missing_canonical: list[str] = Field(default_factory=list)
    total_links: int = 0
    broken_links: int = 0
    public_symbols: int = 0
    documented_symbols: int = 0
    docstring_coverage: float = 0.0
    coverage_score: int = 0
    gap_count: int = 0
    methodology: str = METHODOLOGY


class DocumentationIntelligence(BaseModel):
    """Documentation health for one repository at one ref."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    repository_id: str
    owner: str
    repository: str
    full_name: str
    provider: str
    ref: str | None = None
    commit_sha: str | None = None
    analyzed_at: str
    duration_ms: int = 0
    assets: list[DocumentationAsset] = Field(default_factory=list, max_length=1000)
    coverage: list[DocumentationCoverage] = Field(default_factory=list, max_length=2000)
    gaps: list[DocumentationGap] = Field(default_factory=list, max_length=200)
    summary: DocumentationSummary = Field(default_factory=DocumentationSummary)
    errors: list[str] = Field(default_factory=list, max_length=20)
    truncated: bool = False
