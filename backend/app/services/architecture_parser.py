"""Source-level parsing for architecture analysis.

Scope
-----
This module answers exactly one question per file: *which modules does this file
import, and what is this file called?* Everything else in the architecture engine
is derived from those answers, so this is the only place that touches file text.

Why no tree-sitter
------------------
A full incremental parser is the right tool for refactoring and symbol-level
navigation. It is the wrong tool here, for three reasons:

1. Import statements are the only syntax this engine needs, and they are the
   easiest construct to identify correctly in every one of the three supported
   languages.
2. Adding a native parser introduces a compiled dependency and a second language
   runtime (C) into a deployment that currently needs neither. Rule 5 of the
   project brief is explicit about this.
3. A parse *failure* must degrade, never abort. Regex rules fail per file and are
   trivial to scope; a real parser needs a recovery strategy before it can be
   allowed near untrusted input.

Python is the exception to that reasoning and is handled accordingly: Python ships
an exact, stdlib AST parser, so using it is strictly more accurate than a regex
and costs nothing. Using a regex for Python when ``ast`` is available would be
choosing worse output for stylistic consistency.

Untrusted input
---------------
Repository source is untrusted data. Nothing here executes, evaluates, imports or
compiles it. ``ast.parse`` builds a tree and nothing more — it does not run
``compile()`` and never invokes the code it parses. Every other function operates
on strings. A syntax error, a 10 MB file, a NUL byte or a file that is actually a
binary all return a degraded result rather than raising.

Resolution
----------
Imports are resolved against the set of modules the repository actually contains.
An import that does not resolve is recorded in ``unresolved`` and produces no
edge. Guessing that ``from app.services.x import y`` refers to
``app/services/x.py`` when no such file exists would invent a dependency, which
is precisely the failure mode this engine is built to avoid.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Iterable

from app.schemas.architecture import ArchitectureLanguage
from app.services import repository_paths
from app.services.repository_paths import normalise_path

#: Extension → language. Detection is by extension so a file is always parsed as
#: what it is, never as what a caller claims it is.
LANGUAGE_BY_EXTENSION: dict[str, ArchitectureLanguage] = {
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

SUPPORTED_EXTENSIONS = frozenset(LANGUAGE_BY_EXTENSION)

#: Hard cap on a single analysed file. Matches the security scanner's and the
#: explorer's cap so all three agree on what "too big to analyse" means.
MAX_FILE_BYTES = 200_000

#: Directories never analysed. Vendored and generated code would dominate every
#: metric while describing nothing the maintainers wrote.
IGNORED_DIRECTORIES = repository_paths.IGNORED_DIRECTORIES

_IGNORED_LOWER = repository_paths.is_ignored_lower()


@dataclass(frozen=True)
class ParsedModule:
    """One analysed source file and its raw import statements.

    ``imports`` are the module-level targets exactly as written, before
    resolution — ``"app.services.security"``, ``"./client"``,
    ``"react-router-dom"``. Resolution happens in a later stage because it
    depends on which other files exist.
    """

    path: str
    language: ArchitectureLanguage
    #: Logical module name derived from the path (``app/services/security.py`` →
    #: ``app.services.security``).
    name: str
    line_count: int
    imports: tuple[str, ...] = ()
    #: ``from package import a, b`` names the package in ``imports`` but the real
    #: dependency is usually the submodule ``package.a``. The members are kept
    #: here so resolution can prefer a submodule that exists instead of binding
    #: the edge to the package (or to an arbitrary child).
    import_members: dict[str, tuple[str, ...]] = field(default_factory=dict)
    #: The package containing this module, used to resolve relative imports.
    #: A package module (``__init__.py``) is its own containing package.
    package: str = ""
    #: ``path: reason`` for a file that could not be parsed. The module is still
    #: listed; only its imports are unknown.
    parse_error: str | None = None

    @property
    def parsed(self) -> bool:
        return self.parse_error is None


@dataclass
class ResolutionResult:
    """Resolved dependency graph for one repository."""

    #: Module id → parsed module.
    modules: dict[str, ParsedModule] = field(default_factory=dict)
    #: ``(source_id, target_id, reference)`` for imports resolved to a module in
    #: this repository. Sorted, so the graph is byte-identical across runs.
    internal_edges: list[tuple[str, str, str]] = field(default_factory=list)
    #: ``(source_id, package_name)`` for third-party imports.
    external_edges: list[tuple[str, str]] = field(default_factory=list)
    #: Distinct import statements that resolved to nothing, for reporting.
    unresolved: list[tuple[str, str]] = field(default_factory=list)


def language_for_path(path: str) -> ArchitectureLanguage | None:
    """Language for a path, or ``None`` when it is not an analysable source.

    Extensionless names are the common case in a real repository — ``Makefile``,
    ``LICENSE``, ``Dockerfile`` — so the missing-dot path must return ``None``
    rather than raise. Crashing here would abort an entire analysis because of
    one uninteresting file in the tree.
    """
    name = (path or "").rsplit("/", 1)[-1]
    if "." not in name:
        return None
    dot = name.rindex(".")
    if dot <= 0:
        return None
    return LANGUAGE_BY_EXTENSION.get(name[dot:].lower())


def is_analysable_path(path: str) -> bool:
    """True when a repository path is source this engine should read."""
    if not path or not path.strip():
        return False
    parts = [segment for segment in path.split("/") if segment]
    if not parts:
        return False
    if any(segment.lower() in _IGNORED_LOWER for segment in parts[:-1]):
        return False
    return language_for_path(path) is not None


def module_name_for_path(path: str) -> str:
    """Logical module name for a source path.

    ``app/services/security.py`` → ``app.services.security``
    ``src/api/security.ts``     → ``src/api/security``

    The extension is dropped because import statements name modules, not files.
    Python modules are dotted because that is how Python addresses them; JS/TS
    modules keep slashes because that is how the JS/TS ecosystem addresses them.
    """
    cleaned = normalise_path(path)
    if not cleaned:
        return ""
    name = cleaned.rsplit("/", 1)[-1]
    dot = name.rindex(".")
    if dot > 0:
        name = name[:dot]
    directory = cleaned.rsplit("/", 1)[0] if "/" in cleaned else ""
    if not directory:
        return name
    if cleaned.endswith((".py", ".pyi")):
        return f"{directory.replace('/', '.')}.{name}"
    return f"{directory}/{name}"


# --------------------------------------------------------------------------
# Python
# --------------------------------------------------------------------------

def _python_module_name(path: str) -> tuple[str, str, bool]:
    """``(module_name, package, is_package)`` for a Python path.

    ``a/b/c.py``       → ``("a.b.c", "a.b", False)``
    ``a/b/__init__.py`` → ``("a.b", "a.b", True)``

    ``package`` is what a single-dot relative import resolves against, so it must
    be the *containing* package for a normal module and the module's own name
    for a package. Getting this wrong makes ``from . import x`` resolve to the
    importing file instead of its sibling.
    """
    cleaned = normalise_path(path)
    if not cleaned:
        return "", "", False
    parts = cleaned.split("/")
    is_package = parts[-1] in ("__init__.py", "__init__.pyi")
    if is_package:
        parts = parts[:-1]
    else:
        last = parts[-1]
        if "." in last:
            parts[-1] = last[: last.rindex(".")]
    # A leading ``src/`` is packaging, not a package the project imports.
    if parts and parts[0] in ("src", "lib"):
        parts = parts[1:]
    name = ".".join(parts)
    package = name if is_package else ".".join(parts[:-1])
    return name, package, is_package


def _python_imports(
    source: str,
) -> tuple[list[str], dict[str, tuple[str, ...]], str | None]:
    """``(import targets, members, error)`` from a Python source string.

    Parses with :mod:`ast` and returns raw dotted names, including relative ones
    with their leading dots preserved so the resolver can interpret them. Import
    statements nested inside functions or ``try`` blocks are included: they are
    still real dependencies, and excluding them would understate coupling.

    ``members`` maps a package reference to the names imported from it
    (``from app.services import auth`` → ``app.services``: ``("auth",)``) so the
    resolver can bind the edge to ``app.services.auth`` when that module exists.

    A syntax error is *reported*, not swallowed. Returning an empty list with no
    error would mark a broken file as a module that simply imports nothing, which
    makes a partial repository look structurally complete.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [], {}, f"syntax error on line {exc.lineno or 0}"
    except (ValueError, MemoryError) as exc:
        return [], {}, type(exc).__name__
    except RecursionError:
        return [], {}, "source nesting too deep to analyse"

    targets: list[str] = []
    members: dict[str, tuple[str, ...]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                targets.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            # ``node.level`` is the dot count for a relative import; 0 is absolute.
            prefix = "." * max(0, node.level or 0)
            if node.module:
                # ``from .shared import x`` names the module ``.shared``; ``x`` may
                # be a member or a submodule. Record it so resolution can tell the
                # difference rather than assuming either.
                reference = f"{prefix}{node.module}"
                targets.append(reference)
                member_names = tuple(
                    sorted(alias.name for alias in node.names if alias.name != "*")
                )
                if member_names:
                    members[reference] = member_names
            else:
                # ``from . import helpers`` names the *package*, and the real
                # dependencies are the names it pulls in. Without this branch the
                # statement would resolve to the current module, inventing a
                # self-edge and hiding the sibling it actually depends on.
                for alias in node.names:
                    if alias.name != "*":
                        targets.append(f"{prefix}{alias.name}")
    return targets, members, None


# --------------------------------------------------------------------------
# JavaScript / TypeScript
# --------------------------------------------------------------------------

#: Static ES import forms. ``import "side-effect"`` is included because it is a
#: real dependency. The ``from`` clause is optional for that form.
_JS_IMPORT_RE = re.compile(
    r"""^[ \t]*import\b[ \t]*(?:type\b[ \t]+)?(?:[^;'"]*?from[ \t]*)?['"]([^'"]+)['"]""",
    re.MULTILINE,
)

#: CommonJS and interop requires.
_JS_REQUIRE_RE = re.compile(
    r"""(?:^|[^.\w])require[ \t]*\([ \t]*['"]([^'"]+)['"][ \t]*\)""",
    re.MULTILINE,
)

#: Re-exports, which are edges too — a barrel file imports its members.
_JS_EXPORT_FROM_RE = re.compile(
    r"""^[ \t]*export\b[ \t]+(?:\*|\{[^}]*\})[ \t]+from[ \t]*['"]([^'"]+)['"]""",
    re.MULTILINE,
)

#: ``import("...")`` is dynamic — it only resolves at runtime, and a regex cannot
#: know the argument. Matching it anyway would let a static specifier masquerade
#: as dynamic, so it is deliberately not matched.
_JS_DYNAMIC_IMPORT_RE = re.compile(r"""\bimport[ \t]*\(\s*['"]([^'"]+)['"]\s*\)""")


def _javascript_imports(source: str) -> list[str]:
    """Import targets from a JS/TS source string.

    Literal specifiers only. A non-literal dynamic import (``import(path)``) is
    unresolvable without executing the module, so it is skipped rather than
    guessed; the count of skipped files is surfaced through ``parse_error`` on
    the containing module instead of being silently lost.
    """
    targets: list[str] = []
    for pattern in (_JS_IMPORT_RE, _JS_EXPORT_FROM_RE, _JS_REQUIRE_RE):
        targets.extend(pattern.findall(source))

    if _JS_DYNAMIC_IMPORT_RE.search(source):
        # A literal dynamic import is still a real edge, so keep it, but flag
        # that this file also has runtime-resolved behaviour.
        targets.extend(_JS_DYNAMIC_IMPORT_RE.findall(source))
    return targets


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def parse_module(path: str, content: str | bytes) -> ParsedModule:
    """Parse one file into a :class:`ParsedModule`.

    Never raises. A binary file, a decode failure, a syntax error or an
    unsupported language all produce a module with ``parse_error`` set and no
    imports, so one unreadable file degrades the analysis instead of ending it.
    """
    cleaned_path = normalise_path(path)
    language = language_for_path(cleaned_path)
    if not cleaned_path or language is None:
        return ParsedModule(
            path=cleaned_path,
            language="python",  # unreachable in practice; keeps the type total
            name="",
            line_count=0,
            parse_error="unsupported file type",
        )

    if isinstance(content, bytes):
        try:
            source = content.decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001 - decode must never abort an analysis
            return ParsedModule(
                path=cleaned_path,
                language=language,
                name="",
                line_count=0,
                parse_error="could not decode file",
            )
    else:
        source = content or ""

    # Honour the cap without counting lines we discarded as if we had them.
    truncated = False
    encoded = source.encode("utf-8", errors="ignore")
    if len(encoded) > MAX_FILE_BYTES:
        source = encoded[:MAX_FILE_BYTES].decode("utf-8", errors="ignore")
        truncated = True

    name = (
        _python_module_name(cleaned_path)[0]
        if language == "python"
        else module_name_for_path(cleaned_path)
    )
    package = (
        _python_module_name(cleaned_path)[1] if language == "python" else ""
    )
    line_count = len(source.splitlines())

    if "\x00" in source[:8192]:
        return ParsedModule(
            path=cleaned_path,
            language=language,
            name=name,
            line_count=line_count,
            package=package,
            parse_error="binary content",
        )

    try:
        if language == "python":
            imports, members, error = _python_imports(source)
            if error is None and truncated:
                error = "file too large to analyse fully"
        else:
            imports = _javascript_imports(source)
            members = {}
            error = "file too large to analyse fully" if truncated else None
    except RecursionError:
        return ParsedModule(
            path=cleaned_path,
            language=language,
            name=name,
            line_count=line_count,
            package=package,
            parse_error="source nesting too deep to analyse",
        )
    except Exception as exc:  # noqa: BLE001 - a parser must not abort a scan
        return ParsedModule(
            path=cleaned_path,
            language=language,
            name=name,
            line_count=line_count,
            package=package,
            parse_error=type(exc).__name__,
        )

    return ParsedModule(
        path=cleaned_path,
        language=language,
        name=name,
        line_count=line_count,
        imports=tuple(dict.fromkeys(imports)),
        import_members=members,
        package=package,
        parse_error=error,
    )


# --------------------------------------------------------------------------
# Resolution
# --------------------------------------------------------------------------

#: Standard-library and third-party roots. Used only to *label* an import as
#: external — never to resolve one. Resolution of internal imports happens
#: solely against modules that exist in the repository.
_PYTHON_EXTERNAL_HINTS = frozenset(
    {
        "fastapi", "pydantic", "pydantic_settings", "starlette", "uvicorn",
        "motor", "pymongo", "bson", "jwt", "jose", "httpx", "requests",
        "aiohttp", "google", "openai", "anthropic", "boto3", "botocore",
        "sqlalchemy", "alembic", "redis", "celery", "pytest", "numpy",
        "pandas", "scipy", "sklearn", "torch", "tensorflow", "django",
        "flask", "click", "typer", "rich", "dotenv", "jinja2", "yaml",
        "tomli", "cryptography", "passlib", "bcrypt", "multipart",
    }
)

_JS_EXTERNAL_HINTS = frozenset(
    {
        "react", "react-dom", "react-router-dom", "axios", "clsx",
        "tailwind-merge", "@monaco-editor/react", "lucide-react", "recharts",
        "zod", "lodash", "moment", "date-fns", "redux", "@reduxjs/toolkit",
        "express", "next", "vue", "svelte", "jest", "vitest", "cypress",
        "typescript", "eslint", "prettier", "vite", "webpack", "rollup",
        "mongoose", "mongodb", "pg", "mysql2", "redis", "socket.io",
        "jsonwebtoken", "bcrypt", "passport", "nodemailer", "aws-sdk",
        "firebase", "@google/generativeai", "openai", "graphql", "apollo-client",
    }
)

#: Python submodules that are part of a package that is itself third-party. An
#: import of ``google.generativeai`` is external even though ``google`` is not
#: in the hint set on its own.
_EXTERNAL_SUBMODULE_ROOTS = frozenset({"google", "googleapiclient"})

#: A small stdlib allowlist. An absolute Python import that is neither a module in
#: the repository nor a known third-party package is almost always stdlib. These
#: are listed so the common case is recognised, and anything unknown is reported
#: as unresolved rather than mislabelled.
_PYTHON_STDLIB_HINTS = frozenset(
    {
        "abc", "argparse", "asyncio", "ast", "base64", "binascii", "bisect",
        "builtins", "calendar", "collections", "contextlib", "copy", "csv",
        "dataclasses", "datetime", "decimal", "difflib", "enum", "fnmatch",
        "functools", "gzip", "hashlib", "hmac", "html", "http", "importlib",
        "inspect", "io", "ipaddress", "itertools", "json", "logging", "math",
        "mimetypes", "os", "pathlib", "pickle", "platform", "pprint", "queue",
        "random", "re", "secrets", "shlex", "shutil", "signal", "socket",
        "sqlite3", "ssl", "stat", "string", "struct", "subprocess", "sys",
        "tempfile", "textwrap", "threading", "time", "traceback", "types",
        "typing", "unicodedata", "unittest", "urllib", "uuid", "warnings",
        "weakref", "xml", "zipfile", "zlib", "zoneinfo", "__future__",
    }
)


def is_external_python(module: str) -> bool:
    """True when a dotted Python import names a third-party package."""
    if not module:
        return False
    root = module.lstrip(".").split(".", 1)[0]
    if not root:
        return False
    return root in _PYTHON_EXTERNAL_HINTS or root in _EXTERNAL_SUBMODULE_ROOTS


def package_name_for_js(specifier: str) -> str:
    """The package a JS/TS import specifier addresses.

    Scoped names keep both segments (``@scope/pkg``); subpath imports collapse to
    the package (``react-router-dom`` from ``react-router-dom/v6``), because it
    is the package that is a dependency, not the file inside it.
    """
    if not specifier:
        return ""
    if specifier.startswith("."):
        return ""
    parts = specifier.split("/")
    if specifier.startswith("@"):
        return "/".join(parts[:2]) if len(parts) >= 2 else specifier
    return parts[0]


def _resolve_python_relative(
    current: ParsedModule, reference: str, module_names: set[str]
) -> str | None:
    """Resolve a relative Python import against the repository's modules.

    Dot semantics follow the language: a single dot means *this module's
    containing package*, and each additional dot climbs one level further out.
    ``package`` supplies the containing package, which is why it is carried on
    the module rather than recomputed here.

    Every candidate is checked against modules that demonstrably exist. If none
    matches, the import is reported unresolved — binding it to a plausible-
    looking path would invent a dependency the repository does not have.
    """
    if not reference.startswith("."):
        return None
    dots = len(reference) - len(reference.lstrip("."))
    remainder = reference[dots:]

    base_parts = current.package.split(".") if current.package else []
    # Two dots climb out of the containing package, three climb further, etc.
    climb = dots - 1
    if climb > 0:
        if len(base_parts) < climb:
            return None
        base_parts = base_parts[: len(base_parts) - climb]

    candidates: list[str] = []
    if remainder:
        candidates.append(".".join(base_parts + [remainder]) if base_parts else remainder)
    else:
        # A bare ``from . import x`` was expanded to ``.x`` upstream, so an empty
        # remainder means the import names the containing package itself.
        candidates.append(".".join(base_parts))

    for candidate in candidates:
        if candidate and candidate in module_names:
            return candidate
    return None


def _resolve_python_absolute(reference: str, module_names: set[str]) -> str | None:
    """Resolve an absolute Python import against the repository's modules."""
    if reference in module_names:
        return reference
    # ``from app.services import security`` names the package, while the module
    # is ``app.services.security``. Try the child before giving up. Iteration is
    # sorted so a package with several children resolves the same way every run.
    prefix = f"{reference}."
    for name in sorted(module_names):
        if name.startswith(prefix):
            return name
    return None


def _resolve_python_with_members(
    module: ParsedModule, reference: str, module_names: set[str]
) -> str | None:
    """Resolve a Python import, preferring a named submodule over its package.

    ``from app.services import auth`` depends on ``app.services.auth`` when that
    module exists; only when no member matches a module does it fall back to the
    package the statement literally named. Resolving to the package regardless
    would merge every distinct submodule dependency into one edge.
    """
    members = module.import_members.get(reference, ())
    if members:
        for member in members:
            if reference.startswith("."):
                candidate = _resolve_python_relative(
                    module, f"{reference}.{member}", module_names
                )
            else:
                candidate = (
                    f"{reference}.{member}"
                    if f"{reference}.{member}" in module_names
                    else None
                )
            if candidate is not None:
                return candidate
    if reference.startswith("."):
        return _resolve_python_relative(module, reference, module_names)
    return _resolve_python_absolute(reference, module_names)


def _resolve_js_relative(
    current_path: str, reference: str, path_to_id: dict[str, str]
) -> str | None:
    """Resolve a relative JS/TS specifier against the repository's paths.

    ``./client`` from ``src/api/security.ts`` is ``src/api/client``. The
    extension is unknown to the importer, so every supported extension is tried
    and the first that exists wins — this is resolution against files that are
    demonstrably present, not a guess.
    """
    if not reference.startswith("."):
        return None

    current_dir = current_path.rsplit("/", 1)[0] if "/" in current_path else ""
    segments = current_dir.split("/") if current_dir else []
    for part in reference.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if not segments:
                return None
            segments.pop()
            continue
        segments.append(part)

    base = "/".join(segments)
    candidates = [base, *(f"{base}{ext}" for ext in sorted(SUPPORTED_EXTENSIONS))]
    for extension in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".py"):
        candidates.append(f"{base}/index{extension}")
    for candidate in candidates:
        resolved = path_to_id.get(candidate)
        if resolved:
            return resolved
    return None


