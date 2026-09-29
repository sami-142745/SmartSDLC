import { useEffect, useRef, useState } from 'react';

import type { DiffHunk, ParsedDiffFile } from '../../lib/diff/unifiedDiff';
import { cn } from '../../lib/cn';

const LINE_CLASSES = {
  add: 'bg-emerald-500/[0.07]',
  del: 'bg-rose-500/[0.07]',
  context: 'bg-transparent',
} as const;

const NUMBER_CLASSES = {
  add: 'text-emerald-400/45',
  del: 'text-rose-400/45',
  context: 'text-ink-faint',
} as const;

const MARK_CLASSES = {
  add: 'text-emerald-400/80',
  del: 'text-rose-400/80',
  context: 'text-transparent',
} as const;

function HunkHeader({
  hunk,
  collapsed,
  onToggle,
}: {
  hunk: DiffHunk;
  collapsed: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-expanded={!collapsed}
      className="group sticky top-0 z-10 flex w-full items-center gap-3 border-y border-white/[0.05] bg-surface-2/90 px-3 py-1.5 text-left font-mono text-[11px] text-ink-faint backdrop-blur-sm transition-colors hover:bg-surface-3/90"
    >
      <svg
        viewBox="0 0 24 24"
        className={cn('h-3 w-3 shrink-0 transition-transform duration-150', !collapsed && 'rotate-90')}
        fill="none"
        stroke="currentColor"
        strokeWidth="2.5"
        aria-hidden="true"
      >
        <path d="m9 6 6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <span className="shrink-0 tabular-nums">
        @@ -{hunk.oldStart},{hunk.oldCount} +{hunk.newStart},{hunk.newCount} @@
      </span>
      {hunk.heading ? (
        <span className="min-w-0 flex-1 truncate text-ink-faint/80">{hunk.heading}</span>
      ) : (
        <span className="flex-1" />
      )}
      <span className="shrink-0 font-mono text-[10px] tabular-nums text-ink-faint/70">
        {hunk.lines.filter((l) => l.kind === 'add').length}+ /{' '}
        {hunk.lines.filter((l) => l.kind === 'del').length}-
      </span>
    </button>
  );
}

/**
 * Traditional unified diff, rendered in plain DOM.
 *
 * This is the default view because it stays readable at any width, prints
 * well, costs nothing to load, and degrades gracefully. Monaco's side-by-side
 * editor is opt-in from the parent `DiffViewer`.
 */
export function UnifiedDiffView({
  file,
  focusLine = null,
}: {
  file: ParsedDiffFile;
  /**
   * New-side line to scroll to and briefly highlight, used when a reviewer
   * clicks a finding. Omitted by the legacy `DiffViewer` callers, so their
   * output is unchanged.
   */
  focusLine?: number | null;
}) {
  const [collapsed, setCollapsed] = useState<Set<number>>(new Set());
  const [highlighted, setHighlighted] = useState<number | null>(null);
  const bodyRef = useRef<HTMLDivElement | null>(null);

  const toggle = (index: number) => {
    setCollapsed((previous) => {
      const next = new Set(previous);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  };

  useEffect(() => {
    if (focusLine === null || focusLine === undefined) return;
    if (file.status === 'binary' || file.hunks.length === 0) return;

    const selector = `[data-diff-line="${focusLine}"]`;
    const target = bodyRef.current?.querySelector(selector);
    // Guarded: scrollIntoView is absent in jsdom and in some embedded webviews.
    if (target instanceof HTMLElement) {
      target.scrollIntoView?.({ block: 'center', behavior: 'smooth' });
    }
    setHighlighted(focusLine);
  }, [focusLine, file.path, file.status, file.hunks]);

  // The highlight is a transient attention cue, not a persistent selection, so
  // it clears on its own instead of lingering after the reader moves on.
  useEffect(() => {
    if (highlighted === null) return;
    const timer = window.setTimeout(() => setHighlighted(null), 1600);
    return () => window.clearTimeout(timer);
  }, [highlighted]);

  if (file.status === 'binary') {
    return (
      <p className="px-4 py-8 text-center text-[13px] text-ink-faint">
        Binary file — no textual diff available.
      </p>
    );
  }

  if (file.hunks.length === 0) {
    return (
      <p className="px-4 py-8 text-center text-[13px] text-ink-faint">
        No textual changes in this file.
      </p>
    );
  }

  return (
    <div ref={bodyRef} className="overflow-x-auto font-mono text-[12.5px] leading-[20px]">
      {file.hunks.map((hunk, hunkIndex) => {
        const isCollapsed = collapsed.has(hunkIndex);
        return (
          <div key={`${hunk.oldStart}-${hunk.newStart}-${hunkIndex}`}>
            <HunkHeader hunk={hunk} collapsed={isCollapsed} onToggle={() => toggle(hunkIndex)} />
            {!isCollapsed ? (
              <div>
                {hunk.lines.map((line, lineIndex) => {
                  const anchor = line.kind === 'add' ? line.newLine : null;
                  const isHighlighted = anchor !== null && anchor === highlighted;
                  return (
                    <div
                      key={lineIndex}
                      data-diff-line={anchor ?? undefined}
                      className={cn(
                        'flex min-w-max transition-shadow',
                        LINE_CLASSES[line.kind],
                        isHighlighted && 'shadow-[inset_3px_0_0_rgba(196,181,253,0.9)]',
                      )}
                    >
                      <span
                        aria-hidden
                        className={cn(
                          'w-12 shrink-0 select-none border-r border-white/[0.04] pr-2 text-right text-[11px] tabular-nums',
                          NUMBER_CLASSES[line.kind],
                        )}
                      >
                        {line.oldLine ?? ''}
                      </span>
                      <span
                        aria-hidden
                        className={cn(
                          'w-12 shrink-0 select-none border-r border-white/[0.04] pr-2 text-right text-[11px] tabular-nums',
                          NUMBER_CLASSES[line.kind],
                        )}
                      >
                        {line.newLine ?? ''}
                      </span>
                      <span
                        aria-hidden
                        className={cn('w-5 shrink-0 select-none text-center', MARK_CLASSES[line.kind])}
                      >
                        {line.kind === 'add' ? '+' : line.kind === 'del' ? '-' : ' '}
                      </span>
                      <span className="whitespace-pre px-2 text-ink-muted">
                        {line.content || ' '}
                      </span>
                    </div>
                  );
                })}
              </div>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}
