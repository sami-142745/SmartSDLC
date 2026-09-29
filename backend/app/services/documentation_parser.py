"""Deterministic parsing of a repository's documentation and source docstrings.

Two jobs, both pure and rule-based:

1. **Documentation files.** Detect which files are documentation, classify what
   kind of documentation they are, and measure their structure — headings, code
   blocks, links, badges — without a model. A README is not "good" or "bad"; it
   has, or does not have, an install section, and that is what is recorded.
2. **Source symbol documentation.** Count public symbols and whether each is
   preceded by a docstring (Python, via :mod:`ast`) or a documentation comment
   (JS/TS). This is coverage, so it is reported as a ratio with the undocumented
   names listed, not as a score.

Nothing here reads the network or mutates state.
"""

from __future__ import annotations

import ast
import re
from typing import Iterable

from app.schemas.documentation_intelligence import (
    DocumentationAsset,
    DocumentationAssetKind,
    DocumentationCoverage,
    DocumentationHeading,
    DocumentationLanguage,
    DocumentationLink,
    INSTALL_HEADINGS,
    USAGE_HEADINGS,
)
from app.services import repository_paths
from app.services.repository_paths import normalise_path

#: Extension → documentation language.
_DOC_LANGUAGE_BY_EXTENSION: dict[str, DocumentationLanguage] = {
    ".md": "markdown",
    ".markdown": "markdown",
    ".mdown": "markdown",
    ".mkd": "markdown",
    ".rst": "rst",
    ".adoc": "asciidoc",
    ".asciidoc": "asciidoc",
    ".txt": "text",
}

#: Extension → source language for symbol-coverage measurement.
_SOURCE_LANGUAGE_BY_EXTENSION: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".mts": "typescript",
    ".cts": "typescript",
}

#: Directories whose contents are vendored or generated, never documentation of
#: the project itself. Shared with the other repository engines so a fix to the
#: screening rules applies everywhere.
IGNORED_DIRECTORIES = repository_paths.IGNORED_DIRECTORIES

_MAX_ASSET_BYTES = 400_000
_MAX_HEADINGS = 500
_MAX_LINKS = 500

#: Markdown ATX heading: one to six hashes followed by a space.
_ATX_HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$")
#: Setext underline: a run of ``=`` or ``-``.
_SETEXT_RE = re.compile(r"^[=]{2,}[ \t]*$|^[-]{2,}[ \t]*$")
#: ``[text](target)`` and nested image links.
_MD_LINK_RE = re.compile(r"!?\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
#: Bare ``<http://...>`` autolinks.
_MD_AUTOLINK_RE = re.compile(r"<((?:https?|mailto):[^>\s]+)>")
#: RST external hyperlink: ``\`text <url>\`_``.
_RST_LINK_RE = re.compile(r"`([^`<]+)\s*<([^>]+)>`_")
#: External scheme prefix, so links that are not repository-relative are skipped
#: by the local-link check rather than treated as broken.
_EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "tel:", "ftp://", "//")
#: A single word token, used for a cheap word count.
_WORD_RE = re.compile(r"\b[\w'-]+\b")

_JS_DECLARATION_RE = re.compile(
    r"^[ \t]*export[ \t]+(?:default[ \t]+)?"
    r"(?:(?:async[ \t]+)?function[ \t]+(?P<fn>[A-Za-z_$][\w$]*)"
    r"|class[ \t]+(?P<cls>[A-Za-z_$][\w$]*)"
    r"|interface[ \t]+(?P<iface>[A-Za-z_$][\w$]*)"
    r"|type[ \t]+(?P<type>[A-Za-z_$][\w$]*)"
    r"|(?:const|let|var)[ \t]+(?P<const>[A-Za-z_$][\w$]*))",
    re.MULTILINE,
)


def _extension(path: str) -> str:
    name = (path or "").rsplit("/", 1)[-1]
    if "." not in name:
        return ""
    return name[name.rindex(".") :].lower()


def documentation_language(path: str) -> DocumentationLanguage | None:
    """Documentation format for a path, or ``None`` when it is not documentation."""
    return _DOC_LANGUAGE_BY_EXTENSION.get(_extension(path))


def source_language(path: str) -> str | None:
    """Source language for symbol coverage, or ``None``."""
    return _SOURCE_LANGUAGE_BY_EXTENSION.get(_extension(path))


def is_ignored_path(path: str) -> bool:
    return repository_paths.is_ignored_path(path)


#: Kinds that are recognised even without a documentation extension, because
#: canonical files are commonly shipped as extensionless names (``LICENSE``,
#: ``CONTRIBUTING``, ``CHANGELOG``, ``SECURITY``).
_EXTENSIONLESS_DOC_KINDS = frozenset(
    {
        "readme",
        "license",
        "changelog",
        "contributing",
        "security_policy",
        "code_of_conduct",
    }
)


