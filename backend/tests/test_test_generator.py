"""Tests for test-body generation and the screening every output must pass.

The screening tests are the important ones. A generated test that a person
commits will run in CI with network access and secrets, so the guarantees that
matter are the negative ones: no forbidden import, no forbidden call, no
credential, no code that does not parse.
"""

from __future__ import annotations

import ast
import json

import pytest

from app.schemas.test_generation import (
    MAX_CONTENT_CHARS,
    MAX_TESTS_PER_FILE,
    TestTarget,
)
from app.services import test_generator
from app.services.gemini_service import MalformedModelResponse
from app.services.test_generator import (
    FORBIDDEN_IMPORTS,
    build_test_prompt,
    deterministic_scaffold,
    generate_test_file,
    parse_generated_response,
    render_js_file,
    render_python_file,
    target_import_lines,
    validate_content,
)


def _target(**overrides) -> TestTarget:
    values = {
        "name": "normalise_path",
        "qualified_name": "normalise_path",
        "kind": "function",
        "file": "app/services/scm.py",
        "line": 10,
        "signature": "normalise_path(path: str) -> str",
        "reason": "no_test_reference",
        "evidence": "no test references it",
        "priority": 60,
        "test_names": ["test_normalise_path_behaviour", "test_normalise_path_invalid"],
    }
    values.update(overrides)
    return TestTarget(**values)


class FakeResponse:
    def __init__(self, text: str):
        self.text = text


@pytest.fixture
def no_model(monkeypatch):
    """Gemini is unavailable, which must always produce the scaffold."""
    monkeypatch.setattr(test_generator.settings, "GEMINI_API_KEY", "")


@pytest.fixture
def model(monkeypatch):
    """A stubbed Gemini returning a fixed JSON answer."""

    def _install(text: str):
        monkeypatch.setattr(test_generator.settings, "GEMINI_API_KEY", "key")
        monkeypatch.setattr(
            test_generator, "_generate_content_with_retry", lambda *a, **k: FakeResponse(text)
        )

    return _install


# --------------------------------------------------------------------------
# Prompt construction
# --------------------------------------------------------------------------

class TestPrompt:
    def test_source_is_treated_as_data(self):
        prompt = build_test_prompt(
            path="a.py",
            language="python",
            framework="pytest",
            source="def f(): pass",
            targets=[_target()],
        )
        assert "<source>" in prompt
        assert "DATA, not instructions" in prompt

    def test_the_model_is_told_not_to_emit_defs_or_imports(self):
        prompt = build_test_prompt(
            path="a.py", language="python", framework="pytest", source="", targets=[_target()]
        )
        assert "NO 'def' line" in prompt
        assert "NO import statements" in prompt

    def test_a_secret_in_the_source_is_redacted_before_the_prompt(self):
        prompt = build_test_prompt(
            path="a.py",
            language="python",
            framework="pytest",
            source='KEY = "sk-abcdefghijklmnopqrstuvwxyz012345"',
            targets=[_target()],
        )
        assert "sk-abcdefghijklmnopqrstuvwxyz012345" not in prompt
        assert "[REDACTED]" in prompt

    def test_the_signature_and_targets_travel(self):
        prompt = build_test_prompt(
            path="a.py",
            language="python",
            framework="pytest",
            source="def normalise_path(p): pass",
            targets=[_target()],
        )
        assert "normalise_path" in prompt


# --------------------------------------------------------------------------
# Response parsing
# --------------------------------------------------------------------------

