"""Repository path normalisation and vendored-directory screening.

Every repository-level engine — architecture, documentation, test generation —
has to answer the same two questions about a path: what is its repository-
relative form, and is it vendored or generated code that says nothing about what
the maintainers wrote. This module is the single answer to both, so a fix to the
screening rules applies to every engine at once.

Normalisation is a security boundary, not cosmetic. A provider tree entry is
untrusted input; a ``..`` segment can never survive :func:`normalise_path`, so a
crafted entry cannot make an engine read or link to anything outside the
repository it was asked about.
"""

from __future__ import annotations

import re

#: Directories never analysed. Vendored and generated code would dominate every
#: metric while describing nothing the maintainers wrote. Screened
#: case-insensitively, and only on directory segments: the final segment is a
#: file name, so a repository containing a file called ``build`` is unaffected.
IGNORED_DIRECTORIES = frozenset(
    {
        # Version control and editor metadata.
        ".git",
        ".hg",
        ".svn",
        ".idea",
        ".vscode",
        ".vs",
        # Vendored dependencies.
        "node_modules",
        "bower_components",
        "vendor",
        "vendored",
        "third_party",
        "thirdparty",
        # Python environments.
        ".venv",
        "venv",
        "env",
        "virtualenv",
        ".tox",
        ".nox",
        "site-packages",
        # Build output and compiled artefacts.
        "dist",
        "build",
        "out",
        "target",
        "bin",
        "obj",
        "Pods",
        "DerivedData",
        # Coverage and tooling caches.
        "coverage",
        "htmlcov",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".gradle",
        ".cache",
        ".parcel-cache",
        # Framework build directories.
        ".next",
        ".nuxt",
        ".svelte-kit",
        ".terraform",
        # Generated database migrations.
        "migrations",
    }
)

_IGNORED_LOWER = frozenset(name.lower() for name in IGNORED_DIRECTORIES)

_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:/")


def normalise_path(path: str) -> str:
    """Repository-relative forward-slash path with ``.``/``..`` removed.

    Defends against a provider returning a traversal path: a ``..`` segment can
    never survive this, so a crafted tree entry cannot make an engine read
    something outside the repository it was asked about.
    """
    cleaned = (path or "").strip().replace("\\", "/")
    cleaned = _WINDOWS_DRIVE_RE.sub("", cleaned)
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
    cleaned = cleaned.lstrip("/")
    return "/".join(part for part in cleaned.split("/") if part not in ("", ".", ".."))


def is_ignored_path(path: str) -> bool:
    """True when any directory segment of ``path`` is vendored or generated."""
    parts = [segment for segment in normalise_path(path).split("/") if segment]
    if not parts:
        return True
    # The final segment is a file; only directory segments are screened.
    return any(segment.lower() in _IGNORED_LOWER for segment in parts[:-1])


def is_ignored_lower() -> frozenset[str]:
    """The lowercase screening set, for engines that screen inline."""
    return _IGNORED_LOWER
