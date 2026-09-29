"""Normalized pull-request diff engine (Sprint 3).

The provider APIs expose diffs in two shapes and neither is directly usable for
navigation:

* ``GET /pulls/{n}/files`` returns a per-file record with a ``status``
  (``added``/``removed``/``modified``/``renamed``) and an optional ``patch``
  field. Binary files and files above GitHub's patch size cap simply have no
  ``patch`` at all.
* ``GET /pulls/{n}/diff`` returns a raw unified diff.

This module reconciles both into one deterministic structure
(:class:`NormalizedDiff`) that answers the two questions the review UI and the
AI prompt both need:

1. *What changed in each file, and how?* — status, counts, hunks.
2. *Which line numbers can a finding legitimately point at?* — the **change
   anchors** (:attr:`NormalizedFile.added_lines` / :attr:`removed_lines`).

Anchor resolution matters because a model hallucinating ``line: 1200`` on a
300-line file would otherwise produce a finding the UI cannot navigate to. Every
finding line is passed through :func:`resolve_line`, which either confirms the
line is a real change, snaps it to the nearest real change, or degrades the
finding to file level (:data:`~app.schemas.ai_review.FILE_LEVEL_LINE`) rather
than inventing a location.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from app.schemas.ai_review import FILE_LEVEL_LINE

#: How far a reported line may be from a real change before we give up and
#: downgrade the finding to file level.
ANCHOR_SNAP_WINDOW = 25

HUNK_HEADER = re.compile(r"^@@+ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@+(?: (.*))?$")

#: Git's own words for each file state, mapped onto our five statuses.
_STATUS_MAP: dict[str, str] = {
    "added": "added",
    "add": "added",
    "new": "added",
    "created": "added",
    "modified": "modified",
    "changed": "modified",
    "m": "modified",
    "removed": "deleted",
    "deleted": "deleted",
    "remove": "deleted",
    "delete": "deleted",
    "renamed": "renamed",
    "renamed/copied": "renamed",
    "copy": "renamed",
    "copied": "renamed",
    "binary": "binary",
}

#: Path fragments that mark a file as binary regardless of what the provider
#: reported. Kept small and explicit; guessing from extensions produces too many
#: false positives.
BINARY_EXTENSIONS = frozenset(
    {
        ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".tiff", ".avif",
        ".pdf", ".zip", ".gz", ".bz2", ".xz", ".7z", ".tar", ".rar", ".jar", ".war",
        ".class", ".so", ".dylib", ".dll", ".exe", ".bin", ".o", ".a", ".obj",
        ".pyc", ".pyo", ".pyd", ".wasm", ".mp3", ".mp4", ".avi", ".mov", ".wav",
        ".flac", ".ogg", ".webm", ".mkv", ".ttf", ".otf", ".woff", ".woff2",
        ".eot", ".db", ".sqlite", ".sqlite3", ".mdb", ".dat", ".pack", ".idx",
        ".mo", ".psd", ".ai", ".sketch", ".dmg", ".iso", ".img",
    }
)

LANGUAGE_BY_EXTENSION: dict[str, str] = {
    "py": "python", "pyi": "python",
    "ts": "typescript", "tsx": "typescript", "mts": "typescript", "cts": "typescript",
    "js": "javascript", "jsx": "javascript", "mjs": "javascript", "cjs": "javascript",
    "go": "go", "rs": "rust", "java": "java", "kt": "kotlin", "kts": "kotlin",
    "swift": "swift", "rb": "ruby", "php": "php", "c": "c", "h": "c",
    "cc": "cpp", "cpp": "cpp", "cxx": "cpp", "hpp": "cpp", "hh": "cpp",
    "cs": "csharp", "sh": "bash", "bash": "bash", "zsh": "bash", "fish": "bash",
    "ps1": "powershell", "yml": "yaml", "yaml": "yaml", "toml": "ini", "ini": "ini",
    "json": "json", "jsonc": "json", "md": "markdown", "mdx": "markdown",
    "html": "html", "htm": "html", "css": "css", "scss": "scss", "sass": "scss",
    "less": "less", "sql": "sql", "graphql": "graphql", "gql": "graphql",
    "vue": "vue", "svelte": "svelte", "ex": "elixir", "exs": "elixir",
    "scala": "scala", "dart": "dart", "lua": "lua", "pl": "perl", "r": "r",
    "kt.java": "kotlin", "gradle": "groovy", "groovy": "groovy", "tf": "terraform",
    "hcl": "hcl", "proto": "protobuf", "makefile": "makefile", "dockerfile": "dockerfile",
}


def infer_language(path: str | None) -> str | None:
    """Best-effort language id from a file path, or ``None`` when unknown."""
    if not path:
        return None
    name = path.strip().lower().rstrip("/")
    if not name:
        return None
    base = name.rsplit("/", 1)[-1]
    if base == "dockerfile" or base.startswith("dockerfile."):
        return "dockerfile"
    if base == "makefile" or base.startswith("makefile."):
        return "makefile"
    if base in ("cmakelists.txt",):
        return "cmake"
    dot = base.rfind(".")
    if dot <= 0:
        return None
    return LANGUAGE_BY_EXTENSION.get(base[dot + 1 :]) or None


def looks_binary(path: str | None) -> bool:
    if not path:
        return False
    name = path.strip().lower()
    dot = name.rfind(".")
    if dot == -1:
        return False
    return name[dot:] in BINARY_EXTENSIONS


def _as_int(value: Any, default: int = 0) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return number


def normalize_status(raw: Any) -> str:
    """Map a provider status string onto one of our five file states."""
    if not isinstance(raw, str):
        return "modified"
    slug = raw.strip().lower()
    return _STATUS_MAP.get(slug, _STATUS_MAP.get(slug.replace(" ", ""), "modified"))


# --------------------------------------------------------------------------
# Hunk model
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class DiffLine:
    kind: str  # "add" | "del" | "context"
    content: str
    old_line: int | None
    new_line: int | None


@dataclass
class Hunk:
    old_start: int
    old_lines: int
    new_start: int
    new_lines: int
    header: str | None
    lines: list[DiffLine] = field(default_factory=list)

    @property
    def changed_line_range(self) -> tuple[int, int] | None:
        """Inclusive new-file range covered by this hunk, or ``None`` if empty."""
        if self.new_lines <= 0:
            return None
        return self.new_start, self.new_start + self.new_lines - 1


def parse_patch(patch: str | None) -> list[Hunk]:
    """Parse a unified diff body into hunks with absolute line numbers.

    Tolerates the truncation GitHub applies to very large files: a patch cut
    mid-hunk still yields the hunks that were fully received.
    """
    if not patch or not patch.strip():
        return []

    lines = patch.replace("\r\n", "\n").rstrip("\n").split("\n")
    hunks: list[Hunk] = []
    index = 0
    while index < len(lines):
        match = HUNK_HEADER.match(lines[index])
        if not match:
            index += 1
            continue

        old_start = int(match.group(1))
        old_lines = 1 if match.group(2) is None else int(match.group(2))
        new_start = int(match.group(3))
        new_lines = 1 if match.group(4) is None else int(match.group(4))
        header = (match.group(5) or "").strip() or None

        hunk = Hunk(old_start, old_lines, new_start, new_lines, header)
        old_cursor, new_cursor = old_start, new_start
        old_seen = new_seen = 0

        cursor = index + 1
        while cursor < len(lines):
            raw = lines[cursor]
            if HUNK_HEADER.match(raw) or raw.startswith("diff --git "):
                break
            # Stop once the declared counts are satisfied; anything after that
            # is a new section we have not parsed yet.
            if old_seen >= old_lines and new_seen >= new_lines:
                break

            if raw.startswith("\\"):  # "\ No newline at end of file"
                cursor += 1
                continue
            if raw.startswith("+"):
                hunk.lines.append(DiffLine("add", raw[1:], None, new_cursor))
                new_cursor += 1
                new_seen += 1
            elif raw.startswith("-"):
                hunk.lines.append(DiffLine("del", raw[1:], old_cursor, None))
                old_cursor += 1
                old_seen += 1
            elif raw.startswith(" ") or raw == "":
                content = "" if raw == "" else raw[1:]
                hunk.lines.append(DiffLine("context", content, old_cursor, new_cursor))
                old_cursor += 1
                new_cursor += 1
                old_seen += 1
                new_seen += 1
            else:
                # A context line whose leading space was stripped in transport.
                hunk.lines.append(DiffLine("context", raw, old_cursor, new_cursor))
                old_cursor += 1
                new_cursor += 1
                old_seen += 1
                new_seen += 1
            cursor += 1

        if hunk.lines:
            hunks.append(hunk)
        index = max(cursor, index + 1)

    return hunks


# --------------------------------------------------------------------------
# File / diff model
# --------------------------------------------------------------------------


@dataclass
class NormalizedFile:
    path: str
    previous_path: str | None = None
    status: str = "modified"
    language: str | None = None
    additions: int = 0
    deletions: int = 0
    changes: int = 0
    is_binary: bool = False
    patch: str | None = None
    hunks: list[Hunk] = field(default_factory=list)

    @property
    def is_truncated(self) -> bool:
        """True when a patch exists but GitHub clipped it (patch omitted entirely
        for files over ~3000 lines)."""
        return bool(self.patch) and not self.hunks

    @property
    def added_lines(self) -> frozenset[int]:
        return frozenset(
            line.new_line for hunk in self.hunks for line in hunk.lines
            if line.kind == "add" and line.new_line is not None
        )

    @property
    def removed_lines(self) -> frozenset[int]:
        return frozenset(
            line.old_line for hunk in self.hunks for line in hunk.lines
            if line.kind == "del" and line.old_line is not None
        )

    @property
    def anchor_lines(self) -> frozenset[int]:
        """Every line number a finding may legitimately reference."""
        return self.added_lines | self.removed_lines

    @property
    def new_file_total_lines(self) -> int:
        if not self.hunks:
            return 0
        last = self.hunks[-1]
        return max(last.new_start + max(last.new_lines, 0) - 1, 0)

    @property
    def is_file_level_only(self) -> bool:
        """Deleted and binary files have no editable content to anchor against."""
        return self.status in ("deleted", "binary") or not self.hunks

    def line_content(self, line_number: int) -> str | None:
        """Content of a changed line, on either side of the diff.

        A replaced line shares its number on both sides, so the new-file side
        wins: that is the text the reviewer is looking at.
        """
        for hunk in self.hunks:
            for line in hunk.lines:
                if line.kind == "add" and line.new_line == line_number:
                    return line.content
        for hunk in self.hunks:
            for line in hunk.lines:
                if line.kind == "del" and line.old_line == line_number:
                    return line.content
        return None

    def _anchor_line(self, line_number: int) -> tuple[Hunk, DiffLine] | None:
        for hunk in self.hunks:
            for line in hunk.lines:
                if line.kind == "add" and line.new_line == line_number:
                    return hunk, line
        for hunk in self.hunks:
            for line in hunk.lines:
                if line.kind == "del" and line.old_line == line_number:
                    return hunk, line
        return None

    def snippet_at(self, line_number: int, radius: int = 2) -> str | None:
        """A few lines of real context around a changed line, for evidence."""
        found = self._anchor_line(line_number)
        if found is None:
            return None
        hunk, target = found
        index = hunk.lines.index(target)
        start = max(0, index - radius)
        stop = min(len(hunk.lines), index + radius + 1)
        return "\n".join(line.content for line in hunk.lines[start:stop])


@dataclass
class NormalizedDiff:
    files: list[NormalizedFile] = field(default_factory=list)
    additions: int = 0
    deletions: int = 0
    binary_files: int = 0
    truncated_files: int = 0

    @property
    def is_empty(self) -> bool:
        """An empty diff means there is genuinely nothing to review."""
        return not self.files

    @property
    def reviewable_files(self) -> list[NormalizedFile]:
        return [f for f in self.files if not f.is_binary]

    def by_path(self) -> dict[str, NormalizedFile]:
        return {file.path: file for file in self.files}

    def resolve_path(self, raw: str | None) -> NormalizedFile | None:
        """Find a file by new path, then old path, then by basename match.

        Models routinely echo a path without its directory prefix; basename
        matching keeps those findings attached to the right file instead of
        dropping them.
        """
        if not raw:
            return None
        candidate = raw.strip().lstrip("./")
        files = self.by_path()
        if candidate in files:
            return files[candidate]
        for file in self.files:
            if file.previous_path == candidate:
                return file
        base = candidate.rsplit("/", 1)[-1]
        if not base:
            return None
        matches = [file for file in self.files if file.path.rsplit("/", 1)[-1] == base]
        if len(matches) == 1:
            return matches[0]
        matches = [
            file for file in self.files
            if file.previous_path and file.previous_path.rsplit("/", 1)[-1] == base
        ]
        return matches[0] if len(matches) == 1 else None


# --------------------------------------------------------------------------
# Construction
# --------------------------------------------------------------------------


def _truncate(text: str | None, limit: int) -> str:
    if not text:
        return ""
    return text if len(text) <= limit else text[:limit]


def normalize_file(entry: dict[str, Any], *, max_patch_chars: int = 20000) -> NormalizedFile:
    """Normalize one provider file record into a :class:`NormalizedFile`."""
    path = str(entry.get("filename") or entry.get("path") or entry.get("new_path") or "unknown")
    previous = entry.get("previous_filename") or entry.get("old_path") or None
    if previous == path:
        previous = None

    status = normalize_status(entry.get("status"))
    patch = entry.get("patch") or entry.get("diff") or None
    has_patch = bool(patch and str(patch).strip())

    # A record that claims a textual status but carries no patch is either
    # binary or an over-sized file the provider declined to render. Both are
    # presented as binary, because neither has a diff to show.
    binary = bool(entry.get("binary")) or looks_binary(path)
    if not binary and not has_patch and status != "renamed":
        binary = True
    if binary:
        status = "binary"

    hunks = parse_patch(_truncate(str(patch) if patch else None, max_patch_chars))

    if not has_patch and status == "renamed":
        # Pure rename with no content change: an empty diff is correct here.
        pass

    additions = _as_int(entry.get("additions"))
    deletions = _as_int(entry.get("deletions"))
    changes = _as_int(entry.get("changes")) or (additions + deletions)

    # Prefer real counts from the hunks; provider counts are absent or zero for
    # truncated patches.
    if hunks:
        parsed_add = sum(1 for h in hunks for line in h.lines if line.kind == "add")
        parsed_del = sum(1 for h in hunks for line in h.lines if line.kind == "del")
        additions = parsed_add
        deletions = parsed_del
        changes = changes or (parsed_add + parsed_del)

    return NormalizedFile(
        path=path,
        previous_path=previous,
        status=status,
        language=infer_language(path),
        additions=additions,
        deletions=deletions,
        changes=changes,
        is_binary=binary,
        patch=str(patch) if has_patch else None,
        hunks=hunks,
    )


def normalize_diff(
    files: Iterable[dict[str, Any]] | None,
    *,
    max_files: int = 30,
    max_patch_chars: int = 20000,
) -> NormalizedDiff:
    """Normalize a provider file list into a :class:`NormalizedDiff`.

    Returns a diff whose ``is_empty`` flag is ``True`` for an empty or
    missing file list, which is the signal the service layer uses to skip the
    AI call entirely.
    """
    entries = [
        entry
        for entry in (files or [])
        if isinstance(entry, dict)
        # An entry with no path cannot be displayed or navigated to, so it is
        # dropped rather than surfacing as a phantom "unknown" file.
        and (entry.get("filename") or entry.get("path") or entry.get("new_path"))
    ]
    normalized: list[NormalizedFile] = []
    for entry in entries[:max_files]:
        normalized.append(normalize_file(entry, max_patch_chars=max_patch_chars))

    return NormalizedDiff(
        files=normalized,
        additions=sum(f.additions for f in normalized),
        deletions=sum(f.deletions for f in normalized),
        binary_files=sum(1 for f in normalized if f.is_binary),
        truncated_files=sum(1 for f in normalized if f.is_truncated),
    )


# --------------------------------------------------------------------------
# Anchor resolution
# --------------------------------------------------------------------------


def resolve_line(
    file: NormalizedFile | None,
    requested: Any,
    *,
    snap_window: int = ANCHOR_SNAP_WINDOW,
) -> int:
    """Map a reported line number onto a line that actually changed.

    Resolution order:

    1. Exact match against the file's change anchors -> returned unchanged.
    2. Nearest anchor within ``snap_window`` -> snapped, so a finding that is
       directionally right still lands on a clickable line.
    3. Anything else -> :data:`FILE_LEVEL_LINE`, because a finding the UI cannot
       navigate to is worse than one scoped to the whole file.
    """
    if file is None or file.is_file_level_only:
        return FILE_LEVEL_LINE

    anchors = file.anchor_lines
    if not anchors:
        return FILE_LEVEL_LINE

    try:
        wanted = int(requested)
    except (TypeError, ValueError):
        return FILE_LEVEL_LINE
    if wanted in anchors:
        return wanted

    nearest = min(anchors, key=lambda candidate: (abs(candidate - wanted), candidate))
    if abs(nearest - wanted) <= snap_window:
        return nearest
    return FILE_LEVEL_LINE


def evidence_for(file: NormalizedFile | None, line_number: int) -> tuple[str | None, str | None]:
    """Return ``(original_code, context_snippet)`` for a resolved line."""
    if file is None or line_number == FILE_LEVEL_LINE:
        return None, None
    return file.line_content(line_number), file.snippet_at(line_number)
