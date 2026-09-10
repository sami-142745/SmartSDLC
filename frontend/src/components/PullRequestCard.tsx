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
      className="block w-full rounded-lg border border-slate-200 bg-white p-4 text-left shadow-sm transition-colors hover:border-slate-300 hover:bg-slate-50"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-slate-900">
            #{pullRequest.number} · {pullRequest.title}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            {repoName} · opened by {pullRequest.user ?? '—'}
          </p>
        </div>
        <Badge
          className={
            pullRequest.state === 'open'
              ? 'bg-emerald-100 text-emerald-800 border-emerald-300'
              : 'bg-slate-100 text-slate-700 border-slate-300'
          }
        >
          {pullRequest.state}
        </Badge>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
        <span className="font-mono">
          {pullRequest.base ?? '—'} ← {pullRequest.head ?? '—'}
        </span>
        <span>Updated {formatShortDate(pullRequest.updated_at)}</span>
      </div>
    </button>
  );
}