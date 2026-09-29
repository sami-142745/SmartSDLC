"""Tests for the deterministic documentation parser.

Everything here is pure: no database, no network, no model. The tests pin the
rules that turn repository bytes into measured facts — which files are
documentation, what kind they are, what structure they have, and how many public
symbols carry a docstring.
"""

from __future__ import annotations

from app.services import documentation_parser as parser


# --------------------------------------------------------------------------
# Path handling
# --------------------------------------------------------------------------

class TestNormalisePath:
    def test_backslashes_become_forward_slashes(self):
        assert parser.normalise_path("docs\\guide.md") == "docs/guide.md"

    def test_traversal_segments_cannot_escape_the_repository(self):
        result = parser.normalise_path("docs/../../etc/passwd")
        assert ".." not in result.split("/")
        assert result == "docs/etc/passwd"

    def test_leading_current_directory_and_slash_are_stripped(self):
        assert parser.normalise_path("./docs/a.md") == "docs/a.md"
        assert parser.normalise_path("/docs/a.md") == "docs/a.md"

    def test_a_windows_drive_prefix_is_stripped(self):
        assert parser.normalise_path("C:/repo/README.md") == "repo/README.md"

    def test_empty_input_is_empty(self):
        assert parser.normalise_path("") == ""
        assert parser.normalise_path(".") == ""


class TestLanguageDetection:
    def test_markdown_extensions_are_recognised(self):
        assert parser.documentation_language("README.md") == "markdown"
        assert parser.documentation_language("guide.markdown") == "markdown"

    def test_rst_and_text_are_recognised(self):
        assert parser.documentation_language("docs/index.rst") == "rst"
        assert parser.documentation_language("NOTES.txt") == "text"

    def test_a_source_file_is_not_documentation(self):
        assert parser.documentation_language("app/main.py") is None

    def test_source_languages_are_recognised(self):
        assert parser.source_language("a.py") == "python"
        assert parser.source_language("a.tsx") == "typescript"
        assert parser.source_language("a.js") == "javascript"
        assert parser.source_language("README.md") is None


class TestPathClassification:
    def test_ignored_directories_are_detected(self):
        assert parser.is_ignored_path("node_modules/x/README.md")
        assert parser.is_ignored_path("dist/a.md")
        assert parser.is_ignored_path(".git/objects/a.py")
        assert not parser.is_ignored_path("docs/guide.md")

    def test_a_readme_inside_a_vendored_directory_is_not_documentation(self):
        assert not parser.is_documentation_path("node_modules/pkg/README.md")
        assert parser.is_documentation_path("README.md")

    def test_non_documentation_extensions_are_excluded(self):
        assert not parser.is_documentation_path("package.json")
        assert not parser.is_documentation_path("app/main.py")

    def test_sources_inside_vendored_directories_are_excluded(self):
        assert not parser.is_source_path("venv/lib/a.py")
        assert parser.is_source_path("app/main.py")

    def test_an_extensionless_canonical_file_is_still_documentation(self):
        # Otherwise a repository with a perfectly good LICENSE would be reported
        # as unlicensed purely because the file has no extension.
        assert parser.is_documentation_path("LICENSE")
        assert parser.is_documentation_path("CONTRIBUTING")
        assert parser.is_documentation_path("CHANGELOG")
        assert not parser.is_documentation_path("Makefile")


class TestDocumentationKind:
    def test_readme_is_detected_case_insensitively(self):
        assert parser.documentation_kind("README.md") == "readme"
        assert parser.documentation_kind("readme.rst") == "readme"

    def test_canonical_files_are_classified(self):
        assert parser.documentation_kind("CHANGELOG.md") == "changelog"
        assert parser.documentation_kind("CONTRIBUTING.md") == "contributing"
        assert parser.documentation_kind("LICENSE") == "license"
        assert parser.documentation_kind("SECURITY.md") == "security_policy"
        assert parser.documentation_kind("CODE_OF_CONDUCT.md") == "code_of_conduct"

    def test_adr_is_not_generic_documentation(self):
        # Order matters: the more specific rule wins.
        assert parser.documentation_kind("docs/adr/0001-choice.md") == "adr"

    def test_api_and_guide_kinds_are_detected(self):
        assert parser.documentation_kind("docs/api.md") == "api_reference"
        assert parser.documentation_kind("docs/getting-started-guide.md") == "guide"
        assert parser.documentation_kind("docs/tutorial.md") == "tutorial"

    def test_a_generic_markdown_file_is_other(self):
        assert parser.documentation_kind("notes.md") == "other"


# --------------------------------------------------------------------------
# Markdown assets
# --------------------------------------------------------------------------

README = """# Project

[![build](https://img.shields.io/badge/build-passing)](https://ci)
![logo](./assets/logo.png)

## Table of Contents

## Installation

```bash
# this is not a heading
echo hi
```

## Usage

See the [guide](./docs/guide.md) and the [missing](./docs/nope.md) page.

## License

MIT
"""


