"""File screening shared by every security scanner.

A scan reads repository content over the SCM provider, one file at a time, so
the costliest decision is whether to read a file at all. This module centralises
that decision — ignore rules, generated-file rules, binary detection, size caps
and source-text extraction — so the secret, code and dependency scanners agree
on what "scannable" means instead of each drifting into its own rules.

Two rules are non-negotiable here:

* **Never read a file we would not scan.** Downloading a 40 MB archive or a
  lockfile-propagated bundle wastes a provider round trip on every scan.
* **Never emit file content downstream.** :func:`extract_source_lines` returns
  redacted, length-capped lines only. Scanners describe what they matched; they
  do not pass the matching text along, and by the time a finding exists the raw
  line has already been discarded.
"""

from __future__ import annotations

import re

#: Hard cap on a single file's content, matching the repository explorer so a
#: scan and a manual browse agree on what "this file is too big to show" means.
MAX_FILE_BYTES = 200_000

#: Characters sampled when estimating whether a file is binary. Real binary
#: files declare their type in the first few hundred bytes.
BINARY_SNIFF_BYTES = 8192

#: Directories whose contents are never scanned. Minified bundles, vendored
#: dependencies and build output produce findings that are technically real but
#: not actionable — nobody fixes a key inside ``dist/``.
IGNORED_DIRECTORIES = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".idea",
        ".vscode",
        ".vs",
        "node_modules",
        "bower_components",
        "vendor",
        "third_party",
        "thirdparty",
        ".venv",
        "venv",
        "env",
        "virtualenv",
        ".tox",
        ".nox",
        "site-packages",
        "dist",
        "build",
        "out",
        "target",
        "bin",
        "obj",
        "coverage",
        "htmlcov",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".gradle",
        ".next",
        ".nuxt",
        ".svelte-kit",
        ".terraform",
        "Pods",
        "DerivedData",
        ".cache",
        ".parcel-cache",
    }
)

#: Filenames that are generated, vendored or otherwise not source of truth.
IGNORED_FILENAMES = frozenset(
    {
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "npm-shrinkwrap.json",
        "poetry.lock",
        "Pipfile.lock",
        "composer.lock",
        "Cargo.lock",
        "go.sum",
        "gradle.lockfile",
        "Gemfile.lock",
        "packages.lock.json",
    }
)

#: Extension-level ignores. These are lock-adjacent artifacts and blobs.
IGNORED_SUFFIXES = frozenset(
    {
        ".min.js",
        ".min.css",
        ".map",
        ".lock",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".bmp",
        ".ico",
        ".webp",
        ".svgz",
        ".pdf",
        ".zip",
        ".gz",
        ".tgz",
        ".bz2",
        ".xz",
        ".7z",
        ".rar",
        ".jar",
        ".war",
        ".ear",
        ".class",
        ".so",
        ".dylib",
        ".dll",
        ".exe",
        ".bin",
        ".o",
        ".a",
        ".pyc",
        ".pyo",
        ".wasm",
        ".woff",
        ".woff2",
        ".ttf",
        ".eot",
        ".mp3",
        ".mp4",
        ".mov",
        ".avi",
        ".webm",
        ".wav",
        ".ttf",
        ".db",
        ".sqlite",
        ".sqlite3",
        ".mdb",
        ".pack",
        ".idx",
    }
)

#: Files whose *content* is almost never a meaningful secret/code target, even
#: though they are text. Skipping them is a precision win, not just speed.
_SKIP_CONTENT_SUFFIXES = frozenset({".svg", ".log", ".csv", ".tsv"})

_NULL_BYTE = b"\x00"
#: A high proportion of non-text bytes in the sniff window means binary.
_BINARY_BYTE_RATIO = 0.30

#: Manifest filenames the dependency scanner cares about, matched on the exact
#: basename so a random ``go.mod`` inside a test fixture is still found while
#: ``mygo.mod.bak`` is not.
MANIFEST_FILENAMES = frozenset(
    {
        "package.json",
        "package-lock.json",
        "requirements.txt",
        "pyproject.toml",
        "pom.xml",
        "go.mod",
    }
)

#: Requirements-style manifests appear under many names in the wild.
DEPENDENCY_MANIFEST_FILENAMES = frozenset(
    MANIFEST_FILENAMES
    | {
        "requirements-dev.txt",
        "requirements_dev.txt",
        "requirements-prod.txt",
        "requirements-test.txt",
        "requirements_test.txt",
        "dev-requirements.txt",
        "constraints.txt",
    }
)

#: Value patterns that are placeholders rather than secrets. Matching any of
#: these near a credential-shaped token suppresses the finding, which is what
#: keeps ``password = "changeme"`` out of every repository's scan.
_PLACEHOLDER_HINTS = (
    "example",
    "sample",
    "placeholder",
    "dummy",
    "fake",
    "mock",
    "test",
    "spec",
    "changeme",
    "change_me",
    "changethis",
    "your-",
    "your_",
    "yourvalue",
    "insert",
    "replace",
    "todo",
    "fixme",
    "xxxxx",
    "aaaaa",
    "abcdef",
    "123456",
    "password",
    "redacted",
    "removed",
    "notreal",
    "lorem",
    "foo",
    "bar",
    "baz",
    "notset",
    "unset",
    "null",
    "none",
    "undefined",
    "true",
    "false",
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "example.com",
    "example.org",
)

#: ``${VAR}``/``{{ var }}``/``%ENV{VAR}%`` interpolation means the value is
#: supplied at deploy time and is not committed.
_INTERPOLATION_RE = re.compile(
    r"\$\{[^}]*\}|\{\{[^}]*\}\}|%[A-Za-z_][A-Za-z0-9_]*%|<\s*[A-Z_][A-Z0-9_]*\s*>"
)

