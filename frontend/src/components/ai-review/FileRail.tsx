import { cn } from '../../lib/cn';
import { diffAccentColor } from '../diff/diffAccent';
import type { AiReviewFile, AiReviewFileStatus } from '../../types';

const STATUS_LABEL: Record<AiReviewFileStatus, string> = {
  added: 'added',
  modified: 'modified',
  deleted: 'deleted',
  renamed: 'renamed',
  binary: 'binary',
};

const STATUS_CLASSES: Record<AiReviewFileStatus, string> = {
  added: 'border-emerald-500/25 bg-emerald-500/10 text-emerald-300',
  modified: 'border-sky-500/25 bg-sky-500/10 text-sky-300',
  deleted: 'border-rose-500/25 bg-rose-500/10 text-rose-300',
  renamed: 'border-amber-500/25 bg-amber-500/10 text-amber-300',
  binary: 'border-white/15 bg-white/[0.06] text-ink-muted',
};

export interface FileRailProps {
  files: AiReviewFile[];
  activePath: string | null;
  onSelect: (path: string) => void;
}

/**
 * Left pane of the review workspace: one row per changed file.
 *
 * The rail carries the status vocabulary from the backend so a reviewer can
 * tell a rename from a deletion, and flags binary files because those have no
 * readable diff to click into.
 */
export function FileRail({ files, activePath, onSelect }: FileRailProps) {
  if (files.length === 0) {
    return (
      <p className="px-3 py-6 text-center text-[12.5px] text-ink-faint">
        This pull request has no changed files.
      </p>
    );
  }

  return (
    <ul className="flex flex-col gap-0.5 overflow-y-auto p-2" role="list">
      {files.map((file) => {
        const active = file.path === activePath;
        return (
          <li key={file.path}>
            <button
              type="button"
              onClick={() => onSelect(file.path)}
              aria-current={active ? 'true' : undefined}
              className={cn(
                'group flex w-full flex-col gap-1 rounded-lg px-2.5 py-2 text-left transition-colors',
                active ? 'bg-white/[0.06]' : 'hover:bg-white/[0.03]',
              )}
            >
              <span className="flex min-w-0 items-center gap-2">
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
                {file.finding_ids.length > 0 ? (
                  <span
                    className="shrink-0 rounded-full border border-accent-violet/30 bg-accent-violet/10 px-1.5 font-mono text-[10px] tabular-nums text-accent-lavender"
                    title={`${file.finding_ids.length} finding${file.finding_ids.length === 1 ? '' : 's'}`}
                  >
                    {file.finding_ids.length}
                  </span>
                ) : null}
              </span>

              <span className="flex items-center gap-2 pl-3.5">
                <span
                  className={cn(
                    'shrink-0 rounded border px-1 font-mono text-[9px] uppercase tracking-wide',
                    STATUS_CLASSES[file.status],
                  )}
                >
                  {STATUS_LABEL[file.status]}
                </span>
                <span className="shrink-0 font-mono text-[10.5px] tabular-nums">
                  <span className="text-emerald-400/80">+{file.additions}</span>{' '}
                  <span className="text-rose-400/80">-{file.deletions}</span>
                </span>
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