def is_documentation_path(path: str) -> bool:
    """True when a repository path is a documentation file worth reading."""
    name = normalise_path(path).rsplit("/", 1)[-1].lower()
    # Lock files are ``.txt``/``.lock`` and would otherwise look like prose.
    if name.endswith((".lock", ".min.js", ".map")):
        return False
    if is_ignored_path(path):
        return False
    if documentation_language(path):
        return True
    # A canonical file with no extension is still documentation.
    return documentation_kind(path) in _EXTENSIONLESS_DOC_KINDS


def is_source_path(path: str) -> bool:
    if source_language(path) is None:
        return False
    return not is_ignored_path(path)


def documentation_kind(path: str) -> DocumentationAssetKind:
    """Classify a documentation file by its path.

    Order matters: ``docs/adr/0001-x.md`` is an ADR, not generic documentation,
    and ``SECURITY.md`` is a security policy rather than a README.
    """
    lowered = normalise_path(path).lower()
    name = lowered.rsplit("/", 1)[-1]
    stem = name.rsplit(".", 1)[0]
    segments = lowered.split("/")

    if stem.startswith("readme"):
        return "readme"
    if "changelog" in stem or "changes" in stem or stem.startswith("history"):
        return "changelog"
    if "contributing" in stem or stem.startswith("contributors"):
        return "contributing"
    if (
        stem.startswith("license")
        or stem.startswith("licence")
        or stem in ("copying", "copyright", "notice")
    ):
        return "license"
    if "security" in stem:
        return "security_policy"
    if "code_of_conduct" in stem or "codeofconduct" in stem or "conduct" in stem:
        return "code_of_conduct"
    if "adr" in segments or stem.startswith(("adr-", "adr_")):
        return "adr"
    if any(word in stem for word in ("openapi", "swagger", "api")):
        return "api_reference"
    if any(word in stem for word in ("tutorial", "walkthrough")):
        return "tutorial"
    if any(word in stem for word in ("guide", "howto", "how-to")):
        return "guide"
    if "docs" in segments or "documentation" in segments or stem.startswith("documentation"):
        return "documentation"
    return "other"


def _count_badges(links: Iterable[DocumentationLink]) -> int:
    """Count images that are badges, identified by their target host."""
    count = 0
    for link in links:
        target = link.target.lower()
        if "shields.io" in target or "badge" in target or "badgen" in target:
            count += 1
    return count


def _is_internal(target: str) -> bool:
    target = target.strip()
    if not target:
        return False
    lowered = target.lower()
    if lowered.startswith(_EXTERNAL_PREFIXES):
        return False
    if lowered.startswith("#"):
        return False
    return True


def _resolve_internal(current_path: str, target: str, existing_paths: frozenset[str]) -> bool:
    """True when a repository-relative link points at a file that exists.

    Directory links (ending in ``/``) are resolved against the set of
    directories present, so ``docs/`` is not reported broken merely because it is
    not a file. An anchor-only target is handled by the caller and never reaches
    here.
    """
    target = target.split("#", 1)[0].split("?", 1)[0].strip()
    if not target:
        return True
    if target.startswith(("/", "./", "../")):
        pass
    current_dir = current_path.rsplit("/", 1)[0] if "/" in current_path else ""
    segments = current_dir.split("/") if current_dir else []
    for part in target.replace("\\", "/").split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if not segments:
                return False
            segments.pop()
            continue
        segments.append(part)
    candidate = "/".join(segments)

    if candidate in existing_paths:
        return True
    # ``./setup`` commonly means ``./setup.md`` or a directory with an index.
    for suffix in (".md", ".markdown", ".rst", ".txt", "/index.md", "/README.md", "/readme.md"):
        if f"{candidate}{suffix}" in existing_paths:
            return True
    return False


def parse_documentation(
    path: str,
    content: str | bytes | None,
    *,
    existing_paths: frozenset[str] = frozenset(),
) -> DocumentationAsset:
    """Measure one documentation file's structure.

    ``existing_paths`` is the set of files present in the repository, used only to
    decide whether a repository-relative link resolves. External links are never
    fetched and therefore never judged.
    """
    cleaned = normalise_path(path)
    language = documentation_language(cleaned)
    kind = documentation_kind(cleaned)

    if content is None:
        return DocumentationAsset(path=cleaned, kind=kind, language=language)

    if isinstance(content, bytes):
        source = content.decode("utf-8", errors="replace")
    else:
        source = content
    encoded = source.encode("utf-8", errors="ignore")
    if len(encoded) > _MAX_ASSET_BYTES:
        source = encoded[:_MAX_ASSET_BYTES].decode("utf-8", errors="ignore")

    if language in ("markdown", "text"):
        return _parse_markdown(cleaned, kind, language, source, existing_paths)
    if language == "rst":
        return _parse_rst(cleaned, kind, source, existing_paths)
    # Asciidoc and anything else fall back to a text measurement.
    return _parse_plain(cleaned, kind, language, source)


