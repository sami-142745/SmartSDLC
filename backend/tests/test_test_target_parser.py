"""Tests for deterministic test-target discovery.

The contract under test is that a target is a reproducible fact about the
repository: the same files always produce the same ranked list, a symbol a test
mentions is never proposed, and a file that cannot be parsed is reported rather
than silently treated as having no public API.
"""

from __future__ import annotations

import pytest

from app.services.test_target_parser import (
    RepositoryFile,
    detect_framework,
    find_test_targets,
    is_source_path,
    is_test_path,
    language_for_path,
    parse_js_symbols,
    parse_python_symbols,
    tokenize_names,
)
# Imported under an alias: a module-level name beginning with ``test_`` would be
# collected by pytest as a test function.
from app.services.test_target_parser import proposed_test_names

PY_SOURCE = '''
"""Module docstring."""


def documented(value: int) -> int:
    """Double it."""
    return value * 2


def undocumented(a, b=2, *args, **kwargs):
    if a:
        for _ in args:
            pass
    return b


async def async_one():
    return None


def _private():
    return 1


class Service:
    """A service."""

    def __init__(self):
        self.x = 1

    def handle(self, request):
        if request:
            while False:
                pass
        return request

    def _hidden(self):
        return 2

    async def fetch(self):
        return None

    def __str__(self):
        return "s"


class _Internal:
    pass
'''


class TestLanguageDetection:
    @pytest.mark.parametrize(
        "path,expected",
        [
            ("app/main.py", "python"),
            ("app/main.PY", "python"),
            ("types/api.d.ts", "typescript"),
            ("src/app.tsx", "typescript"),
            ("src/app.js", "javascript"),
            ("src/app.mjs", "javascript"),
            ("README.md", None),
            ("Makefile", None),
            ("LICENSE", None),
            ("", None),
            (".gitignore", None),
        ],
    )
    def test_language_for_path(self, path, expected):
        assert language_for_path(path) == expected

    def test_a_leading_dot_is_not_an_extension(self):
        # ``.gitignore`` has no stem, so treating ``.gitignore`` as an extension
        # would classify a dotfile as source.
        assert language_for_path(".gitignore") is None


class TestPathClassification:
    @pytest.mark.parametrize(
        "path",
        [
            "tests/test_main.py",
            "test/test_main.py",
            "src/foo/__tests__/foo.test.js",
            "src/foo.spec.ts",
            "spec/models/user.js",
            "e2e/checkout.ts",
        ],
    )
    def test_test_paths(self, path):
        assert is_test_path(path) is True

    @pytest.mark.parametrize(
        "path",
        [
            "app/main.py",
            "src/index.ts",
            "node_modules/pkg/index.js",
            "README.md",
            "dist/bundle.js",
            "",
        ],
    )
    def test_non_test_paths(self, path):
        assert is_test_path(path) is False

    @pytest.mark.parametrize("path", ["tests/foo_test.go", "spec/models/user_spec.rb", "tests/x.java"])
    def test_test_files_in_unparseable_languages_are_not_counted(self, path):
        # Documented trade-off: a language this engine cannot parse contributes
        # no symbols, so its tests are not read. Reading them could only ever
        # suppress a target through an incidental name match.
        assert is_test_path(path) is False

    def test_source_paths_exclude_tests_and_vendored_code(self):
        assert is_source_path("app/main.py") is True
        assert is_source_path("tests/test_main.py") is False
        assert is_source_path("node_modules/x/index.js") is False
        assert is_source_path("README.md") is False

    def test_a_dot_in_a_directory_does_not_make_a_file_a_test(self):
        # The pattern ``.test.`` must match the file name, not any segment.
        assert is_test_path("src/my.test.dir/main.py") is False


