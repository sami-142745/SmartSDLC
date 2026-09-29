"""Deterministic discovery of public code that no test file references.

This module decides *what* deserves a test. It is pure: it reads repository files
and returns a ranked list of targets, and it never imports the model, the
database, or the network. That separation is the point — a suggestion that a
symbol is untested must be reproducible from the repository alone, or a reviewer
has no way to check it.

How "untested" is decided
-------------------------
A symbol is public if its name is not underscore-prefixed (dunders excepted).
It is considered referenced when its *name* appears as an identifier token in the
content of any test file. Token matching is deliberately coarse: it catches
``from x import foo``, ``x.foo()`` and ``monkeypatch.setattr(x, "foo", ...)``
alike, because the alternative — resolving the import graph and the attribute
access chain — cannot be done soundly with regexes, and a wrong "untested"
verdict that survives review is worse than a missed target.

Two things this parser will not do
----------------------------------
* It does not decide whether the code is good. A symbol with no test reference
  may be dead code, may be exercised through a plugin registry, or may be public
  only for documentation. The evidence is attached to every target so a reviewer
  can overrule it.
* It does not judge coverage. Without executing anything, the fraction of lines a
  test touches is unknowable, and reporting a coverage percentage here would be a
  fabricated number. The number this engine reports is the count of unreferenced
  public symbols, which is measured.

Names are matched as tokens, so a common name like ``main`` or ``Client`` will
report as referenced when any test mentions it. This errs towards fewer targets,
never towards falsely accusing the code of being untested.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from app.schemas.test_generation import (
    DEFAULT_MAX_TARGETS,
    MAX_TARGETS,
    TEST_DIRECTORIES,
    TEST_FILE_STEMS,
    SymbolKind,  # noqa: F401 - re-exported for callers building symbol rows
    TestFramework,
    TestLanguage,
    TestTarget,
    UntestedSymbol,
)
from app.services.repository_paths import is_ignored_path, normalise_path

#: Extension → language. Only languages with a usable structural or
#: declaration-based parser are included; anything else is not analysable here.
_LANGUAGE_BY_EXTENSION: dict[str, TestLanguage] = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
}

_TEST_DIRECTORY_LOWER = frozenset(name.lower() for name in TEST_DIRECTORIES)
_TEST_STEM_LOWER = frozenset(name.lower() for name in TEST_FILE_STEMS)

#: Identifier tokens. Deliberately simple: a test file is data, and the only
#: question asked of it is which names occur.
_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

#: Python branch constructs. Counted, never interpreted.
_BRANCH_NODES = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.Try,
    ast.BoolOp,
    ast.IfExp,
    ast.comprehension,
    ast.Match,
)

#: Branch keywords in JavaScript and TypeScript, used because there is no
#: JavaScript parser available here and pretending otherwise would produce a
#: number nobody can reproduce.
_JS_BRANCH_RE = re.compile(
    r"\b(if|for|while|switch|catch)\s*\(|\?\?|\?\.|&&|\|\||\?[^.?]|:"
)

#: Declaration forms in JavaScript and TypeScript. ``export`` is optional but a
#: non-exported declaration must start at column 0, so a local ``const`` inside a
#: function body is not mistaken for a public symbol.
_JS_DECLARATION_RE = re.compile(
    r"^(?P<indent>[ \t]*)"
    r"(?P<export>export\s+(?:default\s+)?)?"
    r"(?:async\s+)?"
    r"(?P<kind>function\*?|class|const|let|var|interface|enum|type)\s+"
    r"(?P<name>[A-Za-z_$][\w$]*)",
    re.MULTILINE,
)

_JS_KIND_MAP = {
    "function": "function",
    "function*": "function",
    "class": "class",
    "const": "function",
    "let": "function",
    "var": "function",
    "interface": "class",
    "enum": "class",
    "type": "class",
}

#: Framework evidence, checked in this order. A repository that configures both
#: jest and vitest is ambiguous; the first match wins and the reason is reported
#: so the caller can show why.
_FRAMEWORK_EVIDENCE: tuple[tuple[TestFramework, tuple[str, ...]], ...] = (
    ("vitest", ("vitest.config.ts", "vitest.config.js", "vitest.config.mts", "vitest.config.mts")),
    ("jest", ("jest.config.js", "jest.config.ts", "jest.config.mjs", "jest.config.json")),
    ("pytest", ("conftest.py", "pytest.ini", "tox.ini")),
)


@dataclass(frozen=True)
class RepositoryFile:
    """One repository file and its content, as read from the provider."""

    path: str
    content: str


def language_for_path(path: str) -> TestLanguage | None:
    """Language for a path, or ``None`` when it is not analysable source.

    Extensionless names (``Makefile``, ``LICENSE``) are the common case in a real
    repository, so a missing dot returns ``None`` rather than raising. Crashing
    here would abort generation because of one uninteresting file in the tree.
    """
    name = (path or "").rsplit("/", 1)[-1]
    if "." not in name:
        return None
    dot = name.rindex(".")
    if dot <= 0:
        return None
    return _LANGUAGE_BY_EXTENSION.get(name[dot:].lower())


def is_test_path(path: str) -> bool:
    """True when a path is a test file, by directory convention or by name.

    Both are checked because real repositories use either: ``tests/test_x.py``
    and ``src/x/__tests__/x.test.js`` are the same intent.

    Only files in a language this engine can parse count. A Go or Ruby test file
    is a test file to a human, but this engine extracts no symbols from Go or
    Ruby, so reading it would only ever add tokens that could suppress a target
    for code in a language we *can* read. Not counting it can propose a target a
    reader considers tested; counting it could hide one that is not.
    """
    clean = normalise_path(path)
    if not clean or is_ignored_path(clean):
        return False
    if language_for_path(clean) is None:
        return False
    parts = clean.split("/")
    if any(segment.lower() in _TEST_DIRECTORY_LOWER for segment in parts[:-1]):
        return True
    name = parts[-1].lower()
    # ``test_x.py`` / ``x.test.ts`` / ``x_spec.rb``. Matched against the full
    # file name: the pattern includes the dot that separates the stem from the
    # extension, so testing a de-extensioned stem can never match ``x.test.ts``.
    if name.startswith(("test_", "test-")) or name.endswith(("_test", "-test")):
        return True
    if ".test." in name or ".spec." in name:
        return True
    return any(f".{stem}." in name for stem in TEST_FILE_STEMS)


def is_source_path(path: str) -> bool:
    """True when a path is analysable source that is not itself a test file."""
    clean = normalise_path(path)
    if not clean or is_ignored_path(clean):
        return False
    if is_test_path(clean):
        return False
    return language_for_path(clean) is not None


def _is_public(name: str) -> bool:
    """A public name is not underscore-prefixed, except dunders."""
    if not name.startswith("_"):
        return True
    return name.startswith("__") and name.endswith("__") and len(name) > 4


def _python_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Reconstruct a callable signature from the parsed arguments.

    Rebuilt rather than sliced from source because a slice depends on formatting
    the repository's authors chose; this depends only on the code.
    """
    args = node.args
    parts: list[str] = []
    positional = list(args.posonlyargs) + list(args.args)
    defaults: list[ast.expr | None] = [None] * (len(positional) - len(args.defaults)) + list(args.defaults)
    for arg, default in zip(positional, defaults):
        text = arg.arg
        if arg.annotation is not None:
            try:
                text = f"{text}: {ast.unparse(arg.annotation)}"
            except Exception:  # noqa: BLE001 - a signature is best effort
                text = arg.arg
        if default is not None:
            try:
                text = f"{text} = {ast.unparse(default)}"
            except Exception:  # noqa: BLE001 - a signature is best effort
                pass
        parts.append(text)
    if args.vararg is not None:
        parts.append(f"*{args.vararg.arg}")
    elif args.kwonlyargs:
        parts.append("*")
    for arg, default in zip(args.kwonlyargs, args.kw_defaults):
        text = arg.arg
        if default is not None:
            try:
                text = f"{text} = {ast.unparse(default)}"
            except Exception:  # noqa: BLE001 - a signature is best effort
                pass
        parts.append(text)
    if args.kwarg is not None:
        parts.append(f"**{args.kwarg.arg}")
    returns = ""
    if node.returns is not None:
        try:
            returns = f" -> {ast.unparse(node.returns)}"
        except Exception:  # noqa: BLE001 - a signature is best effort
            returns = ""
    return f"{node.name}({', '.join(parts)}){returns}"