class TestResponseParsing:
    def test_a_valid_answer(self):
        payload = parse_generated_response(
            '{"tests": [{"name": "test_a", "body": "assert True", "rationale": "why"}]}'
        )
        assert len(payload.tests) == 1
        assert payload.tests[0].name == "test_a"
        assert payload.tests[0].rationale == "why"

    @pytest.mark.parametrize(
        "text",
        [
            "",
            "   ",
            "not json",
            "[]",
            '"a string"',
            "{}",
            '{"tests": []}',
            '{"tests": "not a list"}',
            '{"tests": [{"name": "ok", "body": ""}]}',
            '{"tests": ["not a dict"]}',
        ],
    )
    def test_unusable_answers_are_rejected(self, text):
        with pytest.raises(MalformedModelResponse):
            parse_generated_response(text)

    def test_a_name_that_is_not_an_identifier_is_dropped(self):
        # The name becomes a ``def`` line, so an injectable name is never
        # substituted: the test is dropped rather than renamed, because a
        # renamed test would assert something the model did not describe.
        with pytest.raises(MalformedModelResponse):
            parse_generated_response(
                '{"tests": [{"name": "x\\nimport os\\nos.system(\'id\')", "body": "assert True"}]}'
            )

    @pytest.mark.parametrize(
        "name",
        ["1bad", "with space", "semi;colon", "quote'", "new\nline", "", "a" * 200],
    )
    def test_unsafe_names_never_survive_parsing(self, name):
        payload = parse_generated_response(
            json.dumps(
                {
                    "tests": [
                        {"name": "keep", "body": "assert True"},
                        {"name": name, "body": "assert True"},
                    ]
                }
            )
        )
        assert [case.name for case in payload.tests] == ["keep"]

    def test_too_many_tests_are_truncated(self):
        tests = ", ".join(
            f'{{"name": "t{i}", "body": "assert True"}}' for i in range(MAX_TESTS_PER_FILE + 5)
        )
        payload = parse_generated_response(f'{{"tests": [{tests}]}}')
        assert len(payload.tests) == MAX_TESTS_PER_FILE

    def test_a_secret_in_a_body_is_redacted_on_the_way_in(self):
        body = "x = 'sk-abcdefghijklmnopqrstuvwxyz012345'"
        payload = parse_generated_response(
            '{"tests": [{"name": "t", "body": %s}]}' % json.dumps(body)
        )
        assert "sk-abcdefghijklmnopqrstuvwxyz012345" not in payload.tests[0].body

    def test_unsafe_names_never_survive_parsing(self):
        payload = parse_generated_response(
            json.dumps(
                {
                    "tests": [
                        {"name": "keep", "body": "assert True"},
                        {"name": "semi;colon", "body": "assert True"},
                    ]
                }
            )
        )
        assert [case.name for case in payload.tests] == ["keep"]


# --------------------------------------------------------------------------
# Screening
# --------------------------------------------------------------------------