class TestPythonSymbolExtraction:
    def test_public_symbols_are_found(self):
        symbols = parse_python_symbols("app/service.py", PY_SOURCE)
        names = {symbol.name for symbol in symbols}
        assert {"documented", "undocumented", "async_one", "Service", "handle", "fetch"} <= names

    def test_private_and_internal_names_are_excluded(self):
        names = {symbol.name for symbol in parse_python_symbols("app/service.py", PY_SOURCE)}
        assert "_private" not in names
        assert "_Internal" not in names
        assert "_hidden" not in names

    def test_dunder_methods_except_init_are_public(self):
        symbols = parse_python_symbols("app/service.py", PY_SOURCE)
        assert "__str__" in {symbol.name for symbol in symbols}
        assert "__init__" not in {symbol.name for symbol in symbols}

    def test_methods_are_qualified_by_class(self):
        symbols = {s.qualified_name: s for s in parse_python_symbols("app/service.py", PY_SOURCE)}
        assert "Service.handle" in symbols
        assert symbols["Service.handle"].kind == "method"
        assert symbols["Service.handle"].file == "app/service.py"

    def test_signature_records_arguments_defaults_and_return(self):
        symbols = {s.name: s for s in parse_python_symbols("app/service.py", PY_SOURCE)}
        signature = symbols["undocumented"].signature
        assert signature.startswith("undocumented(")
        assert "b = 2" in signature
        assert "*args" in signature
        assert "**kwargs" in signature

    def test_docstring_presence_is_recorded(self):
        symbols = {s.name: s for s in parse_python_symbols("app/service.py", PY_SOURCE)}
        assert symbols["documented"].has_docstring is True
        assert symbols["undocumented"].has_docstring is False

    def test_branching_code_scores_higher_than_a_straight_line(self):
        symbols = {s.name: s for s in parse_python_symbols("app/service.py", PY_SOURCE)}
        assert symbols["undocumented"].branch_score > symbols["documented"].branch_score

    def test_unparseable_source_yields_no_symbols(self):
        assert parse_python_symbols("app/broken.py", "def oops(:\n") == ()

    def test_empty_source_yields_no_symbols(self):
        assert parse_python_symbols("app/empty.py", "") == ()

    def test_results_are_ordered_by_position(self):
        symbols = parse_python_symbols("app/service.py", PY_SOURCE)
        assert symbols == tuple(sorted(symbols, key=lambda s: (s.file, s.line, s.qualified_name)))

    def test_nested_functions_are_not_public_api(self):
        symbols = parse_python_symbols(
            "app/outer.py", "def outer():\n    def inner():\n        return 1\n    return inner\n"
        )
        assert {s.name for s in symbols} == {"outer"}


class TestJavaScriptSymbolExtraction:
    def test_exported_declarations(self):
        symbols = parse_js_symbols(
            "src/index.ts",
            "export function boot(): void {}\n"
            "export const CONFIG = 1;\n"
            "export class Widget {}\n"
            "export interface Options {}\n"
            "export async function load() {}\n",
        )
        assert {s.name for s in symbols} == {"boot", "CONFIG", "Widget", "Options", "load"}
        kinds = {s.name: s.kind for s in symbols}
        assert kinds["Widget"] == "class"
        assert kinds["Options"] == "class"
        assert kinds["boot"] == "function"

    def test_top_level_declarations_without_export(self):
        symbols = parse_js_symbols("src/plain.js", "function helper() {}\nconst VALUE = 2;\n")
        assert {s.name for s in symbols} == {"helper", "VALUE"}

    def test_indented_local_declarations_are_not_public(self):
        symbols = parse_js_symbols("src/plain.js", "function outer() {\n  const local = 1;\n  return local;\n}\n")
        assert {s.name for s in symbols} == {"outer"}

    def test_signature_keeps_the_declaration_keyword(self):
        symbols = {s.name: s for s in parse_js_symbols("src/index.ts", "export function boot(): void {}\n")}
        assert symbols["boot"].signature.startswith("function boot")

    def test_unexported_underscore_names_are_skipped(self):
        assert parse_js_symbols("src/a.js", "function _hidden() {}\n") == ()

    def test_empty_source(self):
        assert parse_js_symbols("src/a.js", "") == ()


