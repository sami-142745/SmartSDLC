"""Response/request models for the Repository Intelligence module.

Every model here is a faithful projection of observed repository data. Fields
that a provider may omit are optional and are surfaced as ``None`` rather than
being defaulted to a plausible-looking zero, so the frontend can distinguish
"not measured" from "measured as zero".
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Repository profile
# ---------------------------------------------------------------------------


class RepositoryProfile(BaseModel):
    """Metadata used by the health score and the dashboard header."""

    owner: str
    repository: str
    name: str
    full_name: str
    private: bool = False
    description: str | None = None
    html_url: str | None = None
    default_branch: str | None = None
    primary_language: str | None = None
    stars: int = 0
    forks: int = 0
    watchers: int = 0
    open_issues: int = 0
    size_kb: int = 0
    license_key: str | None = None
    license_name: str | None = None
    topics: list[str] = Field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None
    pushed_at: str | None = None
    archived: bool = False
    is_fork: bool = False


# ---------------------------------------------------------------------------
# Health score
# ---------------------------------------------------------------------------


class HealthComponent(BaseModel):
    """One weighted signal contributing to the overall health score.

    ``score`` is ``None`` when the underlying signal is not observable (for
    example a repository that never reports a push timestamp). Unavailable
    components are dropped from the weighted average instead of being scored 0,
    and are reported through ``unavailable_signals``.
    """

    key: str
    label: str
    score: float | None
    weight: float
    detail: str


class RepositoryHealth(BaseModel):
    owner: str
    repository: str
    score: float
    grade: str
    components: list[HealthComponent]
    unavailable_signals: list[str]
    #: Signals the score was actually averaged over (weights summing to 1.0).
    measured_weight: float
    method: str
    generated_at: str | None = None
    cached: bool = False


# ---------------------------------------------------------------------------
# Language breakdown
# ---------------------------------------------------------------------------


class LanguageSlice(BaseModel):
    name: str
    bytes: int
    percent: float


class LanguageBreakdown(BaseModel):
    owner: str
    repository: str
    total_bytes: int
    languages: list[LanguageSlice]
    #: Bytes not attributed to any of the reported top languages.
    other_bytes: int
    truncated: bool
    cached: bool = False


# ---------------------------------------------------------------------------
# Dependency inspector
# ---------------------------------------------------------------------------


# Risk labels are plain strings so they stay stable for the frontend:
# ``unpinned``, ``floating_version``, ``git_source``, ``local_path``,
# ``known_risk`` and ``missing_version``.
class Dependency(BaseModel):
    name: str
    version: str | None = None
    ecosystem: str
    manifest: str
    scope: str = "runtime"
    risks: list[str] = Field(default_factory=list)
    pinned: bool = True


class DependencyManifest(BaseModel):
    path: str
    ecosystem: str
    found: bool
    reason: str | None = None


class DependencyReport(BaseModel):
    owner: str
    repository: str
    manifests: list[DependencyManifest]
    dependencies: list[Dependency]
    total: int
    direct_count: int
    flagged_count: int
    ecosystems: list[str]
    cached: bool = False


# ---------------------------------------------------------------------------
# README intelligence
# ---------------------------------------------------------------------------


class ReadmeSection(BaseModel):
    heading: str
    level: int
    line: int
    preview: str


class ReadmeCodeSample(BaseModel):
    language: str | None
    lines: int


class ReadmeIntelligence(BaseModel):
    owner: str
    repository: str
    path: str | None
    available: bool
    reason: str | None = None
    raw: str | None = None
    size_bytes: int = 0
    line_count: int = 0
    word_count: int = 0
    sections: list[ReadmeSection] = Field(default_factory=list)
    has_badges: bool = False
    badge_count: int = 0
    has_toc: bool = False
    has_install_section: bool = False
    has_usage_section: bool = False
    has_license_section: bool = False
    code_blocks: int = 0
    languages_used: list[str] = Field(default_factory=list)
    images: int = 0
    links: int = 0
    cached: bool = False


# ---------------------------------------------------------------------------
# Explorer
# ---------------------------------------------------------------------------


class RepositoryTreeEntry(BaseModel):
    path: str
    name: str
    type: str
    size: int = 0
    depth: int = 0


class RepositoryTree(BaseModel):
    owner: str
    repository: str
    ref: str | None = None
    #: False when the provider truncated the recursive tree listing.
    truncated: bool = False
    total_files: int = 0
    total_directories: int = 0
    total_bytes: int = 0
    entries: list[RepositoryTreeEntry] = Field(default_factory=list)
    cached: bool = False


class RepositoryFileContent(BaseModel):
    path: str
    content: str
    size: int
    truncated: bool = False
    language: str | None = None
    binary: bool = False


# ---------------------------------------------------------------------------
# Aggregate dashboard
# ---------------------------------------------------------------------------


class RepositoryDashboard(BaseModel):
    owner: str
    repository: str
    profile: RepositoryProfile
    health: RepositoryHealth
    languages: LanguageBreakdown
    dependencies: DependencyReport
    readme: ReadmeIntelligence
    generated_at: str
    cached: bool = False