def _parse_markdown(
    path: str,
    kind: DocumentationAssetKind,
    language: DocumentationLanguage,
    source: str,
    existing_paths: frozenset[str],
) -> DocumentationAsset:
    lines = source.splitlines()
    headings: list[DocumentationHeading] = []
    links: list[DocumentationLink] = []
    images = 0
    code_blocks = 0
    in_fence = False
    fence_token = ""
    prose_words = 0

    for index, raw in enumerate(lines, start=1):
        stripped = raw.strip()
        # Fenced code blocks: count the opening fence, ignore structural markup
        # inside the block so a ``# comment`` in a shell example is not a heading.
        if stripped.startswith("```") or stripped.startswith("~~~"):
            token = stripped[:3]
            if not in_fence:
                in_fence = True
                fence_token = token
                code_blocks += 1
            elif token == fence_token:
                in_fence = False
                fence_token = ""
            continue
        if in_fence:
            continue

        atx = _ATX_HEADING_RE.match(raw)
        if atx:
            headings.append(
                DocumentationHeading(level=len(atx.group(1)), text=atx.group(2).strip(), line=index)
            )
            continue
        # Setext heading: previous non-empty line underlined by = or -.
        if _SETEXT_RE.match(raw) and index >= 2:
            previous = lines[index - 2].strip()
            if previous and not _ATX_HEADING_RE.match(lines[index - 2]):
                level = 1 if raw.strip().startswith("=") else 2
                headings.append(DocumentationHeading(level=level, text=previous, line=index - 1))
                continue

        for match in _MD_LINK_RE.finditer(raw):
            is_image = raw[match.start() : match.start() + 2] == "!["
            alt, target = match.group(1), match.group(2)
            internal = _is_internal(target)
            resolved = (
                _resolve_internal(path, target, existing_paths)
                if internal and not target.strip().startswith("#")
                else (None if not internal else True)
            )
            links.append(
                DocumentationLink(
                    text=alt if is_image else alt,
                    target=target,
                    internal=internal,
                    resolved=resolved,
                )
            )
            if is_image:
                images += 1
        for match in _MD_AUTOLINK_RE.finditer(raw):
            target = match.group(1)
            links.append(DocumentationLink(text=target, target=target, internal=False, resolved=None))

        prose_words += len(_WORD_RE.findall(raw))

    heading_text = [heading.text.strip().lower() for heading in headings]
    has_toc = any(text in ("table of contents", "contents", "toc") for text in heading_text)
    has_install = any(text in INSTALL_HEADINGS for text in heading_text)
    has_usage = any(text in USAGE_HEADINGS for text in heading_text)
    has_examples = any("example" in text for text in heading_text)
    has_license = any("license" in text or "licence" in text for text in heading_text)
    has_contributing = any("contributing" in text for text in heading_text)
    badges = _count_badges(
        [
            link
            for link in links
            if "shields.io" in link.target.lower() or "badge" in link.target.lower()
        ]
    )

    return DocumentationAsset(
        path=path,
        kind=kind,
        language=language,
        size_bytes=len(encoded_or_zero(source)),
        line_count=len(lines),
        word_count=prose_words,
        headings=headings[:_MAX_HEADINGS],
        has_toc=has_toc,
        has_install=has_install,
        has_usage=has_usage,
        has_examples=has_examples,
        has_license=has_license,
        has_contributing=has_contributing,
        code_blocks=code_blocks,
        images=images,
        badges=badges,
        links=links[:_MAX_LINKS],
    )


def encoded_or_zero(source: str) -> bytes:
    return source.encode("utf-8", errors="ignore")


def _parse_rst(
    path: str,
    kind: DocumentationAssetKind,
    source: str,
    existing_paths: frozenset[str],
) -> DocumentationAsset:
    lines = source.splitlines()
    headings: list[DocumentationHeading] = []
    links: list[DocumentationLink] = []
    underline_chars = set("=-~^\"'`#*+")
    for index in range(1, len(lines)):
        underline = lines[index].strip()
        title = lines[index - 1].strip()
        if (
            underline
            and title
            and len(set(underline)) == 1
            and underline[0] in underline_chars
            and len(underline) >= len(title)
        ):
            level = 1 if underline[0] in "=#*" else 2
            headings.append(DocumentationHeading(level=level, text=title, line=index))
    for match in _RST_LINK_RE.finditer(source):
        text, target = match.group(1), match.group(2)
        internal = _is_internal(target)
        resolved = _resolve_internal(path, target, existing_paths) if internal else None
        links.append(DocumentationLink(text=text, target=target, internal=internal, resolved=resolved))

    heading_text = [heading.text.strip().lower() for heading in headings]
    return DocumentationAsset(
        path=path,
        kind=kind,
        language="rst",
        size_bytes=len(encoded_or_zero(source)),
        line_count=len(lines),
        word_count=len(_WORD_RE.findall(source)),
        headings=headings[:_MAX_HEADINGS],
        has_install=any(text in INSTALL_HEADINGS for text in heading_text),
        has_usage=any(text in USAGE_HEADINGS for text in heading_text),
        has_examples=any("example" in text for text in heading_text),
        has_license=any("license" in text for text in heading_text),
        has_contributing=any("contributing" in text for text in heading_text),
        has_toc=any(text in ("table of contents", "contents") for text in heading_text),
        links=links[:_MAX_LINKS],
    )


