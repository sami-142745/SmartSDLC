"""Tests for deterministic architecture analysis.

Covers classification, coupling metrics, cycle detection and issue generation.
The recurring theme is the honesty constraint: the analysis must never report a
structure it did not observe, and must never report "clean" when it could not
look.
"""

from __future__ import annotations

import pytest

from app.schemas.architecture import ArchitectureSummary
from app.services import architecture_analysis as analysis
from app.services import architecture_parser as parser


def _analyse(files: dict[str, str]):
    """Parse and resolve a file map, then build the analysis payload."""
    modules = [parser.parse_module(path, content) for path, content in files.items()]
    resolution = parser.resolve(modules)
    return analysis.build_analysis(resolution)


def _serialise(parts) -> list:
    """JSON-comparable form of the five analysis parts, for equality assertions."""
    serialised = []
    for part in parts:
        if isinstance(part, list):
            serialised.append([item.model_dump() for item in part])
        else:
            serialised.append(part.model_dump())
    return serialised


def _node_by_id(nodes, node_id):
    return next(node for node in nodes if node.id == node_id)


def _issue_kinds(issues):
    return [issue.kind for issue in issues]


class TestClassification:
    def test_a_router_path_is_a_route(self):
        _nodes, _edges, _modules, _issues, _summary = _analyse(
            {"app/routers/security.py": ""}
        )
        assert _node_by_id(_nodes, "app.routers.security").kind == "route"

    def test_a_service_path_is_a_service(self):
        _nodes, *_ = _analyse({"app/services/scan.py": ""})
        node = _node_by_id(_nodes, "app.services.scan")
        assert node.kind == "service"
        assert "service" in node.evidence

    def test_a_repository_module_is_a_database_node_even_under_services(self):
        # Most FastAPI projects put persistence under ``services/``, so testing
        # the directory first would label every repository a "service" and hide
        # the data layer from the graph entirely.
        _nodes, *_ = _analyse({"app/services/repository.py": ""})
        node = _node_by_id(_nodes, "app.services.repository")
        assert node.kind == "database"
        assert "repository" in node.evidence

    def test_a_specific_repository_name_wins_over_a_generic_service_directory(self):
        _nodes, *_ = _analyse({"app/services/ai_review_repository.py": ""})
        assert _node_by_id(_nodes, "app.services.ai_review_repository").kind == "database"

    def test_a_service_without_a_role_word_stays_a_service(self):
        _nodes, *_ = _analyse({"app/services/scanner.py": ""})
        assert _node_by_id(_nodes, "app.services.scanner").kind == "service"

    def test_a_route_that_imports_a_data_layer_is_a_controller(self):
        # This is a shape a reviewer can check against the file, not a guess.
        _nodes, *_ = _analyse(
            {
                "app/routers/orders.py": "from app.services.order_repository import save\n",
                "app/services/order_repository.py": "",
            }
        )
        node = _node_by_id(_nodes, "app.routers.orders")
        assert node.kind == "controller"
        assert "data layer" in node.evidence

    def test_a_route_with_no_data_access_stays_a_route(self):
        _nodes, *_ = _analyse(
            {
                "app/routers/orders.py": "from app.services.orders import list_all\n",
                "app/services/orders.py": "",
            }
        )
        assert _node_by_id(_nodes, "app.routers.orders").kind == "route"

    def test_an_unmatched_file_is_a_plain_module_with_no_evidence(self):
        # Absence of a match is an observation, and saying so is more honest
        # than inventing a role.
        _nodes, *_ = _analyse({"pkg/helper.py": ""})
        node = _node_by_id(_nodes, "pkg.helper")
        assert node.kind == "module"
        assert node.evidence == ""

    def test_classification_is_case_insensitive_on_path_fragments(self):
        _nodes, *_ = _analyse({"app/Services/Thing.py": ""})
        assert _node_by_id(_nodes, "app.Services.Thing").kind == "service"


