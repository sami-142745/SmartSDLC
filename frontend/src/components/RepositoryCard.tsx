import { Badge } from './Badge';
import type { Repository } from '../types';

interface RepositoryCardProps {
  repository: Repository;
  onClick?: () => void;
}

export function RepositoryCard({ repository, onClick }: RepositoryCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="block w-full rounded-lg border border-slate-200 bg-white p-4 text-left shadow-sm transition-colors hover:border-slate-300 hover:bg-slate-50"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-slate-900">{repository.name}</p>
          <p className="truncate text-xs text-slate-500">{repository.full_name}</p>
        </div>
        <Badge
          className={
            repository.private
              ? 'bg-amber-100 text-amber-800 border-amber-300'
              : 'bg-emerald-100 text-emerald-800 border-emerald-300'
          }
        >
          {repository.private ? 'Private' : 'Public'}
        </Badge>
      </div>
      <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
        <span>
          Owner: <span className="text-slate-700">{repository.owner ?? '—'}</span>
        </span>
        <span>
          Default branch: <span className="font-mono">{repository.default_branch ?? '—'}</span>
        </span>
      </div>
      <div className="mt-2 text-xs">
        <a
          href={repository.html_url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-sky-600 hover:underline"
          onClick={(event) => event.stopPropagation()}
        >
          Open on GitHub ↗
        </a>
      </div>
    </button>
  );
}