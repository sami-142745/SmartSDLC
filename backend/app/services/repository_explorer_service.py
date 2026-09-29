"""Repository tree and file-content services for the Explorer page.

The provider's recursive tree listing is a flat array of paths, which is cheap
to fetch but awkward to render. :func:`build_tree` turns it into a
breadth-first, directory-first ordered entry list where every entry carries its
``depth``, so the client can render a GitHub-style outline with plain
indentation and no client-side tree construction.

Size discipline
---------------
A recursive tree for a large monorepo can contain hundreds of thousands of
entries. ``MAX_TREE_ENTRIES`` caps what is returned; when the cap bites,
``truncated`` is set to True and the reported counts describe the *returned*
entries, so the UI can state plainly that the listing is partial rather than
implying the repository is fully enumerated. Provider-side truncation (GitHub's
own ``truncated`` flag) is reported separately via ``provider_truncated`` on the
result of :func:`build_tree` so the two causes are never conflated.

File reads are likewise capped by ``MAX_FILE_BYTES`` and screened for binary
content, because a Monaco preview of a PNG is neither useful nor safe to render.
"""

from __future__ import annotations

from typing import Any

from app.schemas.repository_intelligence import (
    RepositoryFileContent,
    RepositoryTree,
    RepositoryTreeEntry,
)

MAX_TREE_ENTRIES = 5000
MAX_FILE_BYTES = 200_000

TYPE_BLOB = "blob"
TYPE_TREE = "tree"

#: Extension to Monaco language id. Covers the languages SmartSDLC reviews most;
#: an unmapped extension is reported as ``None`` and Monaco falls back to plain
#: text, which is the correct behaviour for an unknown file type.
LANGUAGE_BY_EXTENSION: dict[str, str] = {
    ".ts": "typescript",
    ".tsx": "typescript",
    ".mts": "typescript",
    ".cts": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".py": "python",
    ".pyi": "python",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "csharp",
    ".c": "c",
    ".h": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cxx": "cpp",
    ".swift": "swift",
    ".m": "objective-c",
    ".mm": "objective-c",
    ".scala": "scala",
    ".dart": "dart",
    ".ex": "elixir",
    ".exs": "elixir",
    ".erl": "erlang",
    ".hs": "haskell",
    ".lua": "lua",
    ".pl": "perl",
    ".pm": "perl",
    ".r": "r",
    ".jl": "julia",
    ".zig": "zig",
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
    ".ps1": "powershell",
    ".sql": "sql",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "scss",
    ".sass": "scss",
    ".less": "less",
    ".vue": "html",
    ".svelte": "html",
    ".json": "json",
    ".jsonc": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "ini",
    ".ini": "ini",
    ".cfg": "ini",
    ".xml": "xml",
    ".md": "markdown",
    ".mdx": "markdown",
    ".rst": "markdown",
    ".txt": "plaintext",
    ".env": "ini",
    ".dockerfile": "dockerfile",
    ".tf": "hcl",
    ".proto": "proto",
    ".graphql": "graphql",
    ".gql": "graphql",
}

_FILENAME_LANGUAGES: dict[str, str] = {
    "dockerfile": "dockerfile",
    "makefile": "plaintext",
    "gemfile": "ruby",
    "rakefile": "ruby",
    "procfile": "yaml",
    "cmakelists.txt": "cmake",
}


def language_for_path(path: str) -> str | None:
    """Best-effort Monaco language id for a repository path."""
    lowered = (path or "").lower()
    filename = lowered.rsplit("/", 1)[-1]
    if filename in _FILENAME_LANGUAGES:
        return _FILENAME_LANGUAGES[filename]
    if filename.startswith("dockerfile"):
        return "dockerfile"
    if "." not in filename:
        return None
    _, _, extension = filename.rpartition(".")
    return LANGUAGE_BY_EXTENSION.get(f".{extension}")


def looks_binary(sample: bytes) -> bool:
    """Heuristic binary detection used to keep binaries out of the editor.

    A NUL byte in the first chunk is the classic signal and matches git's own
    heuristic closely enough for a preview surface.
    """
    return b"\x00" in sample[:8000]