def _branch_score(node: ast.AST) -> int:
    """Count branch constructs under a node. A size hint, not a metric."""
    return sum(1 for child in ast.walk(node) if isinstance(child, _BRANCH_NODES))


def parse_python_symbols(path: str, content: str) -> tuple[UntestedSymbol, ...]:
    """Extract public module-level and class-level symbols from Python source.

    Returns an empty tuple for source that cannot be parsed. A single unreadable
    file must not abort generation for the whole repository, and the caller can
    tell "no symbols" from "no file" by checking the file was analysable.
    """
    try:
        tree = ast.parse(content or "")
    except (SyntaxError, ValueError, RecursionError):
        return ()

    found: list[UntestedSymbol] = []

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _is_public(node.name):
            found.append(
                UntestedSymbol(
                    name=node.name,
                    qualified_name=node.name,
                    kind="function",
                    file=path,
                    line=node.lineno,
                    signature=_python_signature(node),
                    has_docstring=ast.get_docstring(node) is not None,
                    branch_score=_branch_score(node),
                )
            )
        elif isinstance(node, ast.ClassDef) and _is_public(node.name):
            found.append(
                UntestedSymbol(
                    name=node.name,
                    qualified_name=node.name,
                    kind="class",
                    file=path,
                    line=node.lineno,
                    signature=f"class {node.name}",
                    has_docstring=ast.get_docstring(node) is not None,
                    branch_score=_branch_score(node),
                )
            )
            # Methods are public API too, and the most commonly untested part of
            # a class. ``__init__`` is excluded: it is the class's own
            # construction, tested through the class.
            for child in node.body:
                if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if not _is_public(child.name) or child.name == "__init__":
                    continue
                found.append(
                    UntestedSymbol(
                        name=child.name,
                        qualified_name=f"{node.name}.{child.name}",
                        kind="method",
                        file=path,
                        line=child.lineno,
                        signature=f"{node.name}.{_python_signature(child)}",
                        has_docstring=ast.get_docstring(child) is not None,
                        branch_score=_branch_score(child),
                    )
                )

    return tuple(sorted(found, key=lambda symbol: (symbol.file, symbol.line, symbol.qualified_name)))