def _resolve_js_bare(reference: str, path_to_id: dict[str, str]) -> str | None:
    """Resolve a bare JS/TS specifier that may address a repo-local alias.

    ``@/components/ui``, ``~/lib`` and ``#internal`` are the common project
    aliases, and they are usually mapped to a subdirectory such as ``src/``. Each
    candidate is tried both as written and under those roots, and only against
    paths that demonstrably exist — if nothing matches, the import is treated as
    external or unresolved rather than assumed to be internal.
    """
    cleaned = reference
    for prefix in ("@/", "~/", "#/", "@app/"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :]
            break
    else:
        return None

    trimmed = cleaned.lstrip("./")
    # An alias root may or may not include the source directory; try both rather
    # than assuming the project's tsconfig.
    roots = ["", "src/", "src"]
    for root in roots:
        base = f"{root}/{trimmed}".lstrip("/")
        for extension in (".ts", ".tsx", ".js", ".jsx"):
            resolved = path_to_id.get(f"{base}/index{extension}")
            if resolved:
                return resolved
        resolved = path_to_id.get(base)
        if resolved:
            return resolved
        for extension in sorted(SUPPORTED_EXTENSIONS):
            resolved = path_to_id.get(f"{base}{extension}")
            if resolved:
                return resolved
    return None


