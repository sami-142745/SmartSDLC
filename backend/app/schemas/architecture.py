"""Domain contract for the Architecture Intelligence Engine.

What this module claims, and what it refuses to claim
-----------------------------------------------------
The existing Architecture page drew a radial graph of *repositories* sized by
finding count. That is a portfolio view, not architecture. This contract is for
the thing the name implies: the structure of one repository's source, derived by
reading its files.

Every field here is traceable to something the analyzer actually observed. That
constraint is enforced structurally, not by convention:

* :class:`ArchitectureNode` carries ``evidence`` — the concrete signal that
  produced its ``kind``. A node is never labelled ``service`` because that reads
  well; it is labelled ``service`` because a rule matched, and the rule's output
  is attached.
* :class:`ArchitectureEdge` distinguishes ``internal`` (resolved to a module that
  exists in this repository) from ``external`` (resolved to a third-party
  package). An unresolved import produces *no edge at all* rather than a
  fabricated one, so a graph never implies a dependency that was not observed.
* :class:`ArchitectureSummary` reports ``unresolved_imports`` separately from
  the graph. Silently dropping them would make a partially-analysed repository
  look clean.
* Fields that could not be computed are ``None``, never ``0``. ``cycles=None``
  means "cycle detection did not run"; ``cycles=0`` means "it ran and found
  none". Collapsing the two would let a truncated scan read as a healthy
  architecture.

Determinism
-----------
Nothing in this module calls a model. Module identity, import resolution, node
classification, coupling, cycle detection and issue generation are all pure
functions of the file contents, so the same commit always yields the same graph.
The same repository content analysed twice produces identical output.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

#: Languages the analyzer can parse. Detection is by file extension, not by a
#: user-supplied claim, so a ``.py`` file is always parsed as Python.
ArchitectureLanguage = Literal["python", "javascript", "typescript"]

LANGUAGES: tuple[str, ...] = ("python", "javascript", "typescript")

#: What role a module plays. ``module`` is the fallback for a source file that
#: matched no stronger rule — it is a real observation ("this is a source file
#: with no detected role"), not a placeholder.
ArchitectureNodeKind = Literal[
    "module",
    "service",
    "route",
    "controller",
    "database",
    "external",
]

NODE_KINDS: tuple[str, ...] = (
    "module",
    "service",
    "route",
    "controller",
    "database",
    "external",
)

#: Whether an edge points at code inside this repository or at a third party.
ArchitectureEdgeKind = Literal["internal", "external"]

#: Structural defects the analyzer can actually detect from imports and file
#: size. Each is a deterministic measurement, not a judgement.
ArchitectureIssueKind = Literal[
    "circular_dependency",
    "high_coupling",
    "god_module",
    "oversized_module",
    "orphan_module",
    "external_hotspot",
]

ISSUE_KINDS: tuple[str, ...] = (
    "circular_dependency",
    "high_coupling",
    "god_module",
    "oversized_module",
    "orphan_module",
    "external_hotspot",
)

#: Issues are signals, not verdicts. Every one is a measurement a reviewer can
#: check and disagree with, which is why they are never severity-scored.
ISSUE_SEVERITIES: tuple[str, ...] = ("info", "warning")


def _forbid_extra() -> ConfigDict:
    return ConfigDict(extra="forbid", frozen=True)


class ArchitectureNode(BaseModel):
    """One vertex in the dependency graph.

    ``kind`` is only ever one of :data:`NODE_KINDS` and is always accompanied by
    the ``evidence`` that produced it, so a reader can audit the classification
    instead of trusting it.
    """

    model_config = _forbid_extra()

    #: Dotted/slash-separated logical name, unique within an analysis.
    id: str = Field(min_length=1, max_length=400)
    #: Human-facing short name, usually the file's basename without extension.
    name: str = Field(min_length=1, max_length=200)
    #: Repository-relative forward-slash path. Empty for external packages,
    #: which have no path in this repository.
    path: str = Field(default="", max_length=1000)
    language: ArchitectureLanguage | None = None
    kind: ArchitectureNodeKind = "module"
    #: Why this node was classified as it was. Empty for ``kind="module"``,
    #: which is the absence of a stronger match.
    evidence: str = Field(default="", max_length=300)
    #: Lines of code actually read. ``None`` when the file could not be read,
    #: which is different from a file that read as zero lines.
    line_count: int | None = Field(default=None, ge=0)
    #: Number of modules this one imports. Measured from resolved imports only.
    fan_out: int = Field(default=0, ge=0)
    #: Number of modules that import this one.
    fan_in: int = Field(default=0, ge=0)
    #: Whether the file was parsed successfully. A module that failed to parse is
    #: still listed — hiding it would understate the repository.
    parsed: bool = True


class ArchitectureEdge(BaseModel):
    """A directed import relationship.

    ``source`` is always a node in this repository. ``target`` is an ``id`` that
    is either another node (``kind="internal"``) or an external package
    (``kind="external"``, whose node has an empty ``path``).
    """

    model_config = _forbid_extra()

    source: str = Field(min_length=1, max_length=400)
    target: str = Field(min_length=1, max_length=400)
    kind: ArchitectureEdgeKind = "internal"
    #: The import statement as written, for display only. Never used for
    #: classification, because the same import string can mean different things
    #: in different files.
    reference: str = Field(default="", max_length=500)
    #: False when the import could not be resolved to a node in this repository.
    #: An unresolved import produces no edge, so this is currently always true —
    #: it is retained so a future partial-resolution mode can express itself
    #: without a breaking change.
    resolved: bool = True


class ArchitectureModule(BaseModel):
    """Flat inventory entry, ordered for display.

    One row per analysed source file, whether or not it has any edges. A module
    that imports nothing and is imported by nothing is still a real module and
    still belongs in an inventory.
    """

    model_config = _forbid_extra()

    id: str
    name: str
    path: str
    language: ArchitectureLanguage | None = None
    kind: ArchitectureNodeKind = "module"
    line_count: int | None = Field(default=None, ge=0)
    fan_in: int = Field(default=0, ge=0)
    fan_out: int = Field(default=0, ge=0)
    #: External packages this module imports.
    dependencies: list[str] = Field(default_factory=list)


class ArchitectureIssue(BaseModel):
    """A detected structural signal.

    ``severity`` is bounded to ``info``/``warning`` on purpose: these are
    measurements, and inflating them into ``critical``/``high`` would put them in
    the same vocabulary as security findings, where the numbers mean something
    different entirely.
    """

    model_config = _forbid_extra()

    kind: ArchitectureIssueKind
    severity: Literal["info", "warning"] = "info"
    #: Human-readable statement of what was measured.
    title: str = Field(min_length=1, max_length=300)
    #: The concrete numbers behind the claim, so it can be checked.
    detail: str = Field(default="", max_length=600)
    #: Node ids this issue concerns. A cycle lists every module in it.
    nodes: list[str] = Field(default_factory=list)


class ArchitectureSummary(BaseModel):
    """Aggregate view of one analysis.

    Fields that could not be computed are ``None`` rather than ``0``, so a
    truncated or failed analysis is distinguishable from a clean one.
    """

    model_config = _forbid_extra()

    total_modules: int = Field(default=0, ge=0)
    total_edges: int = Field(default=0, ge=0)
    internal_edges: int = Field(default=0, ge=0)
    external_edges: int = Field(default=0, ge=0)
    #: Module count per language actually detected.
    language_distribution: dict[str, int] = Field(default_factory=dict)
    #: Module count per :data:`NODE_KINDS` value.
    kind_distribution: dict[str, int] = Field(default_factory=dict)
    #: Distinct external packages imported anywhere in the repository.
    external_packages: int = Field(default=0, ge=0)
    #: Import statements that did not resolve to a module in this repository.
    #: Reported so a partial analysis cannot read as a complete one.
    unresolved_imports: int = Field(default=0, ge=0)
    #: Number of dependency cycles. ``None`` when detection did not complete.
    cycles: int | None = Field(default=None, ge=0)
    #: Number of distinct cycle groups. ``None`` alongside ``cycles=None``.
    cycle_groups: int | None = Field(default=None, ge=0)
    #: Modules with the most dependents.
    most_depended_on: list[str] = Field(default_factory=list)
    #: Modules that import the most other modules.
    most_dependent: list[str] = Field(default_factory=list)
    total_lines: int = Field(default=0, ge=0)
    #: Statement describing exactly what was and was not analysed.
    methodology: str = Field(default="", max_length=800)


class ArchitectureGraph(BaseModel):
    """The full result of one architecture analysis."""

    model_config = _forbid_extra()

    repository_id: str = Field(min_length=1, max_length=300)
    owner: str = Field(min_length=1, max_length=200)
    repository: str = Field(min_length=1, max_length=200)
    full_name: str = Field(min_length=1, max_length=300)
    provider: str = Field(default="github", max_length=32)
    ref: str | None = None
    commit_sha: str | None = None
    analyzed_at: str = Field(min_length=1, max_length=64)
    duration_ms: int = Field(default=0, ge=0)
    nodes: list[ArchitectureNode] = Field(default_factory=list)
    edges: list[ArchitectureEdge] = Field(default_factory=list)
    modules: list[ArchitectureModule] = Field(default_factory=list)
    issues: list[ArchitectureIssue] = Field(default_factory=list)
    summary: ArchitectureSummary = Field(default_factory=ArchitectureSummary)
    #: Files that could not be read or parsed, as ``path: reason`` strings.
    #: Truncated to keep the response bounded.
    errors: list[str] = Field(default_factory=list)
    #: True when file selection hit its cap and the graph is therefore partial.
    truncated: bool = False

    @field_validator("nodes", "edges", "modules", "issues", "errors")
    @classmethod
    def _bound_lists(cls, value: list[Any]) -> list[Any]:
        # Defence in depth: the service caps these, and a model-level bound
        # means a future caller cannot construct an unbounded response.
        if len(value) > 20000:
            raise ValueError("architecture payload exceeds 20000 entries")
        return value


#: What the analyzer is and is not able to see. Returned in every response so the
#: page can state its own coverage rather than implying completeness.
ARCHITECTURE_METHODOLOGY = (
    "Deterministic static analysis of the repository's own source. Python is "
    "parsed with the standard-library ast module; JavaScript and TypeScript are "
    "parsed with import-statement rules. No model contributes to module "
    "identity, import resolution, classification, coupling, cycle detection or "
    "issue generation. Dynamic imports, reflection, runtime-constructed imports, "
    "and dependencies inside vendored or generated directories are not resolved "
    "and are reported as unresolved rather than guessed."
)
