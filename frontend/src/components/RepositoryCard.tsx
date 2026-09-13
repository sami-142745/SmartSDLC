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
      className="group relative w-full overflow-hidden rounded-xl border border-white/[0.06] bg-surface-1/70 text-left backdrop-blur-sm transition-all duration-200 hover:-translate-y-0.5 hover:border-accent-indigo/25 hover:bg-surface-2/[0.65] hover:shadow-[0_20px_50px_-20px_rgba(0,0,0,0.65),0_0_0_1px_rgba(99,102,241,0.14),0_0_34px_-14px_rgba(99,102,241,0.35)]"
    >
      <span
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-accent-indigo/50 to-transparent opacity-0 transition-opacity duration-200 group-hover:opacity-100"
      />
      <span
        aria-hidden
        className="pointer-events-none absolute -top-12 right-8 h-24 w-32 rounded-full bg-accent-indigo/[0.08] blur-2xl opacity-0 transition-opacity duration-300 group-hover:opacity-100"
      />
      <div className="relative flex items-center gap-3.5 px-4 py-3.5">
        <span className="relative flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-white/[0.07] bg-glass-gradient text-slate-400 transition-all duration-200 group-hover:-translate-y-0.5 group-hover:border-accent-indigo/30 group-hover:text-accent-lavender group-hover:shadow-[0_0_18px_-4px_rgba(99,102,241,0.55)]">
          <svg viewBox="0 0 24 24" className="h-[18px] w-[18px]" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
            <path d="M2.75 6a2.25 2.25 0 0 1 2.25-2.25h4.13c.6 0 1.17.24 1.6.66l1.44 1.44c.42.42 1 .66 1.6.66h5.48A2.25 2.25 0 0 1 21.5 8.76v9.5a2.25 2.25 0 0 1-2.25 2.25h-14.5a2.25 2.25 0 0 1-2.25-2.25V6Z" strokeLinejoin="round" />
          </svg>
          <span
            aria-hidden
            className="absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full bg-emerald-400/80 shadow-[0_0_6px_rgba(52,211,153,0.7)]"
          />
        </span>

        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-2">
            <span className="truncate font-mono text-sm font-medium text-slate-100">
              {repository.full_name}
            </span>
            <Badge
              className={
                repository.private
                  ? 'border-amber-400/20 bg-amber-400/[0.06] text-amber-300'
                  : 'border-slate-500/25 bg-slate-500/[0.05] text-slate-400'
              }
            >
              {repository.private ? 'Private' : 'Public'}
            </Badge>
          </span>
          <span className="mt-0.5 flex items-center gap-x-3 gap-y-0.5 text-xs text-slate-500">
            <span className="font-mono">
              <span className="text-slate-600">branch</span> {repository.default_branch ?? '\u2014'}
            </span>
            {repository.owner ? (
              <span>
                owner <span className="text-slate-400">{repository.owner}</span>
              </span>
            ) : null}
          </span>
        </span>

        <a
          href={repository.html_url}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(event) => event.stopPropagation()}
          className="hidden text-xs text-slate-500 transition-colors hover:text-slate-200 sm:inline"
        >
          Open on GitHub &#x2197;
        </a>

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