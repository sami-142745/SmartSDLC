/**
 * Unified-diff parsing.
 *
 * The SmartSDLC backend exposes raw unified diffs (GitHub's
 * `GET /pullrequests/{owner}/{repo}/{number}/diff` returns `text/plain`) and
 * per-file `patch` hunks. Monaco's `DiffEditor` is side-by-side, so it needs
 * the reconstructed "before" and "after" documents rather than patch text.
 *
 * This module reconstructs those two documents from a unified diff. Because a
 * unified diff only carries the hunks that changed, unchanged regions between
 * hunks are omitted — exactly how GitHub renders a partial diff. Line numbers
 * therefore drift across multiple hunks, but the *content* of the change is
 * byte-for-byte faithful.
 */

export type DiffLineKind = 'add' | 'del' | 'context';

export interface DiffLine {
  kind: DiffLineKind;
  /** Line content with the leading +/-/space marker stripped. */
  content: string;
  /** 1-based line number in the original document, or null for additions. */
  oldLine: number | null;
  /** 1-based line number in the modified document, or null for deletions. */
  newLine: number | null;
}

export interface DiffHunk {
  oldStart: number;
  oldCount: number;
  newStart: number;
  newCount: number;
  /** The optional `@@ ... @@` section heading, when Git emits one. */
  heading: string | null;
  lines: DiffLine[];
}

export interface ParsedDiffFile {
  /** Path on the "before" side; null when the file was added. */
  oldPath: string | null;
  /** Path on the "after" side; null when the file was deleted. */
  newPath: string | null;
  /** Display path, preferring the post-image name. */
  path: string;
  status: 'added' | 'deleted' | 'modified' | 'renamed' | 'binary';
  additions: number;
  deletions: number;
  hunks: DiffHunk[];
  /** True when the file is unchanged (`diff --git` header with no hunks). */
  unchanged: boolean;
}

export interface UnifiedDiff {
  files: ParsedDiffFile[];
  additions: number;
  deletions: number;
  /** True when the diff contained no `@@` hunks at all. */
  empty: boolean;
}

const HUNK_HEADER = /^@@+ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@+(?: (.*))?$/;