class TestMetrics:
    def test_fan_out_counts_resolved_imports(self):
        _nodes, *_ = _analyse(
            {
                "a/b.py": "from a.c import x\nfrom a.d import y\n",
                "a/c.py": "",
                "a/d.py": "",
            }
        )
        assert _node_by_id(_nodes, "a.b").fan_out == 2

    def test_fan_in_counts_importers(self):
        _nodes, *_ = _analyse(
            {
                "a/b.py": "from a.c import x\n",
                "a/d.py": "from a.c import y\n",
                "a/c.py": "",
            }
        )
        assert _node_by_id(_nodes, "a.c").fan_in == 2

    def test_unresolved_imports_do_not_count_as_coupling(self):
        # Counting a guess would inflate fan-out with a dependency that does not
        # exist.
        _nodes, _edges, _modules, _issues, summary = _analyse(
            {"a/b.py": "from a.missing import x\n"}
        )
        assert _node_by_id(_nodes, "a.b").fan_out == 0
        assert _edges == []
        assert summary.unresolved_imports == 1

    def test_duplicate_imports_of_one_target_count_once(self):
        _nodes, *_ = _analyse(
            {"a/b.py": "from a.c import x\nimport a.c\n", "a/c.py": ""}
        )
        assert _node_by_id(_nodes, "a.b").fan_out == 1

    def test_third_party_imports_are_external_edges_not_fan_out(self):
        _nodes, _edges, _modules, _issues, summary = _analyse(
            {"a/b.py": "import fastapi\nimport os\n"}
        )
        node = _node_by_id(_nodes, "a.b")
        assert node.fan_out == 0
        assert summary.external_edges == 1
        assert summary.external_packages == 1

    def test_external_packages_become_their_own_nodes(self):
        _nodes, *_ = _analyse({"a/b.ts": "import axios from 'axios';\n"})
        node = _node_by_id(_nodes, "external:axios")
        assert node.kind == "external"
        assert node.path == ""
        assert node.fan_in == 1

    def test_total_lines_sums_read_files(self):
        _nodes, _edges, _modules, _issues, summary = _analyse(
            {"a/b.py": "x = 1\ny = 2\n", "a/c.py": "z = 3\n"}
        )
        assert summary.total_lines == 3

    def test_language_distribution_counts_detected_languages(self):
        _nodes, _edges, _modules, _issues, summary = _analyse(
            {"a/b.py": "", "a/c.ts": "", "a/d.tsx": "", "a/e.js": ""}
        )
        assert summary.language_distribution == {
            "python": 1,
            "javascript": 1,
            "typescript": 2,
        }

    def test_most_depended_on_and_most_dependent_exclude_unconnected(self):
        _nodes, _edges, _modules, _issues, summary = _analyse(
            {
                "a/hub.py": "",
                "a/one.py": "from a.hub import x\n",
                "a/two.py": "from a.hub import y\n",
                "a/lonely.py": "x = 1\n" * 5,
            }
        )
        assert "a.hub" in summary.most_depended_on
        assert "a.lonely" not in summary.most_depended_on
        assert "a.one" in summary.most_dependent
        assert "a.lonely" not in summary.most_dependent


class TestCycleDetection:
    def test_a_two_module_cycle_is_found(self):
        cycles = analysis.find_cycles(["a", "b"], [("a", "b"), ("b", "a")])
        assert cycles == [["a", "b"]]

    def test_a_three_module_cycle_is_found(self):
        cycles = analysis.find_cycles(
            ["a", "b", "c"], [("a", "b"), ("b", "c"), ("c", "a")]
        )
        assert cycles == [["a", "b", "c"]]

    def test_a_longer_cycle_is_found(self):
        nodes = ["a", "b", "c", "d"]
        edges = [("a", "b"), ("b", "c"), ("c", "d"), ("d", "a")]
        assert analysis.find_cycles(nodes, edges) == [["a", "b", "c", "d"]]

    def test_an_acyclic_chain_has_no_cycles(self):
        assert analysis.find_cycles(["a", "b", "c"], [("a", "b"), ("b", "c")]) == []

    def test_a_diamond_is_not_a_cycle(self):
        # Two paths to the same node is not mutual dependency.
        cycles = analysis.find_cycles(
            ["a", "b", "c", "d"], [("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")]
        )
        assert cycles == []

    def test_a_self_import_is_a_cycle(self):
        assert analysis.find_cycles(["a"], [("a", "a")]) == [["a"]]

    def test_two_independent_cycles_are_reported_separately(self):
        cycles = analysis.find_cycles(
            ["a", "b", "c", "d"],
            [("a", "b"), ("b", "a"), ("c", "d"), ("d", "c")],
        )
        assert cycles == [["a", "b"], ["c", "d"]]

    def test_a_deep_chain_does_not_exhaust_the_stack(self):
        # A recursive Tarjan would risk RecursionError on a deep chain, which is
        # reachable from untrusted repository content.
        size = 6000
        nodes = [f"m{i}" for i in range(size)]
        edges = [(f"m{i}", f"m{i + 1}") for i in range(size - 1)]
        assert analysis.find_cycles(nodes, edges) == []

    def test_cycles_survive_a_self_loop_in_a_large_graph(self):
        nodes = [f"m{i}" for i in range(3000)]
        edges = [(f"m{i}", f"m{i + 1}") for i in range(2999)] + [("m0", "m0")]
        assert analysis.find_cycles(nodes, edges) == [["m0"]]

    def test_output_is_sorted_and_deterministic(self):
        edges = [("c", "a"), ("a", "b"), ("b", "c"), ("e", "d"), ("d", "e")]
        first = analysis.find_cycles(["a", "b", "c", "d", "e"], edges)
        second = analysis.find_cycles(["e", "d", "c", "b", "a"], list(reversed(edges)))
        assert first == second == [["a", "b", "c"], ["d", "e"]]

    def test_edges_to_unknown_nodes_are_ignored(self):
        assert analysis.find_cycles(["a"], [("a", "ghost")]) == []