def _js_signature(text: str, declaration_end: int) -> str:
    """Slice a declaration head from source, bounded, with balanced brackets."""
    head = text[declaration_end : declaration_end + 200]
    for stop in ("{", ";", "\n"):
        index = head.find(stop)
        if index != -1:
            head = head[:index]
    return " ".join(head.split())[:160]


def parse_js_symbols(path: str, content: str) -> tuple[UntestedSymbol, ...]:
    """Extract exported and top-level JavaScript/TypeScript declarations.

    Declaration matching, not parsing. Without a JavaScript parser this is a
    best-effort read of the file's shape, which is why a match requires a name
    and a recognised keyword: an ambiguous line produces no symbol rather than a
    fabricated one.
    """
    text = content or ""
    found: list[UntestedSymbol] = []
    seen: set[tuple[str, int]] = set()
    for match in _JS_DECLARATION_RE.finditer(text):
        exported = bool(match.group("export"))
        indent = match.group("indent")
        # A non-exported declaration must be top level; an indented one is a
        # local variable inside a function body.
        if not exported and indent:
            continue
        name = match.group("name")
        kind_text = match.group("kind")
        if not _is_public(name):
            continue
        if name in ("default",):
            continue
        line = text.count("\n", 0, match.start()) + 1
        if (name, line) in seen:
            continue
        seen.add((name, line))
        line_end = text.find("\n", match.end())
        line_text = text[match.start() : line_end if line_end != -1 else len(text)]
        # Slice from the keyword, not the name, so the signature keeps the
        # declaration form a reader needs: ``function boot(): void``.
        offset = match.start("kind") - match.start()
        found.append(
            UntestedSymbol(
                name=name,
                qualified_name=name,
                kind=_JS_KIND_MAP.get(kind_text, "function"),
                file=path,
                line=line,
                signature=_js_signature(line_text, offset),
                has_docstring="/**" in line_text or line_text.strip().startswith("//"),
                branch_score=len(_JS_BRANCH_RE.findall(text[match.start() : match.start() + 4000])),
            )
        )
    return tuple(sorted(found, key=lambda symbol: (symbol.file, symbol.line, symbol.qualified_name)))


