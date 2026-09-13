import { Badge } from './Badge';
import type { PullRequestSummary } from '../types';
import { formatShortDate } from '../utils/format';

interface PullRequestCardProps {
  pullRequest: PullRequestSummary;
  repoName: string;
  onClick?: () => void;
}

export function PullRequestCard({ pullRequest, repoName, onClick }: PullRequestCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group relative w-full overflow-hidden rounded-xl border border-white/[0.06] bg-surface-1/70 text-left backdrop-blur-sm transition-all duration-200 hover:-translate-y-0.5 hover:border-accent-indigo/25 hover:bg-surface-2/[0.65] hover:shadow-[0_20px_50px_-20px_rgba(0,0,0,0.65),0_0_0_1px_rgba(99,102,241,0.14),0_0_34px_-14px_rgba(99,102,241,0.35)]"
    >
      <span
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-accent-indigo/50 to-transparent opacity-0 transition-opacity duration-200 group-hover:opacity-100"
      />
      <div className="relative flex items-center gap-3.5 px-4 py-3.5">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-white/[0.07] bg-glass-gradient text-slate-400 transition-all duration-200 group-hover:-translate-y-0.5 group-hover:border-accent-indigo/30 group-hover:text-accent-lavender group-hover:shadow-[0_0_18px_-4px_rgba(99,102,241,0.55)]">
          <svg viewBox="0 0 24 24" className="h-[18px] w-[18px]" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
            <circle cx="6" cy="6" r="2.4" />
            <circle cx="6" cy="18" r="2.4" />
            <circle cx="18" cy="6" r="2.4" />
            <path d="M6 8.4V15.6M6 8.4C6 5.5 9 5 12 5s6 .5 6 1M6 15.6c0-.7 3 .4 6 .4l6 1" />
          </svg>
        </span>

        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-2">
            <span className="truncate text-sm font-medium text-slate-100">
              #{pullRequest.number} &#x00B7; {pullRequest.title}
            </span>
            {pullRequest.state === 'closed' && (
              <span className="hidden text-xs text-slate-600 md:inline">merged &#x00B7; {pullRequest.base ?? '\u2014'} &#x2190; {pullRequest.head ?? '\u2014'}</span>
            )}
          </span>
          <span className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-slate-500">
            <span>{repoName} &#x00B7; opened by {pullRequest.user ?? '\u2014'}</span>
            <span className="font-mono text-slate-600">
              {pullRequest.base ?? '\u2014'}
              <span className="mx-1 text-slate-500">&#x2190;</span>
              {pullRequest.head ?? '\u2014'}
            </span>
            <span>Updated {formatShortDate(pullRequest.updated_at)}</span>
          </span>
        </span>

        <Badge
          className={
            pullRequest.state === 'open'
              ? 'border-emerald-500/20 bg-emerald-500/[0.06] text-emerald-300'
              : 'border-slate-500/25 bg-slate-500/[0.05] text-slate-400'
          }
        >
          {pullRequest.state}
        </Badge>

        <svg
          viewBox="0 0 24 24"
          className="h-4 w-4 shrink-0 text-slate-600 transition-all duration-150 group-hover:translate-x-0.5 group-hover:text-slate-300"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          aria-hidden="true"
        >
          <path d="m9 6 6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
    </button>
  );
}