def _sort_key(entry: dict[str, Any]) -> tuple:
    """Hierarchical sort so every entry follows its parent directory.

    Sorting on the basename alone would interleave siblings, because
    ``src/components`` sorts under "c" and would jump ahead of ``docs`` even
    though its parent ``src`` comes later. Comparing the tuple of path segments
    — with directories ahead of files at every level — keeps a flat list
    renderable as a proper outline.
    """
    path = str(entry.get("path", ""))
    segments = path.split("/")
    # (is_file_flag, segment) per level: 0 sorts directories before files.
    key: list[tuple[int, str]] = []
    for index, segment in enumerate(segments):
        is_last = index == len(segments) - 1
        is_directory = entry.get("type") == TYPE_TREE
        rank = 0 if (is_directory or not is_last) else 1
        key.append((rank, segment.lower()))
    return tuple(key)


def build_tree(
    payload: dict[str, Any] | None,
    *,
    owner: str = "",
    repository: str = "",
    ref: str | None = None,
    max_entries: int = MAX_TREE_ENTRIES,
    cached: bool = False,
) -> RepositoryTree:
    """Convert a recursive provider tree payload into ordered entries.

    Returns a :class:`RepositoryTree` whose ``truncated`` flag is True when
    either the provider truncated the listing or ``max_entries`` was reached.
    """
    raw_tree: list[dict[str, Any]] = []
    provider_truncated = False
    if isinstance(payload, dict):
        provider_truncated = bool(payload.get("truncated"))
        candidate = payload.get("tree")
        if isinstance(candidate, list):
            raw_tree = [item for item in candidate if isinstance(item, dict)]

    normalised: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw_tree:
        path = item.get("path")
        item_type = item.get("type")
        if not isinstance(path, str) or not path or item_type not in (TYPE_BLOB, TYPE_TREE):
            continue
        if path in seen:
            continue
        seen.add(path)
        normalised.append(
            {
                "path": path,
                "name": path.rsplit("/", 1)[-1],
                "type": TYPE_TREE if item_type == TYPE_TREE else TYPE_BLOB,
                "size": item.get("size") if isinstance(item.get("size"), int) else 0,
            }
        )

    normalised.sort(key=_sort_key)

    limit = max(1, int(max_entries))
    clipped = normalised[limit:]
    normalised = normalised[:limit]

    entries = [
        RepositoryTreeEntry(
            path=item["path"],
            name=item["name"],
            type=item["type"],
            size=item["size"],
            depth=item["path"].count("/"),
        )
        for item in normalised
    ]

    total_files = sum(1 for entry in entries if entry.type == TYPE_BLOB)
    total_directories = sum(1 for entry in entries if entry.type == TYPE_TREE)
    total_bytes = sum(entry.size for entry in entries if entry.type == TYPE_BLOB)

    return RepositoryTree(
        owner=owner,
        repository=repository,
        ref=ref,
        truncated=bool(provider_truncated or clipped),
        total_files=total_files,
        total_directories=total_directories,
        total_bytes=total_bytes,
        entries=entries,
        cached=cached,
    )


def build_file_content(
    content: str | bytes | None,
    path: str,
    *,
    max_bytes: int = MAX_FILE_BYTES,
) -> RepositoryFileContent:
    """Prepare provider file content for the Monaco preview.

    Binary payloads are reported with ``binary=True`` and no content, so the
    client can show a "binary file" notice instead of feeding bytes to the
    editor. Oversized text is truncated to ``max_bytes`` characters with
    ``truncated=True``.
    """
    if content is None:
        return RepositoryFileContent(
            path=path,
            content="",
            size=0,
            truncated=False,
            language=language_for_path(path),
            binary=False,
        )

    raw = content.encode("utf-8", errors="replace") if isinstance(content, str) else bytes(content)

    if looks_binary(raw):
        return RepositoryFileContent(
            path=path,
            content="",
            size=len(raw),
            truncated=False,
            language=language_for_path(path),
            binary=True,
        )

    text = raw.decode("utf-8", errors="replace")
    limit = max(1, int(max_bytes))
    if len(text) > limit:
        return RepositoryFileContent(
            path=path,
            content=text[:limit],
            size=len(raw),
            truncated=True,
            language=language_for_path(path),
            binary=False,
        )

    return RepositoryFileContent(
        path=path,
        content=text,
        size=len(raw),
        truncated=False,
        language=language_for_path(path),
        binary=False,
    )


def file_extension(path: str) -> str:
    """Lowercased extension including the dot, or an empty string."""
    filename = (path or "").rsplit("/", 1)[-1]
    if "." not in filename:
        return ""
    return f".{filename.rsplit('.', 1)[-1].lower()}"