def parse_symbols(path: str, content: str) -> tuple[UntestedSymbol, ...]:
    """Parse public symbols for a path, dispatching on language."""
    language = language_for_path(path)
    if language == "python":
        return parse_python_symbols(path, content)
    if language in ("javascript", "typescript"):
        return parse_js_symbols(path, content)
    return ()


def tokenize_names(content: str) -> frozenset[str]:
    """Every identifier token in a test file.

    Coarse by design: it answers "is this name mentioned", not "is this name
    called", because only running the tests would answer the second question.
    """
    return frozenset(_IDENTIFIER_RE.findall(content or ""))


def detect_framework(paths: Sequence[str], contents: Sequence[str] | None = None) -> TestFramework:
    """Detect the repository's test framework from configuration and file names.

    Configuration wins over naming, because a repository can contain both a
    ``jest.config.js`` for its frontend and a ``conftest.py`` for its backend.
    Within one language, explicit configuration is preferred; Python falls back
    to ``pytest`` on a ``test_*.py`` name because that convention is shared by
    pytest, unittest and nose and picking the most common is more useful than
    reporting nothing.
    """
    clean = [normalise_path(path) for path in paths]
    names = {path.rsplit("/", 1)[-1] for path in clean}
    has_python_tests = any(path.endswith(".py") for path in clean if is_test_path(path))
    has_js_tests = any(
        language_for_path(path) in ("javascript", "typescript") for path in clean if is_test_path(path)
    )
    for framework, markers in _FRAMEWORK_EVIDENCE:
        if names & set(markers):
            if framework in ("jest", "vitest") and not has_js_tests:
                continue
            if framework == "pytest" and not has_python_tests:
                continue
            return framework
    if has_js_tests and contents is not None:
        joined = "\n".join(contents).lower()
        if "vitest" in joined:
            return "vitest"
        if "jest" in joined:
            return "jest"
    if has_python_tests:
        return "pytest"
    if has_js_tests:
        return "jest"
    return "unknown"


def proposed_test_names(symbol: UntestedSymbol) -> list[str]:
    """Deterministic test function names that would exercise a symbol.

    Named from the symbol rather than numbered, so re-running generation on an
    unchanged repository proposes the same names and a diff of two previews is
    readable.
    """
    base = re.sub(r"[^0-9a-zA-Z]+", "_", symbol.qualified_name).strip("_").lower()
    return [
        f"test_{base}_behaviour",
        f"test_{base}_handles_invalid_input",
        f"test_{base}_edge_cases",
    ]


def _priority(symbol: UntestedSymbol, *, has_test_suite: bool) -> int:
    """Rank a target from measured facts only. Higher means propose it first.

    A fixed function, so the same repository always produces the same ordering.
    The weights encode only that documented, branching, class-level API is more
    worth a test than an undocumented one-line helper — a judgement worth
    disagreeing with, but stated here rather than hidden in a model prompt.
    """
    score = 50
    if not has_test_suite:
        # Nothing is tested at all, so every target is a first priority.
        score += 20
    if symbol.has_docstring:
        # Documented API is API someone intended to use.
        score += 10
    if symbol.branch_score >= 3:
        score += 10
    if symbol.kind == "class":
        score += 5
    if symbol.kind == "method":
        score += 5
    return max(0, min(100, score))


def _python_parse_error(item: RepositoryFile) -> str | None:
    """A one-line report for source that could not be parsed, or ``None``.

    Reported rather than swallowed: a file that fails to parse contributes no
    symbols, so a repository with one broken file would otherwise look as though
    the file had no public API.
    """
    if not (item.content or "").strip():
        return None
    try:
        ast.parse(item.content)
    except SyntaxError as exc:
        return f"{item.path}: could not be parsed (line {exc.lineno}: {exc.msg})"
    except (ValueError, RecursionError) as exc:
        return f"{item.path}: could not be parsed ({type(exc).__name__})"
    return None


