import { Button } from './ui/Button';
import { cn } from '../lib/cn';

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
    <nav
      aria-label="Pagination"
      className="relative mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-white/[0.07] pt-4 text-[12px] text-ink-faint"
    >
      <span
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/[0.08] to-transparent"
      />
      {total != null && start != null && end != null ? (
        <span className="font-mono tabular-nums">
          {start}–{end} of {total}
        </span>
      ) : (
        <span />
      )}
      <div className="flex items-center gap-2">
        <Button size="sm" onClick={() => onPageChange(page - 1)} disabled={!showPrev}>
          <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <path d="m15 6-6 6 6 6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Previous
        </Button>
        <span className="flex min-w-[4rem] items-center justify-center gap-1.5 font-mono text-[11px] text-ink-faint">
          <span className={cn('tabular-nums text-ink-muted')}>{page}</span>
          {totalPages != null ? <span>/ {Math.max(totalPages, 1)}</span> : null}
        </span>
        <Button size="sm" onClick={() => onPageChange(page + 1)} disabled={!showNext}>
          Next
          <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <path d="m9 6 6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </Button>
      </div>
    </nav>
  );
}