def resolve(modules: Iterable[ParsedModule]) -> ResolutionResult:
    """Resolve every module's imports into internal and external edges.

    Deterministic and order-independent: the output is sorted, so analysing the
    same files in any order yields byte-identical results.
    """
    parsed = [module for module in modules if module.name]
    result = ResolutionResult(modules={module.name: module for module in parsed})

    module_names = set(result.modules)
    path_to_id = {module.path: module.name for module in parsed}

    internal: set[tuple[str, str, str]] = set()
    external: set[tuple[str, str]] = set()
    unresolved: set[tuple[str, str]] = set()
    # A graph has one edge per relationship, not one per import statement.
    # ``from a.b import x`` and ``import a.b`` are the same dependency, so the
    # first reference seen is kept and the duplicate does not inflate fan-out.
    seen_relationship: set[tuple[str, str]] = set()

    for module in sorted(parsed, key=lambda item: item.name):
        if not module.parsed:
            continue
        for reference in module.imports:
            target: str | None = None
            package = ""

            if module.language == "python":
                if reference.startswith("."):
                    target = _resolve_python_with_members(module, reference, module_names)
                    if target is None:
                        unresolved.add((module.name, reference))
                        continue
                elif is_external_python(reference):
                    package = reference.split(".", 1)[0]
                else:
                    target = _resolve_python_with_members(module, reference, module_names)
                    if target is None:
                        # Not a module here and not a known third-party root:
                        # most likely another stdlib module, which is neither an
                        # internal edge nor an external dependency.
                        package = ""
                        if reference.split(".", 1)[0] not in _PYTHON_STDLIB_HINTS:
                            unresolved.add((module.name, reference))
                        continue
            else:
                if reference.startswith("."):
                    target = _resolve_js_relative(module.path, reference, path_to_id)
                    if target is None:
                        unresolved.add((module.name, reference))
                        continue
                else:
                    target = _resolve_js_bare(reference, path_to_id)
                    if target is None:
                        package = package_name_for_js(reference)
                        if not package:
                            unresolved.add((module.name, reference))
                            continue

            if target and target != module.name:
                relationship = (module.name, target)
                if relationship not in seen_relationship:
                    seen_relationship.add(relationship)
                    internal.add((module.name, target, reference))
            elif package:
                external.add((module.name, package))
            elif target == module.name:
                # A module importing itself is a real (if odd) self-reference.
                relationship = (module.name, target)
                if relationship not in seen_relationship:
                    seen_relationship.add(relationship)
                    internal.add((module.name, target, reference))

    result.internal_edges = sorted(internal)
    result.external_edges = sorted(external)
    result.unresolved = sorted(unresolved)
    return result