@dataclass(frozen=True)
class TargetSelection:
    """Everything the deterministic pass found, before any model runs."""

    framework: TestFramework = "unknown"
    test_directories: tuple[str, ...] = ()
    test_files: tuple[str, ...] = ()
    symbols: tuple[UntestedSymbol, ...] = ()
    targets: tuple[TestTarget, ...] = ()
    source_files: int = 0
    public_symbols: int = 0
    untested_symbols: int = 0
    truncated: bool = False
    errors: list[str] = field(default_factory=list)


def find_test_targets(
    files: Iterable[RepositoryFile],
    *,
    max_targets: int = DEFAULT_MAX_TARGETS,
) -> TargetSelection:
    """Rank public symbols that no test file references.

    ``max_targets`` is clamped to the hard ceiling in the schemas: generation
    cost is per target, so an unbounded request is neither fast nor reviewable.
    An explicit ``0`` clamps to ``1`` rather than falling back to the default, so
    a caller asking for nothing does not silently get everything.
    """
    requested = DEFAULT_MAX_TARGETS if max_targets is None else int(max_targets)
    limit = max(1, min(requested, MAX_TARGETS))

    materialised = list(files)
    test_files = [item for item in materialised if is_test_path(item.path)]
    source_files = [item for item in materialised if is_source_path(item.path)]

    referenced: set[str] = set()
    references_by_name: dict[str, list[str]] = {}
    for item in test_files:
        names = tokenize_names(item.content)
        referenced |= names
        for name in names:
            references_by_name.setdefault(name, []).append(item.path)

    symbols: list[UntestedSymbol] = []
    errors: list[str] = []
    for item in source_files:
        symbols.extend(parse_symbols(item.path, item.content))
        if language_for_path(item.path) == "python":
            error = _python_parse_error(item)
            if error:
                errors.append(error)
    symbols.sort(key=lambda symbol: (symbol.file, symbol.line, symbol.qualified_name))

    has_test_suite = bool(test_files)
    untested: list[UntestedSymbol] = []
    for symbol in symbols:
        hits = sorted(set(references_by_name.get(symbol.name, ())))
        if hits:
            continue
        untested.append(symbol)

    ranked = sorted(
        untested,
        key=lambda symbol: (
            -_priority(symbol, has_test_suite=has_test_suite),
            symbol.file,
            symbol.line,
        ),
    )
    selected = ranked[:limit]

    targets = tuple(
        TestTarget(
            name=symbol.name,
            qualified_name=symbol.qualified_name,
            kind=symbol.kind,
            file=symbol.file,
            line=symbol.line,
            signature=symbol.signature,
            reason="no_test_reference" if has_test_suite else "no_test_suite",
            evidence=(
                f"{len(test_files)} test file(s) in the repository reference none of "
                f"`{symbol.name}`."
                if has_test_suite
                else "The repository has no recognisable test file, so no symbol is "
                "referenced by a test."
            ),
            priority=_priority(symbol, has_test_suite=has_test_suite),
            test_names=proposed_test_names(symbol),
        )
        for symbol in selected
    )

    directories = tuple(
        sorted(
            {
                segment
                for path in (item.path for item in test_files)
                for segment in normalise_path(path).split("/")[:-1]
                if segment.lower() in _TEST_DIRECTORY_LOWER
            }
        )
    )

    return TargetSelection(
        framework=detect_framework(
            [item.path for item in materialised],
            [item.content for item in test_files],
        ),
        test_directories=directories,
        test_files=tuple(sorted(item.path for item in test_files)),
        symbols=tuple(symbols),
        targets=targets,
        source_files=len(source_files),
        public_symbols=len(symbols),
        untested_symbols=len(untested),
        truncated=len(ranked) > len(selected),
        errors=errors,
    )


__all__ = [
    "RepositoryFile",
    "TargetSelection",
    "detect_framework",
    "find_test_targets",
    "is_source_path",
    "is_test_path",
    "language_for_path",
    "parse_js_symbols",
    "parse_python_symbols",
    "parse_symbols",
    "proposed_test_names",
    "tokenize_names",
]