class TestTokenizing:
    def test_identifiers_are_collected(self):
        assert tokenize_names("from a.b import c\nx.c()\n") == {"from", "a", "b", "import", "c", "x"}

    def test_empty_content(self):
        assert tokenize_names("") == frozenset()


class TestFrameworkDetection:
    def test_pytest_from_conftest(self):
        assert detect_framework(["conftest.py", "tests/test_a.py"]) == "pytest"

    def test_jest_config(self):
        assert detect_framework(["jest.config.js", "src/a.test.js"]) == "jest"

    def test_vitest_config(self):
        assert detect_framework(["vitest.config.ts", "src/a.test.ts"]) == "vitest"

    def test_config_for_another_language_is_ignored(self):
        # A repository with a frontend jest config and backend pytest tests.
        assert detect_framework(["jest.config.js", "conftest.py", "tests/test_a.py"]) == "pytest"

    def test_python_test_names_imply_pytest(self):
        assert detect_framework(["tests/test_a.py"]) == "pytest"

    def test_no_tests_means_unknown(self):
        assert detect_framework(["app/main.py"]) == "unknown"

    def test_content_mention_can_disambiguate(self):
        assert detect_framework(["src/a.test.ts"], ["import { it } from 'vitest'"]) == "vitest"
        assert detect_framework(["src/a.test.js"], ["const x = require('jest')"]) == "jest"


class TestTestNameGeneration:
    def test_names_are_derived_from_the_symbol(self):
        symbol = parse_python_symbols("app/a.py", "def my_func():\n    return 1\n")[0]
        assert proposed_test_names(symbol)[0] == "test_my_func_behaviour"

    def test_method_names_include_the_class(self):
        symbol = {
            s.qualified_name: s
            for s in parse_python_symbols("app/a.py", "class Alpha:\n    def b(self):\n        pass\n")
        }["Alpha.b"]
        assert proposed_test_names(symbol)[0] == "test_alpha_b_behaviour"

    def test_names_are_deterministic(self):
        symbol = parse_python_symbols("app/a.py", "def f():\n    pass\n")[0]
        assert proposed_test_names(symbol) == proposed_test_names(symbol)