class TestCycleIssues:
    def test_a_cycle_produces_a_warning_naming_every_module(self):
        _nodes, _edges, _modules, issues, summary = _analyse(
            {"a/x.py": "from a.y import p\n", "a/y.py": "from a.x import q\n"}
        )
        assert summary.cycles == 1
        cycle = next(i for i in issues if i.kind == "circular_dependency")
        assert cycle.severity == "warning"
        assert sorted(cycle.nodes) == ["a.x", "a.y"]

    def test_a_clean_graph_reports_zero_cycles_not_none(self):
        _nodes, _edges, _modules, _issues, summary = _analyse(
            {"a/x.py": "from a.y import p\n", "a/y.py": ""}
        )
        # Zero means "looked and found none", which is different from None.
        assert summary.cycles == 0
        assert summary.cycle_groups == 0

    def test_cycle_issue_truncates_a_long_member_list(self):
        files = {f"a/m{i}.py": f"from a.m{(i + 1) % 20} import x\n" for i in range(20)}
        _nodes, _edges, _modules, issues, _summary = _analyse(files)
        cycle = next(i for i in issues if i.kind == "circular_dependency")
        assert len(cycle.nodes) == 20
        assert "more)" in cycle.detail


class TestCouplingAndSizeIssues:
    def test_high_fan_out_is_reported_with_the_threshold_in_the_detail(self):
        imports = "\n".join(f"from a.m{i} import x" for i in range(20))
        files = {f"a/m{i}.py": "" for i in range(20)}
        files["a/big.py"] = imports
        _nodes, _edges, _modules, issues, _summary = _analyse(files)
        issue = next(i for i in issues if i.kind == "high_coupling")
        assert issue.severity == "warning"
        assert str(analysis.COUPLING_FAN_OUT_THRESHOLD) in issue.detail

    def test_a_module_below_the_threshold_is_not_reported(self):
        imports = "\n".join(f"from a.m{i} import x" for i in range(3))
        files = {f"a/m{i}.py": "" for i in range(3)}
        files["a/small.py"] = imports
        _nodes, _edges, _modules, issues, _summary = _analyse(files)
        assert "high_coupling" not in _issue_kinds(issues)

    def test_an_oversized_module_is_reported_as_info_not_a_warning(self):
        # Line count is a signal, not a defect, so it must not read as alarming.
        _nodes, _edges, _modules, issues, _summary = _analyse(
            {"a/huge.py": "x = 1\n" * (analysis.OVERSIZED_MODULE_LINES + 10)}
        )
        issue = next(i for i in issues if i.kind == "oversized_module")
        assert issue.severity == "info"

    def test_an_orphan_module_is_reported(self):
        _nodes, _edges, _modules, issues, _summary = _analyse(
            {"a/lonely.py": "x = 1\n" * 60}
        )
        assert "orphan_module" in _issue_kinds(issues)

    def test_a_tiny_unconnected_file_is_not_an_orphan_issue(self):
        # Flagging a two-line constant as an orphan is noise.
        _nodes, _edges, _modules, issues, _summary = _analyse({"a/x.py": "X = 1\n"})
        assert "orphan_module" not in _issue_kinds(issues)

    def test_a_god_module_needs_all_three_conditions(self):
        # Wide fan-in, wide fan-out and a large body. Building a file that
        # clears every bar is the only way this issue can appear, so the
        # positive case also proves the thresholds are reachable.
        big = "value = 1\n" * analysis.GOD_MODULE_LINES
        files = {"a/god.py": big}
        files["a/god.py"] = "".join(
            f"from a.p{i} import y\n" for i in range(analysis.GOD_MODULE_FAN_OUT + 2)
        ) + big
        for index in range(analysis.GOD_MODULE_FAN_IN + 2):
            files[f"a/p{index}.py"] = "from a.god import value\n"
        _nodes, _edges, _modules, issues, _summary = _analyse(files)
        assert "god_module" in _issue_kinds(issues)

    def test_a_module_missing_one_condition_is_not_a_god_module(self):
        # Large and widely depended on, but imports almost nothing. Reporting
        # this as a god module would be a false positive.
        big = "value = 1\n" * analysis.GOD_MODULE_LINES
        files = {"a/god.py": big}
        for index in range(analysis.GOD_MODULE_FAN_IN + 2):
            files[f"a/p{index}.py"] = "from a.god import value\n"
        _nodes, _edges, _modules, issues, _summary = _analyse(files)
        assert "god_module" not in _issue_kinds(issues)

    def test_a_widely_imported_external_package_is_a_hotspot(self):
        importers = "".join(f"import axios from 'axios';\n" for _ in range(1))
        files = {f"a/m{i}.ts": importers for i in range(analysis.COUPLING_FAN_IN_THRESHOLD + 5)}
        _nodes, _edges, _modules, issues, _summary = _analyse(files)
        hotspot = next(i for i in issues if i.kind == "external_hotspot")
        assert "axios" in hotspot.title

    def test_issues_are_sorted_so_output_is_stable(self):
        files = {
            "a/z.py": "from a.missing import x\n" * 1 + "x = 1\n" * 1300,
            "a/big.py": "y = 1\n" * 1300,
        }
        _nodes, _edges, _modules, first, _summary = _analyse(files)
        _nodes2, _edges2, _modules2, second, _summary2 = _analyse(dict(reversed(list(files.items()))))
        assert [i.title for i in first] == [i.title for i in second]