class TestParseMarkdown:
    def _asset(self, content=README, existing=None):
        return parser.parse_documentation(
            "README.md",
            content,
            existing_paths=frozenset(existing or ["README.md", "docs/guide.md"]),
        )

    def test_headings_are_captured_with_levels(self):
        asset = self._asset()
        texts = {heading.text for heading in asset.headings}
        assert "Installation" in texts
        assert "Project" in texts

    def test_a_comment_inside_a_code_fence_is_not_a_heading(self):
        asset = self._asset()
        assert "this is not a heading" not in {h.text for h in asset.headings}
        assert asset.code_blocks == 1

    def test_section_presence_is_measured(self):
        asset = self._asset()
        assert asset.has_install is True
        assert asset.has_usage is True
        assert asset.has_toc is True
        assert asset.has_license is True

    def test_badges_and_images_are_counted_separately(self):
        asset = self._asset()
        assert asset.badges == 1
        assert asset.images == 1

    def test_internal_links_are_resolved_against_the_tree(self):
        asset = self._asset()
        resolved = {link.target: link.resolved for link in asset.links if link.internal}
        assert resolved["./docs/guide.md"] is True
        assert resolved["./docs/nope.md"] is False

    def test_external_links_are_not_judged(self):
        asset = self._asset()
        external = [link for link in asset.links if not link.internal]
        assert external
        assert all(link.resolved is None for link in external)

    def test_setext_headings_are_detected(self):
        asset = parser.parse_documentation("NOTES.md", "Title\n=====\n\nbody\n")
        assert any(h.level == 1 and h.text == "Title" for h in asset.headings)

    def test_none_content_yields_an_empty_asset(self):
        asset = parser.parse_documentation("README.md", None)
        assert asset.word_count == 0
        assert asset.headings == []
        assert asset.kind == "readme"

    def test_bytes_are_decoded(self):
        asset = parser.parse_documentation("README.md", b"# Hello\n")
        assert asset.headings[0].text == "Hello"

    def test_an_asset_never_truncates_a_heading(self):
        asset = parser.parse_documentation("README.md", "# Hello World\n")
        assert asset.headings[0].text == "Hello World"


# --------------------------------------------------------------------------
# RST assets
# --------------------------------------------------------------------------

class TestParseRst:
    def test_rst_headings_are_detected(self):
        source = "Title\n=====\n\nSection\n-------\n"
        asset = parser.parse_documentation("docs/index.rst", source)
        levels = {h.text: h.level for h in asset.headings}
        assert levels == {"Title": 1, "Section": 2}

    def test_rst_links_are_classified(self):
        source = "See `guide <guide.md>`_ and `site <https://example.com>`_.\n"
        asset = parser.parse_documentation(
            "docs/index.rst",
            source,
            existing_paths=frozenset({"docs/guide.md", "docs/index.rst"}),
        )
        by_target = {link.target: link for link in asset.links}
        assert by_target["guide.md"].internal is True
        assert by_target["guide.md"].resolved is True
        assert by_target["https://example.com"].internal is False
        assert by_target["https://example.com"].resolved is None


# --------------------------------------------------------------------------
# Other documentation
# --------------------------------------------------------------------------

class TestParsePlain:
    def test_a_license_file_records_only_facts(self):
        asset = parser.parse_documentation("LICENSE", "The MIT License\n\nPermission is granted")
        assert asset.kind == "license"
        assert asset.language is None
        assert asset.word_count > 0
        assert asset.headings == []

    def test_asciidoc_falls_back_to_a_plain_measurement(self):
        asset = parser.parse_documentation("docs/guide.adoc", "= Title\n\nSome text.\n")
        assert asset.language == "asciidoc"
        assert asset.word_count > 0


# --------------------------------------------------------------------------
# Source symbol coverage
# --------------------------------------------------------------------------

PYTHON_SOURCE = '''"""Module documentation."""


def public(x):
    """Return x."""
    return x


def _private():
    pass


class Widget:
    """A widget."""

    def render(self):
        pass

    def _internal(self):
        pass
'''


class TestPythonCoverage:
    def test_public_symbols_are_counted_and_docstrings_detected(self):
        row = parser.parse_source_coverage("app/widget.py", PYTHON_SOURCE)
        assert row.public_symbols == 3
        assert row.documented_symbols == 2
        assert row.undocumented == ["Widget.render"]

    def test_private_symbols_are_excluded(self):
        row = parser.parse_source_coverage("app/widget.py", PYTHON_SOURCE)
        assert "_private" not in row.undocumented
        assert "Widget._internal" not in row.undocumented

    def test_coverage_is_a_ratio(self):
        row = parser.parse_source_coverage("app/widget.py", PYTHON_SOURCE)
        assert row.coverage == round(2 / 3, 4)

    def test_a_syntax_error_yields_a_zero_symbol_row_not_an_exception(self):
        row = parser.parse_source_coverage("app/broken.py", "def oops(:\n")
        assert row is not None
        assert row.public_symbols == 0
        assert row.coverage == 1.0

    def test_a_non_source_file_is_skipped(self):
        assert parser.parse_source_coverage("README.md", "# hi\n") is None

    def test_missing_content_is_skipped(self):
        assert parser.parse_source_coverage("app/widget.py", None) is None


JS_SOURCE = """import x from './x';

/** Adds two numbers. */
export function add(a, b) {
  return a + b;
}

// Subtracts two numbers.
export const sub = (a, b) => a - b;

export class Calc {}
"""


class TestJavaScriptCoverage:
    def test_exported_declarations_are_counted(self):
        row = parser.parse_source_coverage("src/math.ts", JS_SOURCE)
        assert row.language == "typescript"
        assert row.public_symbols == 3
        assert set(row.undocumented) == {"Calc"}

    def test_a_leading_doc_comment_counts_as_documented(self):
        row = parser.parse_source_coverage("src/math.ts", JS_SOURCE)
        assert row.documented_symbols == 2

    def test_a_decorator_between_comment_and_declaration_is_tolerated(self):
        source = "// Documented.\n@decorator\nexport function fn() {}\n"
        row = parser.parse_source_coverage("src/deco.ts", source)
        assert row.documented_symbols == 1