class TestTargetFinding:
    def test_a_symbol_a_test_references_is_not_a_target(self):
        selection = find_test_targets(
            [
                RepositoryFile("app/a.py", "def covered():\n    return 1\n"),
                RepositoryFile("tests/test_a.py", "from app.a import covered\n\ndef test_x():\n    covered()\n"),
            ]
        )
        assert selection.targets == ()
        assert selection.untested_symbols == 0

    def test_an_unreferenced_symbol_is_a_target(self):
        selection = find_test_targets(
            [
                RepositoryFile("app/a.py", "def orphan():\n    return 1\n"),
                RepositoryFile("tests/test_a.py", "def test_other():\n    assert True\n"),
            ]
        )
        assert [t.name for t in selection.targets] == ["orphan"]
        assert selection.targets[0].reason == "no_test_reference"
        assert "1 test file" in selection.targets[0].evidence

    def test_a_repository_with_no_tests_uses_the_no_test_suite_reason(self):
        selection = find_test_targets([RepositoryFile("app/a.py", "def orphan():\n    return 1\n")])
        assert selection.targets[0].reason == "no_test_suite"
        assert selection.framework == "unknown"
        assert "no recognisable test file" in selection.targets[0].evidence

    def test_a_reference_outside_a_test_file_does_not_count(self):
        # ``docs/example.py`` mentioning the name is not a test.
        selection = find_test_targets(
            [
                RepositoryFile("app/a.py", "def thing():\n    return 1\n"),
                RepositoryFile("docs/notes.py", "# thing is documented here\n"),
            ]
        )
        assert [t.name for t in selection.targets] == ["thing"]

    def test_vendored_tests_do_not_suppress_targets(self):
        selection = find_test_targets(
            [
                RepositoryFile("app/a.py", "def thing():\n    return 1\n"),
                RepositoryFile("node_modules/p/test.js", "thing()\n"),
            ]
        )
        assert [t.name for t in selection.targets] == ["thing"]

    def test_targets_are_ranked_by_priority_then_path(self):
        selection = find_test_targets(
            [
                RepositoryFile("app/a.py", "def plain():\n    return 1\n"),
                RepositoryFile("app/b.py", 'def complex(x):\n    """Doc."""\n    if x:\n        pass\n    for _ in range(3):\n        pass\n    return x\n'),
            ],
            max_targets=2,
        )
        assert [t.name for t in selection.targets] == ["complex", "plain"]
        assert selection.targets[0].priority > selection.targets[1].priority

    def test_max_targets_truncates_and_reports(self):
        selection = find_test_targets(
            [RepositoryFile("app/a.py", "".join(f"def f{i}():\n    return {i}\n" for i in range(10)))],
            max_targets=3,
        )
        assert len(selection.targets) == 3
        assert selection.truncated is True
        assert selection.untested_symbols == 10

    def test_max_targets_is_clamped_to_the_schema_ceiling(self):
        selection = find_test_targets(
            [RepositoryFile("app/a.py", "".join(f"def f{i}():\n    return {i}\n" for i in range(80)))],
            max_targets=10_000,
        )
        assert len(selection.targets) <= 60

    def test_a_zero_or_negative_max_targets_still_returns_one(self):
        selection = find_test_targets(
            [RepositoryFile("app/a.py", "def a():\n    pass\ndef b():\n    pass\n")], max_targets=0
        )
        assert len(selection.targets) == 1

    def test_test_directories_are_reported(self):
        selection = find_test_targets(
            [
                RepositoryFile("app/a.py", "def a():\n    pass\n"),
                RepositoryFile("tests/unit/test_a.py", "def test_x():\n    pass\n"),
            ]
        )
        # Only conventionally named directories are reported; ``unit`` is a
        # subdirectory of ``tests``, not a convention of its own.
        assert selection.test_directories == ("tests",)

    def test_a_parse_failure_is_reported_not_swallowed(self):
        selection = find_test_targets(
            [
                RepositoryFile("app/broken.py", "def oops(:\n"),
                RepositoryFile("app/a.py", "def a():\n    pass\n"),
            ]
        )
        assert any("app/broken.py" in error for error in selection.errors)
        assert "could not be parsed" in selection.errors[0]

    def test_blank_files_are_not_parse_failures(self):
        selection = find_test_targets([RepositoryFile("app/empty.py", "   \n")])
        assert selection.errors == []

    def test_counts_are_reported(self):
        selection = find_test_targets(
            [
                RepositoryFile("app/a.py", "def a():\n    pass\ndef b():\n    pass\n"),
                RepositoryFile("tests/test_a.py", "def test_a():\n    a()\n"),
            ]
        )
        assert selection.source_files == 1
        assert selection.public_symbols == 2
        assert selection.untested_symbols == 1
        assert selection.test_files == ("tests/test_a.py",)

    def test_selection_is_reproducible(self):
        files = [
            RepositoryFile("app/a.py", "def a():\n    pass\ndef b():\n    pass\n"),
            RepositoryFile("app/c.py", "def c():\n    pass\n"),
            RepositoryFile("tests/test_a.py", "def test_a():\n    a()\n"),
        ]
        first = find_test_targets(files)
        second = find_test_targets(list(reversed(files)))
        assert [t.qualified_name for t in first.targets] == [t.qualified_name for t in second.targets]

    def test_no_files_produces_an_empty_selection(self):
        selection = find_test_targets([])
        assert selection.targets == ()
        assert selection.framework == "unknown"
        assert selection.source_files == 0
