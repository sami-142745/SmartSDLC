"""Tests for the architecture source parser.

These cover the layer that actually reads repository source, so they concentrate
on the three things that can go badly wrong here: resolving an import to the wrong
module, resolving one that does not exist, and letting a malformed file abort the
whole analysis.
"""

from __future__ import annotations

import pytest

from app.services import architecture_parser as parser


class TestLanguageDetection:
    def test_python_and_its_stubs_are_python(self):
        assert parser.language_for_path("a/b.py") == "python"
        assert parser.language_for_path("a/b.pyi") == "python"

    @pytest.mark.parametrize(
        "path,expected",
        [
            ("a/b.js", "javascript"),
            ("a/b.jsx", "javascript"),
            ("a/b.mjs", "javascript"),
            ("a/b.cjs", "javascript"),
            ("a/b.ts", "typescript"),
            ("a/b.tsx", "typescript"),
        ],
    )
    def test_javascript_family(self, path, expected):
        assert parser.language_for_path(path) == expected

    @pytest.mark.parametrize(
        "path", ["README.md", "Makefile", "data.json", "styles.css", "a/b.py.bak", "noext"]
    )
    def test_non_source_is_not_analysable(self, path):
        assert parser.language_for_path(path) is None

    def test_extension_matching_is_case_insensitive(self):
        assert parser.language_for_path("A/B.PY") == "python"

    def test_a_dotfile_has_no_extension(self):
        # ``.py`` alone is a name with no extension, not a Python file.
        assert parser.language_for_path("weird/.py") is None


class TestPathScreening:
    @pytest.mark.parametrize(
        "path",
        [
            "node_modules/react/index.js",
            "dist/bundle.js",
            "src/vendor/lib.js",
            ".git/config.js",
            "backend/.venv/lib/module.py",
            "vendor/pkg/service.py",
            "src/__pycache__/thing.py",
            "migrations/0001_initial.py",
            "coverage/report.js",
        ],
    )
    def test_vendored_and_generated_paths_are_excluded(self, path):
        assert parser.is_analysable_path(path) is False

    def test_ignored_directory_matching_is_case_insensitive(self):
        # ``Node_Modules`` and ``node_modules`` are the same directory on macOS.
        assert parser.is_analysable_path("Node_Modules/x.js") is False

    def test_real_source_is_included(self):
        assert parser.is_analysable_path("app/services/security.py") is True

    def test_a_source_file_named_like_an_ignored_dir_is_still_analysable(self):
        # Only *directories* are ignored, never the final segment.
        assert parser.is_analysable_path("src/build.py") is True

    @pytest.mark.parametrize("path", ["", "   ", "///", "./"])
    def test_empty_paths_are_not_analysable(self, path):
        assert parser.is_analysable_path(path) is False


class TestNormalisePath:
    def test_leading_dot_slash_is_removed(self):
        assert parser.normalise_path("./app/main.py") == "app/main.py"

    def test_backslashes_become_forward_slashes(self):
        assert parser.normalise_path("app\\services\\main.py") == "app/services/main.py"

    def test_traversal_segments_cannot_survive(self):
        # A provider returning a crafted path must not make the analyzer read
        # outside the repository it was asked about.
        assert parser.normalise_path("app/../../etc/passwd") == "app/etc/passwd"
        assert parser.normalise_path("../../../etc/passwd") == "etc/passwd"
        assert ".." not in parser.normalise_path("a/../../b/../c.py")

    def test_windows_drive_letters_are_stripped(self):
        assert parser.normalise_path("C:/app/main.py") == "app/main.py"

    def test_absolute_paths_become_relative(self):
        assert parser.normalise_path("/app/main.py") == "app/main.py"


class TestModuleNaming:
    def test_python_path_becomes_a_dotted_name(self):
        name, package, is_package = parser._python_module_name("app/services/security.py")
        assert name == "app.services.security"
        assert package == "app.services"
        assert is_package is False

    def test_init_is_the_package_itself(self):
        name, package, is_package = parser._python_module_name("app/services/__init__.py")
        assert name == "app.services"
        # A package is its own containing package, which is what makes
        # ``from . import x`` inside it mean ``app.services.x``.
        assert package == "app.services"
        assert is_package is True

    def test_top_level_module_has_an_empty_package(self):
        name, package, _ = parser._python_module_name("setup.py")
        assert name == "setup"
        assert package == ""

    def test_leading_src_is_packaging_not_a_package(self):
        # Projects import ``myapp`` from ``src/myapp``, never from ``src``.
        name, _, _ = parser._python_module_name("src/myapp/main.py")
        assert name == "myapp.main"

    def test_javascript_paths_keep_slashes(self):
        assert parser.module_name_for_path("src/api/security.ts") == "src/api/security"

    def test_a_filename_with_dots_only_loses_the_extension(self):
        assert parser.module_name_for_path("src/a.b.ts") == "src/a.b"