class TestSummaryAndEmptyInputs:
    def test_an_empty_repository_produces_an_empty_but_valid_graph(self):
        _nodes, _edges, _modules, issues, summary = _analyse({})
        assert (_nodes, _edges, _modules, issues) == ([], [], [], [])
        assert summary.total_modules == 0
        assert summary.cycles == 0
        assert summary.methodology

    def test_the_methodology_states_what_was_not_analysed(self):
        # The page must be able to state its own limits.
        _nodes, _edges, _modules, _issues, summary = _analyse({"a/b.py": ""})
        assert "ast" in summary.methodology
        assert "No model" in summary.methodology
        assert "unresolved rather than guessed" in summary.methodology

    def test_a_summary_can_be_constructed_with_no_cycles_measurement(self):
        # None must remain expressible: it means "not measured", not "zero".
        assert ArchitectureSummary(cycles=None, cycle_groups=None).cycles is None

    def test_kind_distribution_accounts_for_every_node(self):
        _nodes, _edges, _modules, _issues, summary = _analyse(
            {
                "app/routers/r.py": "",
                "app/services/s.py": "",
                "app/services/repository.py": "",
                "app/util.py": "",
                "a/t.ts": "import axios from 'axios';\n",
            }
        )
        assert sum(summary.kind_distribution.values()) == len(_nodes)
        assert summary.kind_distribution["external"] == 1


class TestDeterminism:
    def test_the_same_files_always_produce_the_same_analysis(self):
        files = {
            "app/routers/security.py": "from app.services.scan import run\nimport fastapi\n",
            "app/services/scan.py": "from app.services.repository import save\n",
            "app/services/repository.py": "from motor import x\n",
            "src/api/a.ts": "import axios from 'axios';\nimport './b';\n",
            "src/api/b.ts": "export const b = 1;\n",
        }
        first = _analyse(files)
        second = _analyse(files)
        assert _serialise(first) == _serialise(second)

    def test_input_order_does_not_change_the_result(self):
        files = {
            "app/routers/security.py": "from app.services.scan import run\n",
            "app/services/scan.py": "from app.services.repository import save\n",
            "app/services/repository.py": "",
        }
        forward = _analyse(files)
        backward = _analyse(dict(reversed(list(files.items()))))
        assert _serialise(forward) == _serialise(backward)

    def test_every_payload_part_is_sorted(self):
        files = {"a/z.py": "from a.y import x\n", "a/y.py": "from a.x import x\n", "a/x.py": ""}
        nodes, edges, modules, issues, _summary = _analyse(files)
        assert [n.id for n in nodes] == sorted(n.id for n in nodes)
        assert [(e.source, e.target) for e in edges] == sorted(
            (e.source, e.target) for e in edges
        )
        assert [m.id for m in modules] == sorted(m.id for m in modules)
        assert [(i.kind, i.title) for i in issues] == sorted(
            (i.kind, i.title) for i in issues
        )