_ANGLE_URL_CREDENTIALS_RE = re.compile(r"://[^/\s:@]+:[^/\s:@]+@")

#: URLs, UUIDs, dates and hex blobs are high-entropy but never secrets on their
#: own. These are the shapes that make naive entropy scanning useless.
_NON_SECRET_SHAPES = (
    re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I),
    re.compile(r"^[0-9a-f]{32,}$", re.I),
    re.compile(r"^\d+$"),
    re.compile(r"^\d{4}-\d{2}-\d{2}"),
    re.compile(r"^https?://", re.I),
    re.compile(r"^/[\w\-./]*$"),
)


def _segments(path: str) -> list[str]:
    return [segment for segment in path.split("/") if segment]


def basename(path: str) -> str:
    parts = _segments(path)
    return parts[-1] if parts else ""


def is_ignored_path(path: str) -> bool:
    """True when a path is out of scope for scanning.

    Directories are matched case-insensitively because ``Node_Modules`` and
    ``node_modules`` are the same directory on macOS and Windows, and a
    generated bundle should not become a finding just because of casing.
    """
    if not path or not path.strip():
        return True
    segments = _segments(path)
    if not segments:
        return True
    for segment in segments[:-1]:
        if segment.lower() in IGNORED_DIRECTORIES:
            return True
    name = segments[-1]
    lowered = name.lower()
    if lowered in IGNORED_FILENAMES:
        return True
    if any(lowered.endswith(suffix) for suffix in IGNORED_SUFFIXES):
        return True
    return False


def is_manifest_path(path: str) -> bool:
    return basename(path).lower() in DEPENDENCY_MANIFEST_FILENAMES


def looks_like_binary(content: bytes | str, filename: str = "") -> bool:
    """Detect binary content from a byte sample plus the filename.

    A NUL byte is conclusive on its own. Otherwise the sniff window is scored by
    control-character density, with a small allowance for UTF-8 and UTF-16 text
    encodings so a BOM-prefixed source file is not misread as binary.
    """
    lowered = basename(filename).lower()
    if any(lowered.endswith(suffix) for suffix in IGNORED_SUFFIXES):
        return True

    if isinstance(content, str):
        return "\x00" in content[:BINARY_SNIFF_BYTES]

    sample = content[:BINARY_SNIFF_BYTES]
    if not sample:
        return False
    if _NULL_BYTE in sample:
        return True

    # UTF-16 text is half NUL bytes, which the check above would reject; if the
    # bytes decode cleanly as UTF-16, it is text.
    if len(sample) >= 4 and sample[:2] in (b"\xff\xfe", b"\xfe\xff"):
        try:
            sample.decode("utf-16")
            return False
        except UnicodeDecodeError:
            return True

    control = sum(
        1 for byte in sample if byte < 9 or (13 < byte < 32) or byte == 127
    )
    return (control / len(sample)) > _BINARY_BYTE_RATIO


def is_skippable_content(path: str) -> bool:
    """Text formats that generate noise faster than signal."""
    return basename(path).lower().endswith(tuple(_SKIP_CONTENT_SUFFIXES))


def is_placeholder(value: str) -> bool:
    """True when a credential-shaped value is a documented placeholder.

    Two independent signals are used: surrounding interpolation syntax, and a
    literal placeholder word. Requiring interpolation to be absent means a real
    secret that happens to sit in a line mentioning ``test`` is not suppressed
    unless it also *looks* like a placeholder.
    """
    if not value:
        return True
    if _INTERPOLATION_RE.search(value):
        return True
    lowered = value.lower()
    for shape in _NON_SECRET_SHAPES:
        if shape.match(lowered):
            return True
    return any(hint in lowered for hint in _PLACEHOLDER_HINTS)


def strip_url_credentials(line: str) -> str:
    """Blank out ``user:pass@host`` so a connection string is not read as a
    password assignment. The host is kept: it is useful context and is not a
    secret."""
    return _ANGLE_URL_CREDENTIALS_RE.sub("://[REDACTED]@", line)


def extract_source_lines(content: str | bytes, path: str) -> list[str]:
    """Return scannable lines for a file, or ``[]`` when it is not scannable.

    Enforces the size cap and skips binary content and noisy text formats. The
    returned strings are the file's own lines; callers must not store them, and
    the secret scanner additionally redacts before it builds any finding.
    """
    if content is None:
        return []
    if isinstance(content, bytes):
        if looks_like_binary(content, path):
            return []
        try:
            text = content.decode("utf-8", errors="replace")
        except Exception:
            return []
    else:
        text = content
        if looks_like_binary(text, path):
            return []
    if is_skippable_content(path):
        return []
    # Honour the byte cap even for text that decoded from a large buffer.
    if len(text.encode("utf-8", errors="ignore")) > MAX_FILE_BYTES:
        text = text.encode("utf-8")[:MAX_FILE_BYTES].decode("utf-8", errors="ignore")
    return text.splitlines()


def file_extension(path: str) -> str:
    name = basename(path)
    if "." not in name:
        return ""
    return name[name.rindex(".") :].lower()


def normalize_path_for_scan(path: str) -> str:
    """Normalize a scan path to a repository-relative forward-slash path.

    Distinct from :func:`app.schemas.security.normalize_path`, which this
    mirrors: the schema normalizes for *validation*, this one normalizes for
    *fingerprints*. Both are kept so the scanner layer never has to import a
    Pydantic model just to compare two paths.
    """
    if not isinstance(path, str):
        return ""
    cleaned = path.strip().replace("\\", "/")
    cleaned = re.sub(r"^[A-Za-z]:/", "", cleaned)
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
    cleaned = cleaned.lstrip("/")
    parts = [part for part in cleaned.split("/") if part not in ("", ".", "..")]
    return "/".join(parts)
