import { Suspense, lazy, useEffect, useMemo, useState } from 'react';

import {
  buildModified,
  buildOriginal,
  inferLanguage,
  parseUnifiedDiff,
} from '../lib/diff/unifiedDiff';
import type { ParsedDiffFile } from '../lib/diff/unifiedDiff';
import { cn } from '../lib/cn';
import { Tabs } from './ui/Tabs';
import { UnifiedDiffView } from './diff/UnifiedDiffView';
import { diffAccentColor } from './diff/diffAccent';

type ViewMode = 'unified' | 'split';

/**
 * Monaco is ~2MB of JS plus its language workers. Loading it on demand (and
 * only for the split view) keeps the default review path fast.
 */
const MonacoDiff = lazy(() => import('./diff/MonacoDiff'));

const MODE_ITEMS: { value: ViewMode; label: string }[] = [
  { value: 'unified', label: 'Unified' },
  { value: 'split', label: 'Side by side' },
];

function FileRail({
  files,
  activePath,
  onSelect,
}: {
  files: ParsedDiffFile[];
  activePath: string;
  onSelect: (path: string) => void;
}) {
  return (
    <ul className="flex max-h-56 flex-col gap-0.5 overflow-y-auto p-2" role="list">
      {files.map((file) => {
        const active = file.path === activePath;
        return (
          <li key={file.path}>
            <button
              type="button"
              onClick={() => onSelect(file.path)}
              aria-current={active ? 'true' : undefined}
              className={cn(
                'group flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left transition-colors',
                active ? 'bg-white/[0.06]' : 'hover:bg-white/[0.03]',
              )}
            >
              <span
                aria-hidden
                className="h-1.5 w-1.5 shrink-0 rounded-full"
                style={{ backgroundColor: diffAccentColor(file.additions, file.deletions) }}
              />
              <span
                className={cn(
                  'min-w-0 flex-1 truncate font-mono text-[11.5px]',
                  active ? 'text-ink' : 'text-ink-subtle group-hover:text-ink-muted',
                )}
                title={file.path}
              >
                {file.path}
              </span>
              {file.status === 'added' ? (
                <span className="shrink-0 rounded border border-emerald-500/25 bg-emerald-500/10 px-1 font-mono text-[9px] uppercase text-emerald-300">
                  new
                </span>
              ) : file.status === 'deleted' ? (
                <span className="shrink-0 rounded border border-rose-500/25 bg-rose-500/10 px-1 font-mono text-[9px] uppercase text-rose-300">
                  del
                </span>
              ) : null}
              <span className="shrink-0 font-mono text-[10.5px] tabular-nums">
                <span className="text-emerald-400/80">+{file.additions}</span>{' '}
                <span className="text-rose-400/80">-{file.deletions}</span>
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

export interface DiffViewerProps {
  /** Raw unified diff text from the backend. */
  diff: string;
  className?: string;
  /** Force a view mode, e.g. from a user preference. */
  defaultMode?: ViewMode;
  height?: number;
  /**
   * New-side line to scroll to, so the AI review workspace can jump from a
   * finding to the code it refers to. Unused by the legacy callers.
   */
  focusLine?: number | null;
}

export function DiffViewer({
  diff,
  className,
  defaultMode = 'unified',
  height = 560,
  focusLine = null,
}: DiffViewerProps) {
  const parsed = useMemo(() => parseUnifiedDiff(diff), [diff]);
  const [activePath, setActivePath] = useState<string>(parsed.files[0]?.path ?? '');
  const [mode, setMode] = useState<ViewMode>(defaultMode);

  // When a new diff arrives, fall back to the first file unless the previously
  // selected file is still present.
  useEffect(() => {
    if (parsed.files.length === 0) {
      setActivePath('');
      return;
    }
    if (!parsed.files.some((file) => file.path === activePath)) {
      setActivePath(parsed.files[0].path);
    }
  }, [parsed, activePath]);

  const activeFile = parsed.files.find((file) => file.path === activePath) ?? parsed.files[0];

  if (parsed.files.length === 0 || !activeFile) {
    return (
      <div
        className={cn(
          'rounded-xl border border-dashed border-white/[0.09] bg-surface-1/40 px-6 py-12 text-center',
          className,
        )}
      >
        <p className="text-[13px] text-ink-faint">No diff available.</p>
      </div>
    );
  }

  const language = inferLanguage(activeFile.newPath ?? activeFile.oldPath);
  const original = buildOriginal(activeFile) ?? '';
  const modified = buildModified(activeFile) ?? '';
  const multiFile = parsed.files.length > 1;

  return (
    <div
      className={cn(
        'flex flex-col overflow-hidden rounded-xl border border-white/[0.07] bg-surface-0 shadow-elevated md:flex-row',
        className,
      )}
    >
      {multiFile ? (
        <div className="shrink-0 border-b border-white/[0.07] md:w-64 md:border-b-0 md:border-r">
          <div className="flex items-center justify-between border-b border-white/[0.05] px-3 py-2">
            <span className="eyebrow">Files</span>
            <span className="font-mono text-[10.5px] tabular-nums text-ink-faint">
              {parsed.files.length}
            </span>
          </div>
          <FileRail files={parsed.files} activePath={activeFile.path} onSelect={setActivePath} />
        </div>
      ) : null}

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/[0.07] bg-surface-1/50 px-3 py-2">
          <div className="flex min-w-0 items-center gap-2.5">
            {/* With one file the surrounding UI already names it; repeating the
                path here would just duplicate the text. */}
            {multiFile ? (
              <span className="truncate font-mono text-[11.5px] text-ink-muted" title={activeFile.path}>
                {activeFile.path}
              </span>
            ) : (
              <span className="font-mono text-[11.5px] uppercase tracking-[0.14em] text-ink-faint">
                Diff
              </span>
            )}
            <span className="shrink-0 font-mono text-[10.5px] tabular-nums">
              <span className="text-emerald-400/85">+{activeFile.additions}</span>{' '}
              <span className="text-rose-400/85">-{activeFile.deletions}</span>
            </span>
          </div>
          <Tabs
            aria-label="Diff view mode"
            items={MODE_ITEMS}
            value={mode}
            onChange={setMode}
            size="sm"
          />
        </div>

        <div className="min-h-0 flex-1">
          {mode === 'unified' ? (
            <div className="max-h-[560px] overflow-y-auto">
              <UnifiedDiffView file={activeFile} focusLine={focusLine} />
            </div>
          ) : (
            <Suspense
              fallback={
                <div className="flex h-[560px] items-center justify-center text-[12px] text-ink-faint">
                  Loading editor…
                </div>
              }
            >
              <MonacoDiff
                original={original}
                modified={modified}
                language={language}
                path={activeFile.path}
                height={height}
              />
            </Suspense>
          )}
        </div>
      </div>
    </div>
  );
}