/** Strip the `a/` and `b/` prefixes Git adds to diff paths. */
function normalizePath(raw: string | null | undefined): string | null {
  if (!raw) return null;
  const trimmed = raw.trim();
  if (!trimmed || trimmed === '/dev/null') return null;
  return trimmed.replace(/^[ab]\//, '');
}

interface FileAccumulator {
  oldPath: string | null;
  newPath: string | null;
  status: ParsedDiffFile['status'];
  hunks: DiffHunk[];
  additions: number;
  deletions: number;
}

function createAccumulator(oldPath: string | null, newPath: string | null): FileAccumulator {
  const added = oldPath === null && newPath !== null;
  const deleted = newPath === null && oldPath !== null;
  return {
    oldPath,
    newPath,
    status: added ? 'added' : deleted ? 'deleted' : 'modified',
    hunks: [],
    additions: 0,
    deletions: 0,
  };
}

/**
 * Consume the body lines of a single hunk, assigning 1-based line numbers on
 * each side. Returns the raw body lines (markers intact) for the caller.
 */
function parseHunkBody(
  body: string[],
  oldStart: number,
  oldCount: number,
  newStart: number,
  newCount: number,
  heading: string | null,
): DiffHunk {
  const lines: DiffLine[] = [];
  let oldLine = oldStart;
  let newLine = newStart;
  let oldSeen = 0;
  let newSeen = 0;

  for (const raw of body) {
    // A bare empty line inside a hunk is a context line whose trailing space
    // was stripped by the transport. Stop once both declared counts are met.
    if (oldSeen >= oldCount && newSeen >= newCount) break;

    if (raw.startsWith('+')) {
      lines.push({ kind: 'add', content: raw.slice(1), oldLine: null, newLine: newLine++ });
      newSeen += 1;
    } else if (raw.startsWith('-')) {
      lines.push({ kind: 'del', content: raw.slice(1), oldLine: oldLine++, newLine: null });
      oldSeen += 1;
    } else if (raw.startsWith(' ') || raw === '') {
      lines.push({ kind: 'context', content: raw === '' ? '' : raw.slice(1), oldLine: oldLine++, newLine: newLine++ });
      oldSeen += 1;
      newSeen += 1;
    } else {
      // Git emits "\ No newline at end of file" — metadata, not content.
      continue;
    }
  }

  return { oldStart, oldCount, newStart, newCount, heading, lines };
}

/**
 * Parse a raw unified diff into per-file records with reconstructed hunks.
 * Tolerates the header lines Git prepends (`diff --git`, `index`, `similarity`).
 */
export function parseUnifiedDiff(raw: string | null | undefined): UnifiedDiff {
  const files: ParsedDiffFile[] = [];
  if (!raw || !raw.trim()) {
    return { files, additions: 0, deletions: 0, empty: true };
  }

  // A diff normally ends with a newline; splitting on it would yield a
  // phantom empty context line, so drop exactly one trailing break.
  const lines = raw.replace(/\n$/, '').split('\n');
  let index = 0;
  let current: FileAccumulator | null = null;
  let sawHunk = false;

  const flush = () => {
    if (!current) return;
    files.push({
      oldPath: current.oldPath,
      newPath: current.newPath,
      path: current.newPath ?? current.oldPath ?? 'unknown',
      status: current.status,
      additions: current.additions,
      deletions: current.deletions,
      hunks: current.hunks,
      unchanged: current.hunks.length === 0,
    });
    current = null;
  };

  while (index < lines.length) {
    const line = lines[index];

    // New file boundary.
    if (line.startsWith('diff --git ')) {
      flush();
      // "diff --git a/old b/new" — the paths can themselves contain spaces,
      // so prefer the ---/+++ headers when they follow.
      const match = /^diff --git (?:"?a\/)?(.*?)"? (?:"?b\/)?(.*?)"?$/.exec(line);
      current = createAccumulator(
        normalizePath(match?.[1] ?? null),
        normalizePath(match?.[2] ?? null),
      );
      index += 1;
      continue;
    }

    if (!current) {
      // Content before any `diff --git` header: treat as an implicit single
      // file so bare hunks (e.g. from a `patch` field) still render.
      if (HUNK_HEADER.test(line)) {
        current = createAccumulator(null, null);
      } else {
        index += 1;
        continue;
      }
    }

    if (line.startsWith('old mode') || line.startsWith('new mode')) {
      index += 1;
      continue;
    }

    if (line.startsWith('new file mode')) {
      current.status = 'added';
      index += 1;
      continue;
    }

    if (line.startsWith('deleted file mode')) {
      current.status = 'deleted';
      index += 1;
      continue;
    }

    if (line.startsWith('rename from') || line.startsWith('rename to')) {
      current.status = 'renamed';
      index += 1;
      continue;
    }

    if (line.startsWith('Binary files ') || line.startsWith('GIT binary patch')) {
      current.status = 'binary';
      index += 1;
      continue;
    }

    if (line.startsWith('--- ')) {
      const oldPath = normalizePath(line.slice(4).split('\t')[0]);
      // Only adopt the ---/+++ path when it is not a placeholder, and when we
      // do not already have a more precise name from the `diff --git` header.
      if (oldPath && (!current.oldPath || current.oldPath === 'unknown')) {
        current.oldPath = oldPath;
      } else if (oldPath === null) {
        current.oldPath = null;
      }
      index += 1;
      continue;
    }

    if (line.startsWith('+++ ')) {
      const newPath = normalizePath(line.slice(4).split('\t')[0]);
      if (newPath && (!current.newPath || current.newPath === 'unknown')) {
        current.newPath = newPath;
      } else if (newPath === null) {
        current.newPath = null;
      }
      if (current.status === 'modified') {
        current.status = current.oldPath === null ? 'added' : current.newPath === null ? 'deleted' : 'modified';
      }
      index += 1;
      continue;
    }

    const hunkMatch = HUNK_HEADER.exec(line);
    if (hunkMatch) {
      sawHunk = true;
      const oldStart = Number(hunkMatch[1]);
      const oldCount = hunkMatch[2] === undefined ? 1 : Number(hunkMatch[2]);
      const newStart = Number(hunkMatch[3]);
      const newCount = hunkMatch[4] === undefined ? 1 : Number(hunkMatch[4]);
      const heading = hunkMatch[5]?.trim() || null;

      // Collect body lines until the next hunk header or file boundary.
      const body: string[] = [];
      let cursor = index + 1;
      while (cursor < lines.length && !HUNK_HEADER.test(lines[cursor]) && !lines[cursor].startsWith('diff --git ')) {
        body.push(lines[cursor]);
        cursor += 1;
      }

      const hunk = parseHunkBody(body, oldStart, oldCount, newStart, newCount, heading);
      for (const hunkLine of hunk.lines) {
        if (hunkLine.kind === 'add') current.additions += 1;
        if (hunkLine.kind === 'del') current.deletions += 1;
      }
      current.hunks.push(hunk);
      index = cursor;
      continue;
    }

    index += 1;
  }

  flush();

  return {
    files,
    additions: files.reduce((sum, file) => sum + file.additions, 0),
    deletions: files.reduce((sum, file) => sum + file.deletions, 0),
    empty: !sawHunk,
  };
}

/**
 * Reconstruct the full "before" document for a parsed file, or null when the
 * file did not exist before the change.
 */
export function buildOriginal(file: ParsedDiffFile): string | null {
  if (file.oldPath === null || file.status === 'added') return null;
  const out: string[] = [];
  for (const hunk of file.hunks) {
    for (const line of hunk.lines) {
      if (line.kind !== 'add') out.push(line.content);
    }
  }
  return out.join('\n');
}

/**
 * Reconstruct the full "after" document for a parsed file, or null when the
 * file was removed by the change.
 */
export function buildModified(file: ParsedDiffFile): string | null {
  if (file.newPath === null || file.status === 'deleted') return null;
  const out: string[] = [];
  for (const hunk of file.hunks) {
    for (const line of hunk.lines) {
      if (line.kind !== 'del') out.push(line.content);
    }
  }
  return out.join('\n');
}

/** Best-effort language id for Monaco, inferred from the file extension. */
const LANGUAGE_BY_EXTENSION: Record<string, string> = {
  ts: 'typescript',
  tsx: 'typescript',
  mts: 'typescript',
  cts: 'typescript',
  js: 'javascript',
  jsx: 'javascript',
  mjs: 'javascript',
  cjs: 'javascript',
  json: 'json',
  py: 'python',
  rb: 'ruby',
  go: 'go',
  rs: 'rust',
  java: 'java',
  kt: 'kotlin',
  kts: 'kotlin',
  swift: 'swift',
  c: 'c',
  h: 'c',
  cc: 'cpp',
  cpp: 'cpp',
  cxx: 'cpp',
  hpp: 'cpp',
  cs: 'csharp',
  php: 'php',
  sh: 'shell',
  bash: 'shell',
  zsh: 'shell',
  yml: 'yaml',
  yaml: 'yaml',
  toml: 'ini',
  ini: 'ini',
  md: 'markdown',
  mdx: 'markdown',
  html: 'html',
  css: 'css',
  scss: 'scss',
  sql: 'sql',
  graphql: 'graphql',
  gql: 'graphql',
  dockerfile: 'dockerfile',
  vue: 'html',
  svelte: 'html',
  ex: 'elixir',
  exs: 'elixir',
  scala: 'scala',
  dart: 'dart',
  lua: 'lua',
  pl: 'perl',
  r: 'r',
};

export function inferLanguage(path: string | null | undefined): string {
  if (!path) return 'plaintext';
  const name = path.toLowerCase();
  const base = name.slice(name.lastIndexOf('/') + 1);
  if (base === 'dockerfile' || base.startsWith('dockerfile.')) return 'dockerfile';
  if (base === 'makefile') return 'makefile';
  const dot = base.lastIndexOf('.');
  if (dot === -1) return 'plaintext';
  return LANGUAGE_BY_EXTENSION[base.slice(dot + 1)] ?? 'plaintext';
}