class TestPythonImportExtraction:
    def test_plain_import(self):
        module = parser.parse_module("a/b.py", "import os\n")
        assert "os" in module.imports

    def test_import_from_names_the_module_not_the_symbol(self):
        # ``x`` is a member of the module, not a module dependency.
        module = parser.parse_module("a/b.py", "from os import path\n")
        assert module.imports == ("os",)

    def test_from_dot_import_names_each_target(self):
        module = parser.parse_module("app/routers/s.py", "from . import helpers, utils\n")
        assert ".helpers" in module.imports
        assert ".utils" in module.imports
        # The bare dot must not survive as a self-reference.
        assert "." not in module.imports

    def test_from_star_import_is_not_a_named_dependency(self):
        module = parser.parse_module("a/b.py", "from .x import *\n")
        assert module.imports == (".x",)

    def test_multiple_dots_are_preserved_for_resolution(self):
        module = parser.parse_module("app/routers/s.py", "from ..shared import util\n")
        assert "..shared" in module.imports

    def test_imports_inside_functions_and_try_blocks_count(self):
        source = "def f():\n    import json\n\ntry:\n    import motor\nexcept ImportError:\n    pass\n"
        module = parser.parse_module("a/b.py", source)
        assert "json" in module.imports
        assert "motor" in module.imports

    def test_conditional_imports_are_deduplicated(self):
        module = parser.parse_module("a/b.py", "import os\nimport os\nfrom os import sep\n")
        assert module.imports == ("os",)

    def test_a_syntax_error_degrades_rather_than_raising(self):
        module = parser.parse_module("a/b.py", "def broken(:\n")
        assert module.parsed is False
        assert module.parse_error is not None
        assert module.imports == ()

    def test_a_syntax_error_does_not_lose_the_file(self):
        # The module is still listed; only its imports are unknown. Hiding it
        # would understate the repository.
        module = parser.parse_module("a/b.py", "def broken(:\n")
        assert module.name == "a.b"
        assert module.path == "a/b.py"


class TestJavaScriptImportExtraction:
    def test_default_import(self):
        module = parser.parse_module("a/b.ts", "import axios from 'axios';\n")
        assert "axios" in module.imports

    def test_named_import(self):
        module = parser.parse_module("a/b.ts", "import { http } from './client';\n")
        assert "./client" in module.imports

    def test_type_only_import_is_still_a_dependency(self):
        # Dropping it would understate coupling, and `tsc` treats it as real.
        module = parser.parse_module("a/b.ts", "import type { S } from '../types';\n")
        assert "../types" in module.imports

    def test_side_effect_import(self):
        module = parser.parse_module("a/b.ts", "import './polyfill';\n")
        assert "./polyfill" in module.imports

    def test_require_is_an_import(self):
        module = parser.parse_module("a/b.js", "const zod = require('zod');\n")
        assert "zod" in module.imports

    def test_bare_require_is_an_import_but_dot_notation_is_not(self):
        source = "const a = require('lodash');\nfoo.require('not-a-dep');\n"
        module = parser.parse_module("a/b.js", source)
        assert "lodash" in module.imports
        assert "not-a-dep" not in module.imports

    def test_re_export_from_is_an_import(self):
        module = parser.parse_module("a/index.ts", "export { X } from './x';\n")
        assert "./x" in module.imports

    def test_star_re_export_is_an_import(self):
        module = parser.parse_module("a/index.ts", "export * from './y';\n")
        assert "./y" in module.imports

    def test_export_without_from_is_not_an_import(self):
        module = parser.parse_module("a/b.ts", "export const x = 1;\nexport function f() {}\n")
        assert module.imports == ()

    def test_literal_dynamic_import_is_kept(self):
        module = parser.parse_module("a/b.ts", "const m = await import('./lazy');\n")
        assert "./lazy" in module.imports

    def test_computed_dynamic_import_is_skipped_not_guessed(self):
        # ``import(path)`` is unresolvable without executing the module, so it is
        # skipped rather than guessed at.
        module = parser.parse_module("a/b.ts", "const m = await import(name);\n")
        assert module.imports == ()

    def test_double_quotes_are_handled(self):
        module = parser.parse_module("a/b.ts", 'import x from "./c";\n')
        assert "./c" in module.imports


