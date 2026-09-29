"""Deterministic architecture analysis.

Everything in this module is a pure function of the parsed modules produced by
:mod:`app.services.architecture_parser`. No I/O, no model, no clock, no randomness.
That is what makes the graph reproducible: analysing the same commit twice yields
byte-identical output, which is the property a code-structure view needs in order
to be diffable across runs.

The three analytical stages
---------------------------
1. **Classification.** Each module is assigned a ``kind`` from an ordered rule
   list. The first matching rule wins and its output is stored as ``evidence``,
   so every classification is auditable rather than asserted.
2. **Metrics.** Fan-in, fan-out, total coupling and per-module size are counted
   from the resolved edge set. Nothing is estimated.
3. **Structure.** Cycles are found with an iterative Tarjan SCC pass, and issues
   are emitted from explicit numeric thresholds recorded in this module.

Honesty constraints
-------------------
* A module that matched no rule is ``kind="module"`` with empty ``evidence``.
  That is an observation ("no detected role"), not a default that hides a gap.
* Cycles are ``None`` when the analysis did not run to completion, never ``0``.
* The JSON path is analysed too, because a backend importing ``schemas/security``
  has a real dependency on it. A module therefore may be both a service and a
  target of other modules' imports.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from app.schemas.architecture import (
    ARCHITECTURE_METHODOLOGY,
    ArchitectureEdge,
    ArchitectureIssue,
    ArchitectureModule,
    ArchitectureNode,
    ArchitectureSummary,
)
from app.services.architecture_parser import ParsedModule, ResolutionResult

# --------------------------------------------------------------------------
# Thresholds. Every one is a stated constant, not a magic number at a call site,
# so a reviewer can see the whole policy for "what counts as a problem" in one
# place and disagree with it in one place.
# --------------------------------------------------------------------------

#: fan-out at or above this makes a module a coupling hotspot.
COUPLING_FAN_OUT_THRESHOLD = 15

#: fan-in at or above this makes a module widely depended upon.
COUPLING_FAN_IN_THRESHOLD = 15

#: A module at or above this line count is reported as oversized. A thousand
#: lines of generated-looking repetition is less reviewable than a thousand lines
#: of dense logic, but line count is the one size signal available without
#: semantic analysis, so it is stated as a signal rather than a verdict.
OVERSIZED_MODULE_LINES = 1200

#: fan-in, fan-out and size must *all* exceed these for a god-module report.
GOD_MODULE_FAN_IN = 20
GOD_MODULE_FAN_OUT = 20
GOD_MODULE_LINES = 800

#: How many modules appear in the summary's most-connected lists.
TOP_CONNECTED_LIMIT = 10

#: Most external packages listed in the summary.
TOP_EXTERNAL_LIMIT = 15

#: Maximum nodes a cycle issue will enumerate before summarising.
MAX_CYCLE_NODES_SHOWN = 12


# --------------------------------------------------------------------------
# Classification
# --------------------------------------------------------------------------

#: Path fragments that mark a module as an HTTP entry point. Matched
#: case-insensitively against the module id.
_ROUTE_FRAGMENTS = (
    "routers",
    "routes",
    "api",
    "controller",
    "handlers",
    "endpoints",
    "views",
    "blueprints",
)

#: Path fragments that mark a module as business/service logic.
_SERVICE_FRAGMENTS = ("services", "service", "usecases", "domain", "logic")

#: Fragments that mark a module as a persistence adapter.
_DATABASE_FRAGMENTS = (
    "repository",
    "repositories",
    "models",
    "dao",
    "persistence",
    "store",
    "db",
    "database",
)

#: Role words checked against the module's own *name* before the full path is
#: considered. A persistence module called ``security_repository.py`` lives under
#: ``services/`` in most FastAPI projects, so testing the directory first would
#: label every repository module a "service" and hide the data layer entirely.
#: The filename is the more specific signal and therefore the more reliable one.
_NAME_ROLE_FRAGMENTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("database", _DATABASE_FRAGMENTS),
    ("route", _ROUTE_FRAGMENTS),
    ("service", _SERVICE_FRAGMENTS),
)

#: A module that both accepts requests and does work is a controller. Detected
#: as "a route module that also reaches into a data layer", which is a shape a
#: reviewer can check against the file.
_CONTROLLER_ROUTE_FRAGMENTS = ("routers", "routes", "controllers", "api", "views")


def _has_fragment(module_id: str, fragments: Sequence[str]) -> str:
    """First fragment contained in the module id, lowercased. Empty if none."""
    lowered = module_id.lower()
    for fragment in fragments:
        if fragment in lowered:
            return fragment
    return ""


def classify_module(module: ParsedModule, resolution: ResolutionResult) -> tuple[str, str]:
    """Return ``(kind, evidence)`` for one module.

    Tested most-specific-first: the module's own name, then its full dotted path.
    ``evidence`` is a short, human-checkable statement of *why* — the fragment
    that matched, or the concrete import that triggered the rule.
    """
    module_id = module.name.lower()
    short_name = module_id.rsplit(".", 1)[-1].rsplit("/", 1)[-1]

    for kind, fragments in _NAME_ROLE_FRAGMENTS:
        fragment = _has_fragment(short_name, fragments)
        if fragment:
            return kind, f"module name contains '{fragment}'"

    route_fragment = _has_fragment(module_id, _ROUTE_FRAGMENTS)
    if route_fragment:
        # A route that also depends on a data layer is a controller.
        internal_targets = {
            target
            for source, target, _ in resolution.internal_edges
            if source == module.name
        }
        touches_data = any(
            _has_fragment(target, _DATABASE_FRAGMENTS) for target in internal_targets
        )
        if touches_data and _has_fragment(module_id, _CONTROLLER_ROUTE_FRAGMENTS):
            return (
                "controller",
                f"route module ('{route_fragment}') that imports a data layer directly",
            )
        return "route", f"path contains '{route_fragment}'"

    for kind, fragments in (("service", _SERVICE_FRAGMENTS), ("database", _DATABASE_FRAGMENTS)):
        fragment = _has_fragment(module_id, fragments)
        if fragment:
            return kind, f"path contains '{fragment}'"

    return "module", ""


def _external_nodes(resolution: ResolutionResult) -> dict[str, int]:
    """External package name → number of modules importing it."""
    counts: dict[str, int] = {}
    for _source, package in resolution.external_edges:
        counts[package] = counts.get(package, 0) + 1
    return counts


# --------------------------------------------------------------------------
# Structure: cycle detection
# --------------------------------------------------------------------------

def find_cycles(module_ids: Iterable[str], edges: Iterable[tuple[str, str]]) -> list[list[str]]:
    """Strongly connected components of size > 1, plus explicit self-loops.

    Iterative Tarjan. The graph can be deep — a chain of a few hundred modules is
    ordinary — and a recursive implementation would risk ``RecursionError`` on
    hostile input, so the traversal keeps its own explicit stack.

    Each returned component is a *cycle* in the meaningful sense: every member
    reaches every other. A component of size one is excluded unless the module
    imports itself, because a lone node is not a cycle.

    Output is sorted, so the result is stable across runs.
    """
    nodes = sorted(set(module_ids))
    known = set(nodes)
    adjacency: dict[str, list[str]] = {node: [] for node in nodes}
    for source, target in edges:
        if source in known and target in known and source != target:
            adjacency[source].append(target)

    index_of: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    result: list[list[str]] = []
    counter = 0

    for root in nodes:
        if root in index_of:
            continue
        # (node, iterator position into its adjacency list)
        work: list[tuple[str, int]] = [(root, 0)]
        while work:
            node, position = work[-1]
            if position == 0:
                index_of[node] = counter
                lowlink[node] = counter
                counter += 1
                stack.append(node)
                on_stack.add(node)

            descended = False
            neighbours = adjacency[node]
            while position < len(neighbours):
                neighbour = neighbours[position]
                position += 1
                if neighbour not in index_of:
                    work[-1] = (node, position)
                    work.append((neighbour, 0))
                    descended = True
                    break
                if neighbour in on_stack:
                    lowlink[node] = min(lowlink[node], index_of[neighbour])
            if descended:
                continue

            work[-1] = (node, position)
            if lowlink[node] == index_of[node]:
                component: list[str] = []
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    component.append(member)
                    if member == node:
                        break
                if len(component) > 1:
                    result.append(sorted(component))
            work.pop()
            if work:
                parent, _ = work[-1]
                lowlink[parent] = min(lowlink[parent], lowlink[node])

    # A module importing itself is a real, if degenerate, cycle.
    for source, target in edges:
        if source == target and source in known and [source] not in result:
            result.append([source])

    return sorted(result)


# --------------------------------------------------------------------------
# Assembly
# --------------------------------------------------------------------------

def build_analysis(resolution: ResolutionResult) -> tuple[
    list[ArchitectureNode],
    list[ArchitectureEdge],
    list[ArchitectureModule],
    list[ArchitectureIssue],
    ArchitectureSummary,
]:
    """Turn resolved imports into the full architecture payload.

    The five return values are the graph, the edge list, the flat inventory, the
    issues and the summary. They are returned separately rather than bundled so
    the caller can persist the cheap parts and stream the expensive ones.
    """
    modules = resolution.modules
    if not modules:
        # Cycle detection genuinely ran, over an empty graph, and found nothing.
        # Reporting ``None`` here would claim the check was skipped, which is a
        # different and less useful statement.
        return (
            [],
            [],
            [],
            [],
            ArchitectureSummary(cycles=0, cycle_groups=0, methodology=ARCHITECTURE_METHODOLOGY),
        )

    # ---- metrics -----------------------------------------------------------
    fan_out: dict[str, int] = {name: 0 for name in modules}
    fan_in: dict[str, int] = {name: 0 for name in modules}
    outgoing: dict[str, list[str]] = {name: [] for name in modules}

    internal_edges: list[ArchitectureEdge] = []
    for source, target, reference in resolution.internal_edges:
        if source not in modules or target not in modules:
            continue
        internal_edges.append(
            ArchitectureEdge(source=source, target=target, kind="internal", reference=reference)
        )
        fan_out[source] += 1
        fan_in[target] += 1
        outgoing[source].append(target)

    external_packages: dict[str, list[str]] = {}
    for source, package in resolution.external_edges:
        external_packages.setdefault(package, []).append(source)
    external_edges = [
        ArchitectureEdge(
            source=source,
            target=f"external:{package}",
            kind="external",
            reference=package,
        )
        for source, package in sorted(resolution.external_edges)
    ]

    # ---- nodes -------------------------------------------------------------
    nodes: list[ArchitectureNode] = []
    inventory: list[ArchitectureModule] = []
    kind_counts: dict[str, int] = {}
    language_counts: dict[str, int] = {}
    total_lines = 0

    for name in sorted(modules):
        module = modules[name]
        kind, evidence = classify_module(module, resolution)
        kind_counts[kind] = kind_counts.get(kind, 0) + 1
        if module.language:
            language_counts[module.language] = language_counts.get(module.language, 0) + 1
        if module.line_count:
            total_lines += module.line_count

        nodes.append(
            ArchitectureNode(
                id=name,
                name=module.path.rsplit("/", 1)[-1] or name,
                path=module.path,
                language=module.language,
                kind=kind,
                evidence=evidence,
                line_count=module.line_count,
                fan_out=fan_out[name],
                fan_in=fan_in[name],
                parsed=module.parsed,
            )
        )
        inventory.append(
            ArchitectureModule(
                id=name,
                name=module.path.rsplit("/", 1)[-1] or name,
                path=module.path,
                language=module.language,
                kind=kind,
                line_count=module.line_count,
                fan_in=fan_in[name],
                fan_out=fan_out[name],
                dependencies=sorted(set(outgoing.get(name, [])).intersection(modules)),
            )
        )

    # One node per distinct external package, so the graph can show it.
    for package, importers in sorted(external_packages.items()):
        kind_counts["external"] = kind_counts.get("external", 0) + 1
        nodes.append(
            ArchitectureNode(
                id=f"external:{package}",
                name=package,
                path="",
                kind="external",
                evidence=f"imported by {len(importers)} module(s)",
                fan_in=len(importers),
            )
        )

    # ---- structure ---------------------------------------------------------
    cycles = find_cycles(
        modules.keys(), [(source, target) for source, target, _ in resolution.internal_edges]
    )
    issues = _build_issues(modules, cycles, fan_in, fan_out, external_packages)

    # ---- summary -----------------------------------------------------------
    by_dependents = sorted(modules, key=lambda name: (-fan_in[name], name))
    by_dependencies = sorted(modules, key=lambda name: (-fan_out[name], name))

    summary = ArchitectureSummary(
        total_modules=len(modules),
        total_edges=len(internal_edges) + len(external_edges),
        internal_edges=len(internal_edges),
        external_edges=len(external_edges),
        language_distribution=dict(sorted(language_counts.items())),
        kind_distribution=dict(sorted(kind_counts.items())),
        external_packages=len(external_packages),
        unresolved_imports=len(resolution.unresolved),
        cycles=len(cycles),
        cycle_groups=len(cycles),
        most_depended_on=[
            name for name in by_dependents[:TOP_CONNECTED_LIMIT] if fan_in[name] > 0
        ],
        most_dependent=[
            name for name in by_dependencies[:TOP_CONNECTED_LIMIT] if fan_out[name] > 0
        ],
        total_lines=total_lines,
        methodology=ARCHITECTURE_METHODOLOGY,
    )

    return (
        sorted(nodes, key=lambda node: node.id),
        sorted(internal_edges + external_edges, key=lambda edge: (edge.source, edge.target)),
        sorted(inventory, key=lambda item: item.id),
        issues,
        summary,
    )


def _build_issues(
    modules: dict[str, ParsedModule],
    cycles: list[list[str]],
    fan_in: dict[str, int],
    fan_out: dict[str, int],
    external_packages: dict[str, list[str]],
) -> list[ArchitectureIssue]:
    """Emit structural issues from the stated thresholds.

    Every issue carries the numbers behind it, so a reviewer can check the claim
    and disagree. Nothing here is severity-scored: these are measurements, and
    putting them on the same scale as security findings would imply a precision
    the analysis does not have.
    """
    issues: list[ArchitectureIssue] = []

    for cycle in cycles:
        shown = cycle[:MAX_CYCLE_NODES_SHOWN]
        hidden = len(cycle) - len(shown)
        listing = ", ".join(shown) + (f" (+{hidden} more)" if hidden else "")
        issues.append(
            ArchitectureIssue(
                kind="circular_dependency",
                severity="warning",
                title=f"Circular dependency across {len(cycle)} module(s)",
                detail=(
                    f"Every module in this group imports, directly or transitively, "
                    f"every other. Modules: {listing}."
                ),
                nodes=list(cycle),
            )
        )

    for name in sorted(modules):
        module = modules[name]
        lines = module.line_count or 0

        if fan_out[name] >= COUPLING_FAN_OUT_THRESHOLD:
            issues.append(
                ArchitectureIssue(
                    kind="high_coupling",
                    severity="warning",
                    title=f"'{name}' imports {fan_out[name]} modules",
                    detail=(
                        f"Fan-out is at or above the {COUPLING_FAN_OUT_THRESHOLD}-module "
                        f"threshold, so a change here can affect {fan_out[name]} "
                        f"dependencies at once."
                    ),
                    nodes=[name],
                )
            )

        if lines >= OVERSIZED_MODULE_LINES:
            issues.append(
                ArchitectureIssue(
                    kind="oversized_module",
                    severity="info",
                    title=f"'{name}' is {lines} lines",
                    detail=(
                        f"At or above the {OVERSIZED_MODULE_LINES}-line threshold for a "
                        f"single module."
                    ),
                    nodes=[name],
                )
            )

        if (
            fan_in[name] >= GOD_MODULE_FAN_IN
            and fan_out[name] >= GOD_MODULE_FAN_OUT
            and lines >= GOD_MODULE_LINES
        ):
            issues.append(
                ArchitectureIssue(
                    kind="god_module",
                    severity="warning",
                    title=f"'{name}' is widely depended on and widely dependent",
                    detail=(
                        f"{fan_in[name]} modules import it, it imports {fan_out[name]} "
                        f"modules, and it is {lines} lines. All three thresholds are "
                        f"exceeded, which usually means several responsibilities share "
                        f"one file."
                    ),
                    nodes=[name],
                )
            )

        if fan_in[name] == 0 and fan_out[name] == 0 and lines >= 50:
            issues.append(
                ArchitectureIssue(
                    kind="orphan_module",
                    severity="info",
                    title=f"'{name}' is not connected to any other module",
                    detail=(
                        f"{lines} lines, no detected imports and no detected importers "
                        f"within the analysed set."
                    ),
                    nodes=[name],
                )
            )

    for package, importers in sorted(external_packages.items()):
        if len(importers) >= COUPLING_FAN_IN_THRESHOLD:
            issues.append(
                ArchitectureIssue(
                    kind="external_hotspot",
                    severity="info",
                    title=f"{len(importers)} modules import '{package}'",
                    detail=(
                        f"A single third-party package is used across "
                        f"{len(importers)} modules, so its behaviour affects all of them."
                    ),
                    nodes=sorted(importers)[:MAX_CYCLE_NODES_SHOWN],
                )
            )

    # Stable ordering: kind, then title, so the same analysis always lists
    # issues in the same order.
    return sorted(issues, key=lambda issue: (issue.kind, issue.title))
