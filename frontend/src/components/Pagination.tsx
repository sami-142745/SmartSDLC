interface PaginationProps {
  page: number;
  perPage: number;
  total?: number;
  totalPages?: number;
  hasMore?: boolean;
  onPageChange: (page: number) => void;
}

export function Pagination({
  page,
  perPage,
  total,
  totalPages,
  hasMore,
  onPageChange,
}: PaginationProps) {
  const showNext = hasMore ?? (totalPages ? page < totalPages : false);
  const showPrev = page > 1;
  const start = total ? (page - 1) * perPage + 1 : null;
  const end = total ? Math.min(page * perPage, total) : null;

  return (
    <div className="relative mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-white/[0.06] pt-4 text-sm text-slate-500">
      <span
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/[0.06] to-transparent"
      />
      {total != null && start != null && end != null ? (
        <span className="font-mono text-xs tabular-nums">
          {start}–{end} of {total}
        </span>
      ) : (
        <span />
      )}
      <div className="flex items-center gap-2">
        <button
          type="button"
          disabled={!showPrev}
          onClick={() => onPageChange(page - 1)}
          className="relative inline-flex items-center gap-1.5 rounded-lg border border-white/[0.08] bg-white/[0.02] px-3 py-1.5 text-[13px] font-medium text-slate-300 transition-all duration-150 hover:border-accent-indigo/30 hover:text-slate-100 hover:shadow-[0_0_14px_-8px_rgba(99,102,241,0.5)] disabled:cursor-not-allowed disabled:opacity-30 disabled:hover:border-white/[0.08] disabled:hover:text-slate-300 disabled:hover:shadow-none"
        >
          <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <path d="m15 6-6 6 6 6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Previous
        </button>
        <span className="flex min-w-[4rem] items-center justify-center gap-1.5 font-mono text-xs text-slate-500">
          <span className="tabular-nums text-slate-300">{page}</span>
          {totalPages != null && <span className="text-slate-700">/ {Math.max(totalPages, 1)}</span>}
        </span>
        <button
          type="button"
          disabled={!showNext}
          onClick={() => onPageChange(page + 1)}
          className="relative inline-flex items-center gap-1.5 rounded-lg border border-white/[0.08] bg-white/[0.02] px-3 py-1.5 text-[13px] font-medium text-slate-300 transition-all duration-150 hover:border-accent-indigo/30 hover:text-slate-100 hover:shadow-[0_0_14px_-8px_rgba(99,102,241,0.5)] disabled:cursor-not-allowed disabled:opacity-30 disabled:hover:border-white/[0.08] disabled:hover:text-slate-300 disabled:hover:shadow-none"
        >
          Next
          <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <path d="m9 6 6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </div>
    </div>
  );
}