class TestExternalClassification:
    @pytest.mark.parametrize(
        "module", ["fastapi", "fastapi.responses", "motor", "google.generativeai", "pydantic"]
    )
    def test_known_third_party_python_is_external(self, module):
        assert parser.is_external_python(module) is True

    @pytest.mark.parametrize("module", ["app.services.security", "", ".", "nonexistent_pkg"])
    def test_internal_and_unknown_python_is_not_external(self, module):
        assert parser.is_external_python(module) is False

    @pytest.mark.parametrize(
        "specifier,expected",
        [
            ("axios", "axios"),
            ("react-router-dom/v6", "react-router-dom"),
            ("@monaco-editor/react", "@monaco-editor/react"),
            ("@google/generativeai", "@google/generativeai"),
            ("@scope/pkg/sub/path", "@scope/pkg"),
            ("./local", ""),
            ("../up", ""),
        ],
    )
    def test_js_package_names_collapse_subpaths(self, specifier, expected):
        assert parser.package_name_for_js(specifier) == expected


class TestResolution:
    def _resolve(self, files):
        modules = [parser.parse_module(path, content) for path, content in files.items()]
        return parser.resolve(modules)

    def test_absolute_python_import_resolves_to_the_module(self):
        result = self._resolve(
            {
                "app/services/a.py": "from app.services.b import x\n",
                "app/services/b.py": "",
            }
        )
        assert ("app.services.a", "app.services.b", "app.services.b") in result.internal_edges

    def test_from_package_import_submodule_targets_the_submodule(self):
        # ``from app.services import auth`` depends on app.services.auth, not on
        # the package. Binding it to the package would merge every service into a
        # single edge and understate real coupling.
        result = self._resolve(
            {
                "app/routers/s.py": "from app.services import auth\n",
                "app/services/__init__.py": "",
                "app/services/auth.py": "",
            }
        )
        assert result.internal_edges == [
            ("app.routers.s", "app.services.auth", "app.services")
        ]

    def test_from_package_import_symbol_falls_back_to_the_package(self):
        result = self._resolve(
            {
                "app/routers/s.py": "from app.services import CONFIG\n",
                "app/services/__init__.py": "CONFIG = {}\n",
            }
        )
        assert result.internal_edges == [
            ("app.routers.s", "app.services", "app.services")
        ]

    def test_named_submodule_of_a_multi_child_package_is_deterministic(self):
        # A set-iteration resolver could return app.services.aaa for
        # ``import zeta`` and change between runs. The named member must win.
        files = {
            "app/routers/s.py": "from app.services import zeta\n",
            "app/services/__init__.py": "",
            "app/services/aaa.py": "",
            "app/services/zeta.py": "",
        }
        first = self._resolve(files)
        second = self._resolve(dict(reversed(list(files.items()))))
        assert first.internal_edges == second.internal_edges == [
            ("app.routers.s", "app.services.zeta", "app.services")
        ]

    def test_relative_from_package_import_submodule_targets_the_submodule(self):
        result = self._resolve(
            {
                "app/routers/s.py": "from . import helpers\nfrom .shared import util\n",
                "app/routers/helpers.py": "",
                "app/routers/shared/util.py": "",
            }
        )
        assert ("app.routers.s", "app.routers.helpers", ".helpers") in result.internal_edges
        assert ("app.routers.s", "app.routers.shared.util", ".shared") in result.internal_edges

    def test_single_dot_resolves_to_a_sibling_not_the_importer(self):
        # The bug this guards: ``from . import helpers`` resolving to the
        # importing module, inventing a self-edge and hiding the real sibling.
        result = self._resolve(
            {
                "app/routers/s.py": "from . import helpers\n",
                "app/routers/helpers.py": "",
            }
        )
        assert result.internal_edges == [("app.routers.s", "app.routers.helpers", ".helpers")]

    def test_double_dot_climbs_one_package_level(self):
        result = self._resolve(
            {
                "app/routers/s.py": "from ..shared import util\n",
                "app/shared/__init__.py": "",
            }
        )
        assert result.internal_edges == [("app.routers.s", "app.shared", "..shared")]

    def test_a_relative_import_from_init_targets_its_own_package(self):
        result = self._resolve(
            {
                "app/services/__init__.py": "from . import scanner\n",
                "app/services/scanner.py": "",
            }
        )
        assert result.internal_edges == [("app.services", "app.services.scanner", ".scanner")]

    def test_a_dot_dot_beyond_the_root_is_unresolved_not_guessed(self):
        result = self._resolve({"a/b.py": "from ...nowhere import x\n"})
        assert result.internal_edges == []
        assert ("a.b", "...nowhere") in result.unresolved

    def test_unresolved_import_produces_no_edge(self):
        # Inventing an edge here is exactly the failure this engine avoids.
        result = self._resolve({"a/b.py": "from app.missing import x\n"})
        assert result.internal_edges == []
        assert result.unresolved == [("a.b", "app.missing")]

    def test_stdlib_is_neither_internal_nor_unresolved(self):
        result = self._resolve({"a/b.py": "import os\nimport json\n"})
        assert result.internal_edges == []
        assert result.external_edges == []
        assert result.unresolved == []

    def test_third_party_becomes_an_external_edge(self):
        result = self._resolve({"a/b.py": "import fastapi\nfrom motor import x\n"})
        assert result.external_edges == [("a.b", "fastapi"), ("a.b", "motor")]

    def test_relative_js_resolves_across_extensions(self):
        # ``./client`` does not say ``.ts``; resolution finds the real file.
        result = self._resolve(
            {
                "src/api/security.ts": "import { http } from './client';\n",
                "src/api/client.ts": "",
            }
        )
        assert result.internal_edges == [("src/api/security", "src/api/client", "./client")]

    def test_relative_js_resolves_to_an_index_file(self):
        result = self._resolve(
            {
                "src/api/security.ts": "import { x } from './util';\n",
                "src/api/util/index.ts": "",
            }
        )
        assert result.internal_edges == [("src/api/security", "src/api/util/index", "./util")]

    def test_relative_js_can_climb(self):
        result = self._resolve(
            {
                "src/api/deep/s.ts": "import { x } from '../../lib/u';\n",
                "src/lib/u.ts": "",
            }
        )
        assert ("src/api/deep/s", "src/lib/u", "../../lib/u") in result.internal_edges

    def test_relative_js_beyond_the_root_is_unresolved(self):
        result = self._resolve({"b.ts": "import { x } from '../../nope';\n"})
        assert result.internal_edges == []
        assert result.unresolved

    def test_tsconfig_alias_resolves_to_a_real_path(self):
        result = self._resolve(
            {
                "src/api/s.ts": "import { x } from '@/components/ui';\n",
                "src/components/ui/index.tsx": "",
            }
        )
        assert result.internal_edges == [("src/api/s", "src/components/ui/index", "@/components/ui")]

    def test_bare_specifier_with_no_matching_file_is_external(self):
        result = self._resolve({"a/b.ts": "import axios from 'axios';\n"})
        # JS/TS module ids keep slashes, so the source is ``a/b``.
        assert result.external_edges == [("a/b", "axios")]
        assert result.internal_edges == []

    def test_an_unparsed_target_is_still_a_valid_edge_target(self):
        # ``a.c`` genuinely depends on ``a.b``; the fact that ``a.b`` itself
        # could not be parsed removes *its* outgoing edges, not the edge into it.
        modules = [
            parser.parse_module("a/b.py", "def broken(:\n"),
            parser.parse_module("a/c.py", "from a.b import x\n"),
        ]
        result = parser.resolve(modules)
        assert result.internal_edges == [("a.c", "a.b", "a.b")]
        assert result.modules["a.b"].parsed is False

    def test_an_unparsed_module_contributes_no_outgoing_edges(self):
        modules = [
            parser.parse_module("a/b.py", "def broken(:\nimport os\n"),
            parser.parse_module("a/c.py", ""),
        ]
        result = parser.resolve(modules)
        assert result.external_edges == []

    def test_output_is_sorted_and_deterministic(self):
        files = {
            "a/z.py": "from a.y import x\nimport os\n",
            "a/y.py": "from a.x import x\n",
            "a/x.py": "",
        }
        first = self._resolve(files)
        second = self._resolve(dict(reversed(list(files.items()))))
        assert first.internal_edges == second.internal_edges
        assert first.internal_edges == sorted(first.internal_edges)

    def test_duplicate_imports_of_the_same_target_collapse(self):
        # A graph has one edge per relationship, so this must not double-count
        # fan-out — that would fabricate coupling.
        result = self._resolve(
            {
                "a/b.py": "from a.c import x\nimport a.c\n",
                "a/c.py": "",
            }
        )
        assert result.internal_edges == [("a.b", "a.c", "a.c")]