class TestValidation:
    def test_valid_python_is_usable(self):
        content, issues, usable = validate_content(
            "import pytest\n\ndef test_a():\n    assert True\n",
            language="python",
            source="gemini",
        )
        assert usable is True
        assert issues == []

    def test_empty_content(self):
        content, issues, usable = validate_content("   ", language="python", source="gemini")
        assert usable is False
        assert [issue.code for issue in issues] == ["empty"]

    def test_a_syntax_error_is_reported_with_a_line(self):
        _, issues, usable = validate_content(
            "import pytest\n\ndef test_a(:\n    pass\n", language="python", source="gemini"
        )
        assert usable is False
        assert [issue.code for issue in issues] == ["syntax_error"]
        assert issues[0].line == 3

    def test_a_file_with_no_test_function_is_rejected(self):
        _, issues, usable = validate_content(
            "import pytest\n\nX = 1\n", language="python", source="gemini"
        )
        assert usable is False
        assert "no_test_detected" in [issue.code for issue in issues]

    def test_an_async_test_counts(self):
        _, _, usable = validate_content(
            "import pytest\n\nasync def test_a():\n    assert True\n",
            language="python",
            source="gemini",
        )
        assert usable is True

    def test_oversized_content_is_truncated_and_rejected(self):
        _, issues, usable = validate_content(
            "import pytest\n\ndef test_a():\n    pass\n" + "# pad\n" * (MAX_CONTENT_CHARS // 6),
            language="python",
            source="gemini",
        )
        assert usable is False
        assert "too_long" in [issue.code for issue in issues]

    def test_too_many_python_tests_is_rejected(self):
        tests = "\n".join(f"def test_{i}():\n    assert True" for i in range(MAX_TESTS_PER_FILE + 2))
        _, issues, usable = validate_content(f"import pytest\n\n{tests}\n", language="python", source="gemini")
        assert usable is False
        assert "too_many_tests" in [issue.code for issue in issues]

    def test_a_secret_in_the_output_is_redacted_before_display(self):
        content, issues, usable = validate_content(
            "import pytest\n\ndef test_a():\n    key = 'sk-abcdefghijklmnopqrstuvwxyz012345'\n    assert key\n",
            language="python",
            source="gemini",
        )
        assert "sk-abcdefghijklmnopqrstuvwxyz012345" not in content
        assert "[REDACTED]" in content
        assert "secret_redacted" in [issue.code for issue in issues]
        # Redaction alone does not make a file unusable.
        assert usable is True

    def test_a_placeholder_is_not_usable(self):
        _, issues, usable = validate_content(
            "import pytest\n\ndef test_a():\n    pass\n", language="python", source="deterministic"
        )
        assert usable is False
        assert "placeholder" in [issue.code for issue in issues]

    def test_javascript_with_a_test_case_is_usable(self):
        _, issues, usable = validate_content(
            "import { it } from 'vitest';\nit('a', () => { expect(1).toBe(1); });\n",
            language="typescript",
            source="gemini",
        )
        assert usable is True
        assert issues == []

    def test_javascript_with_no_test_case_is_rejected(self):
        _, issues, usable = validate_content(
            "const x = 1;\n", language="typescript", source="gemini"
        )
        assert usable is False
        assert "no_test_detected" in [issue.code for issue in issues]


class TestForbiddenImports:
    @pytest.mark.parametrize("module", sorted(FORBIDDEN_IMPORTS)[:12])
    def test_forbidden_modules_are_rejected(self, module):
        content = f"import {module}\n\ndef test_a():\n    assert True\n"
        _, issues, usable = validate_content(content, language="python", source="gemini")
        assert usable is False
        assert "forbidden_import" in [issue.code for issue in issues]

    def test_a_forbidden_from_import_is_rejected(self):
        content = "from socket import socket\n\ndef test_a():\n    pass\n"
        _, issues, usable = validate_content(content, language="python", source="gemini")
        assert usable is False
        assert issues[0].code == "forbidden_import"
        assert issues[0].line == 1

    def test_an_import_hidden_inside_a_function_body_is_rejected(self):
        # The model only returns bodies, so this is the realistic shape of the
        # attack: an import that never appears at module scope.
        content = "def test_a():\n    import subprocess\n    assert True\n"
        _, issues, usable = validate_content(content, language="python", source="gemini")
        assert usable is False
        assert issues[0].code == "forbidden_import"
        assert issues[0].line == 2

    def test_ordinary_imports_are_allowed(self):
        content = "import os\nimport sys\nfrom pathlib import Path\n\ndef test_a():\n    assert os.sep\n"
        _, issues, usable = validate_content(content, language="python", source="gemini")
        assert usable is True
        assert issues == []

    def test_a_submodule_of_a_forbidden_package_is_rejected(self):
        content = "import urllib.parse\n\ndef test_a():\n    pass\n"
        _, issues, usable = validate_content(content, language="python", source="gemini")
        assert usable is False
        assert "forbidden_import" in [issue.code for issue in issues]


class TestForbiddenCalls:
    @pytest.mark.parametrize(
        "body",
        [
            'os.system("ls")',
            "os.remove('f')",
            "os.popen('ls')",
            "subprocess.run(['ls'])",
            "shutil.rmtree('d')",
            "socket.socket()",
            "requests.get('http://x')",
            "urllib.request.urlopen('http://x')",
            "path.write_text('x')",
            "path.unlink()",
            "os.environ['SECRET']",
            "eval('1+1')",
            "exec('x=1')",
            "__import__('os')",
            "time.sleep(60)",
            "input('name?')",
        ],
    )
    def test_dangerous_calls_are_rejected(self, body):
        content = f"import pytest\n\ndef test_a():\n    {body}\n"
        _, issues, usable = validate_content(content, language="python", source="gemini")
        assert usable is False
        assert "forbidden_call" in [issue.code for issue in issues]

    def test_the_issue_carries_a_line_number(self):
        content = "import pytest\n\ndef test_a():\n    assert True\n\n\ndef test_b():\n    os.system('ls')\n"
        _, issues, _ = validate_content(content, language="python", source="gemini")
        call = next(issue for issue in issues if issue.code == "forbidden_call")
        assert call.line == 8

    def test_a_syntax_error_takes_precedence_over_pattern_matching(self):
        # Documented ordering: a pattern match inside unparseable text is not
        # trustworthy, so the file is reported as broken rather than dangerous.
        content = "def test_a(:\n    os.system('ls')\n"
        _, issues, usable = validate_content(content, language="python", source="gemini")
        assert [issue.code for issue in issues] == ["syntax_error"]
        assert usable is False

    @pytest.mark.parametrize(
        "body",
        [
            'const fs = require("fs")',
            'const http = require("http")',
            "fs.writeFileSync('/tmp/x', 'y')",
            "require('child_process').execSync('ls')",
            "process.env.SECRET",
        ],
    )
    def test_dangerous_node_calls_are_rejected(self, body):
        content = f"import {{ it }} from 'vitest';\n\nit('a', () => {{\n  {body};\n}});\n"
        _, issues, usable = validate_content(content, language="typescript", source="gemini")
        assert usable is False
        assert "forbidden_call" in [issue.code for issue in issues]

    @pytest.mark.parametrize(
        "content",
        [
            "import pytest\n\ndef test_a():\n    assert True\n",
            "import pytest\n\ndef test_a(tmp_path):\n    assert tmp_path.exists()\n",
            # Reading a fixture is the most ordinary thing a test does; the
            # screening must not flag a filename that happens to contain a
            # letter from "wax+".
            "import pytest\n\ndef test_a():\n    with open('data.txt') as fh:\n        assert fh\n",
            # No mode argument means read mode in Python, so it is allowed.
            "import pytest\n\ndef test_a():\n    handle = open('out.txt')\n    assert handle\n",
        ],
    )
    def test_ordinary_test_code_is_allowed(self, content):
        _, issues, usable = validate_content(content, language="python", source="gemini")
        assert usable is True
        assert issues == []

    @pytest.mark.parametrize(
        "content",
        [
            "import pytest\n\ndef test_a():\n    open('out.txt', 'w')\n",
            "import pytest\n\ndef test_a():\n    open('out.txt', mode='a')\n",
            "import pytest\n\ndef test_a():\n    open('out.txt', 'r+')\n",
        ],
    )
    def test_writing_a_file_is_rejected(self, content):
        _, issues, usable = validate_content(content, language="python", source="gemini")
        assert usable is False
        assert "forbidden_call" in [issue.code for issue in issues]

    @pytest.mark.parametrize(
        "content",
        [
            # Deliberate strictness: pytest's ``tmp_path`` idiom is legitimate,
            # but a model that writes files can also write anywhere, and the two
            # are indistinguishable here. The safe default is to refuse and let
            # a reviewer readmit the case; the alternative risks model-written
            # code overwriting a file in CI.
            "import pytest\n\ndef test_a(tmp_path):\n    path = tmp_path / 'a.txt'\n    path.write_text('x')\n    assert path.exists()\n",
            "import pytest\n\ndef test_a():\n    Path('a').unlink()\n",
            "import pytest\n\ndef test_a():\n    os.rename('a', 'b')\n",
        ],
    )
    def test_file_mutation_is_refused_even_when_legitimate(self, content):
        _, issues, usable = validate_content(content, language="python", source="gemini")
        assert usable is False
        assert "forbidden_call" in [issue.code for issue in issues]


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

class TestRendering:
    def test_python_header_and_imports_are_not_model_text(self):
        content = render_python_file(
            "pytest", [_target()], [("test_a", "assert True")], placeholder=False
        )
        assert content.startswith('"""Tests proposed by SmartSDLC Test Generation.')
        assert "import pytest" in content
        assert "def test_a() -> None:" in content
        assert ast.parse(content) is not None

    def test_a_scaffold_is_marked_and_skipped(self):
        content = render_python_file(
            "pytest", [_target()], [("test_a", "")], placeholder=True
        )
        assert "SCAFFOLD" in content
        assert "pytest.mark.skip" in content
        assert ast.parse(content) is not None

    def test_an_indented_body_is_normalised(self):
        content = render_python_file(
            "pytest", [_target()], [("test_a", "  if True:\n      assert True")], placeholder=False
        )
        assert "    if True:\n        assert True" in content
        assert ast.parse(content) is not None

    def test_javascript_imports_the_detected_runner(self):
        content = render_js_file("vitest", [_target()], [("t", "assert(1)")], placeholder=False)
        assert "from 'vitest'" in content
        jest = render_js_file("jest", [_target()], [("t", "assert(1)")], placeholder=False)
        # Jest does not export these from a package named "jest"; asserting the
        # old spelling here would lock in a file that cannot resolve its runner.
        assert "from '@jest/globals'" in jest
        assert "from 'jest'" not in jest

    def test_javascript_scaffold_is_skipped(self):
        content = render_js_file("jest", [_target()], [("t", "")], placeholder=True)
        assert "it.skip" in content
        assert "SCAFFOLD" in content

    def test_a_quote_in_the_suite_name_cannot_escape_the_string(self):
        # The suite name is derived from a provider-supplied path, so it is
        # sanitised where the string literal is built, not by the caller.
        content = render_js_file(
            "jest", [_target()], [("t", "assert(1)")], placeholder=False, suite="it's 'quoted'"
        )
        assert "describe('it s quoted''" not in content
        assert "describe('it s quoted'" in content

    def test_a_quote_in_a_test_name_cannot_escape_the_string(self):
        content = render_js_file(
            "jest", [_target()], [("it's', () => { process.exit(1)", "assert(1)")], placeholder=False
        )
        assert "it('it s', () => { process.exit(1)', () => {" not in content
        assert content.count("it('") == 1


# --------------------------------------------------------------------------
# Target imports
# --------------------------------------------------------------------------

class TestTargetImports:
    """The model writes bodies only, so the import has to be built here.

    Without this, every model-generated file referred to a name it never
    imported: valid Python syntactically, unusable as a test.
    """

    def test_python_imports_come_from_the_target_file(self):
        lines = target_import_lines(
            targets=[_target()], language="python", test_path="tests/test_scm.py"
        )
        assert lines == ["from app.services.scm import normalise_path"]

    def test_python_imports_group_by_module(self):
        targets = [
            _target(name="alpha", qualified_name="alpha", file="app/a.py"),
            _target(name="beta", qualified_name="beta", file="app/a.py"),
            _target(name="gamma", qualified_name="gamma", file="app/b.py"),
        ]
        lines = target_import_lines(
            targets=targets, language="python", test_path="tests/test_x.py"
        )
        assert lines == ["from app.a import alpha, beta", "from app.b import gamma"]

    def test_a_package_init_imports_the_package(self):
        lines = target_import_lines(
            targets=[_target(file="app/services/__init__.py")],
            language="python",
            test_path="tests/test_scm.py",
        )
        assert lines == ["from app.services import normalise_path"]

    def test_the_python_renderer_emits_the_import(self):
        content = render_python_file(
            "pytest",
            [_target()],
            [("test_a", "assert callable(normalise_path)")],
            placeholder=False,
            test_path="tests/test_scm.py",
        )
        assert ast.parse(content) is not None
        # The name the body asserts on is bound, so the file can actually run.
        assert "from app.services.scm import normalise_path" in content

    def test_javascript_imports_are_relative_to_the_test_file(self):
        target = _target(file="src/services/scm.ts", name="normalisePath")
        lines = target_import_lines(
            targets=[target], language="typescript", test_path="tests/unit/scm.test.ts"
        )
        assert lines == ["import { normalisePath } from '../../src/services/scm';"]

    def test_a_non_identifier_is_not_imported(self):
        # A provider-supplied name that is not an identifier cannot be placed in
        # an import clause without becoming a syntax error or an injection.
        target = _target(file="src/a.ts", name="not valid; process.exit(1)")
        assert target_import_lines(
            targets=[target], language="typescript", test_path="tests/a.test.ts"
        ) == []

    def test_the_scaffold_keeps_its_import(self):
        file = deterministic_scaffold(
            path="tests/test_scm.py",
            language="python",
            framework="pytest",
            targets=[_target()],
        )
        assert ast.parse(file.content) is not None
        assert "from app.services.scm import normalise_path" in file.content


# --------------------------------------------------------------------------
# Scaffold
# --------------------------------------------------------------------------

class TestScaffold:
    def test_a_scaffold_is_valid_python(self):
        file = deterministic_scaffold(
            path="tests/test_a.py", language="python", framework="pytest", targets=[_target()]
        )
        assert ast.parse(file.content) is not None
        assert file.source == "deterministic"
        assert file.usable is False

    def test_a_scaffold_names_every_target(self):
        targets = [
            _target(name="alpha", qualified_name="alpha", test_names=["test_alpha"]),
            _target(name="beta", qualified_name="beta", test_names=["test_beta"]),
        ]
        file = deterministic_scaffold(
            path="tests/test_a.py", language="python", framework="pytest", targets=targets
        )
        assert file.test_names == ["test_alpha", "test_beta"]
        assert file.covers == ["alpha", "beta"]

    def test_a_scaffold_is_valid_javascript(self):
        file = deterministic_scaffold(
            path="src/a.test.ts", language="typescript", framework="vitest", targets=[_target()]
        )
        assert "describe(" in file.content
        assert file.usable is False

    def test_every_scaffold_test_is_skipped(self):
        file = deterministic_scaffold(
            path="tests/test_a.py", language="python", framework="pytest", targets=[_target()]
        )
        # A scaffold that runs and asserts nothing would be a false pass.
        assert file.content.count("pytest.mark.skip") == len(file.test_names)


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

@pytest.mark.asyncio
class TestGenerateTestFile:
    async def test_no_model_configured_yields_a_scaffold_and_a_reason(self, no_model):
        result = await generate_test_file(
            path="tests/test_a.py", language="python", framework="pytest", targets=[_target()]
        )
        assert result.file.source == "deterministic"
        assert result.unavailable_reason == "Gemini is not configured for this deployment"

    async def test_a_valid_model_answer_is_used(self, model):
        model('{"tests": [{"name": "test_a", "body": "assert True", "rationale": "r"}]}')
        result = await generate_test_file(
            path="tests/test_a.py", language="python", framework="pytest", targets=[_target()]
        )
        assert result.file.source == "gemini"
        assert result.file.model is not None
        assert result.file.usable is True
        assert ast.parse(result.file.content) is not None

    async def test_an_unusable_answer_falls_back_to_the_scaffold(self, model):
        model("this is not json")
        result = await generate_test_file(
            path="tests/test_a.py", language="python", framework="pytest", targets=[_target()]
        )
        assert result.file.source == "deterministic"
        assert "not valid JSON" in result.unavailable_reason

    async def test_a_model_crash_falls_back_to_the_scaffold(self, monkeypatch):
        monkeypatch.setattr(test_generator.settings, "GEMINI_API_KEY", "key")

        def _boom(*args, **kwargs):
            raise RuntimeError("model exploded")

        monkeypatch.setattr(test_generator, "_generate_content_with_retry", _boom)
        result = await generate_test_file(
            path="tests/test_a.py", language="python", framework="pytest", targets=[_target()]
        )
        assert result.file.source == "deterministic"
        assert result.unavailable_reason

    async def test_duplicate_test_names_are_disambiguated(self, model):
        model('{"tests": [{"name": "test_a", "body": "assert True"}, {"name": "test_a", "body": "assert False"}]}')
        result = await generate_test_file(
            path="tests/test_a.py", language="python", framework="pytest", targets=[_target()]
        )
        assert result.file.test_names == ["test_a", "test_a_2"]
        assert ast.parse(result.file.content) is not None

    async def test_a_forbidden_call_makes_the_file_unusable(self, model):
        body = "    import subprocess\n    subprocess.run(['ls'])"
        model('{"tests": [{"name": "test_a", "body": %s}]}' % json.dumps(body))
        result = await generate_test_file(
            path="tests/test_a.py", language="python", framework="pytest", targets=[_target()]
        )
        assert result.file.usable is False
        assert "forbidden_import" in [issue.code for issue in result.file.validation]

    async def test_no_targets_yields_an_empty_marked_file(self, model):
        model('{"tests": [{"name": "t", "body": "assert True"}]}')
        result = await generate_test_file(
            path="tests/test_a.py", language="python", framework="pytest", targets=[]
        )
        assert result.file.content == ""
        assert result.file.usable is False
        assert result.unavailable_reason == "no targets"

    async def test_generation_never_raises(self, model):
        model("}{ not json at all")
        result = await generate_test_file(
            path="tests/test_a.py", language="python", framework="pytest", targets=[_target()]
        )
        assert isinstance(result.file.content, str)