def _parse_plain(
    path: str,
    kind: DocumentationAssetKind,
    language: DocumentationLanguage | None,
    source: str,
) -> DocumentationAsset:
    # A ``LICENSE`` has no structure to parse and a huge word count would only
    # describe the licence text, so only the facts are recorded.
    return DocumentationAsset(
        path=path,
        kind=kind,
        language=language,
        size_bytes=len(encoded_or_zero(source)),
        line_count=len(source.splitlines()),
        word_count=len(_WORD_RE.findall(source)),
    )


# --------------------------------------------------------------------------
# Source symbol coverage
# --------------------------------------------------------------------------

def _python_symbols(source: str) -> list[tuple[str, str, bool]]:
    tree = ast.parse(source)
    symbols: list[tuple[str, str, bool]] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                symbols.append((node.name, "function", ast.get_docstring(node) is not None))
        elif isinstance(node, ast.ClassDef):
            if not node.name.startswith("_"):
                symbols.append((node.name, "class", ast.get_docstring(node) is not None))
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Dunder and private methods are not part of the public API.
                    if not child.name.startswith("_"):
                        symbols.append(
                            (f"{node.name}.{child.name}", "method", ast.get_docstring(child) is not None)
                        )
    return symbols


def _js_symbols(source: str) -> list[tuple[str, str, bool]]:
    lines = source.splitlines()
    symbols: list[tuple[str, str, bool]] = []
    for match in _JS_DECLARATION_RE.finditer(source):
        name = match.group("fn") or match.group("cls") or match.group("iface") or match.group("type") or match.group("const")
        if not name:
            continue
        if match.group("fn"):
            kind = "function"
        elif match.group("cls"):
            kind = "class"
        elif match.group("iface"):
            kind = "interface"
        elif match.group("type"):
            kind = "type"
        else:
            kind = "const"
        line_index = source.count("\n", 0, match.start())
        documented = _has_leading_doc_comment(lines, line_index)
        symbols.append((name, kind, documented))
    return symbols


def _has_leading_doc_comment(lines: list[str], declaration_line: int) -> bool:
    """True when the declaration is immediately preceded by a doc/line comment."""
    index = declaration_line - 1
    while index >= 0 and not lines[index].strip():
        index -= 1
    if index < 0:
        return False
    previous = lines[index].strip()
    if previous.startswith("//"):
        return True
    if previous.endswith("*/"):
        return True
    # Decorators sit between the comment and the declaration.
    if previous.startswith("@"):
        return _has_leading_doc_comment(lines, index)
    return False


def parse_source_coverage(path: str, content: str | bytes | None) -> DocumentationCoverage | None:
    """Documentation coverage for one source file, or ``None``.

    A syntax error in a Python file yields a coverage row with zero symbols
    rather than an exception: one unparsable file must not abort an analysis of
    the whole repository.
    """
    cleaned = normalise_path(path)
    language = source_language(cleaned)
    if language is None or content is None:
        return None
    if isinstance(content, bytes):
        source = content.decode("utf-8", errors="replace")
    else:
        source = content

    try:
        if language == "python":
            symbols = _python_symbols(source)
        else:
            symbols = _js_symbols(source)
    except (SyntaxError, ValueError, MemoryError, RecursionError):
        return DocumentationCoverage(
            path=cleaned,
            language=language,  # type: ignore[arg-type]
            public_symbols=0,
            documented_symbols=0,
            coverage=1.0,
            undocumented=[],
        )

    total = len(symbols)
    documented = sum(1 for _, _, has_doc in symbols if has_doc)
    coverage = documented / total if total else 1.0
    undocumented = [name for name, _, has_doc in symbols if not has_doc]
    return DocumentationCoverage(
        path=cleaned,
        language=language,  # type: ignore[arg-type]
        public_symbols=total,
        documented_symbols=documented,
        coverage=round(coverage, 4),
        undocumented=undocumented[:100],
    )