class TestHardenedParsing:
    def test_binary_content_is_rejected(self):
        module = parser.parse_module("a/b.py", "x = 1\x00\x00\x00\n")
        assert module.parsed is False
        assert module.parse_error == "binary content"

    def test_bytes_content_is_decoded(self):
        module = parser.parse_module("a/b.py", b"import os\n")
        assert module.imports == ("os",)

    def test_undecodable_bytes_do_not_raise(self):
        module = parser.parse_module("a/b.py", b"\xff\xfe\xfd\xfc import os")
        assert module.path == "a/b.py"

    def test_an_oversized_file_is_truncated_and_flagged(self):
        # Generated files must not silently produce a partial graph that looks
        # complete.
        huge = "import os\n" * 40000
        module = parser.parse_module("a/b.py", huge)
        assert module.parse_error == "file too large to analyse fully"
        assert module.line_count < 40000

    def test_a_file_within_the_cap_is_not_flagged(self):
        module = parser.parse_module("a/b.py", "import os\n")
        assert module.parse_error is None

    def test_an_unsupported_file_yields_no_module_name(self):
        module = parser.parse_module("README.md", "# hi\n")
        assert module.name == ""

    def test_none_content_is_handled(self):
        module = parser.parse_module("a/b.py", None)
        assert module.line_count == 0
