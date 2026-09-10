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
    <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-sm text-slate-600">
      {total != null && start != null && end != null ? (
        <span>
          Showing {start}–{end} of {total}
        </span>
      ) : (
        <span />
      )}
      <div className="flex items-center gap-2">
        <button
          type="button"
          disabled={!showPrev}
          onClick={() => onPageChange(page - 1)}
          className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Previous
        </button>
        <span className="min-w-[4rem] text-center text-xs font-medium text-slate-500">
          Page {page}
          {totalPages != null ? ` of ${Math.max(totalPages, 1)}` : ''}
        </span>
        <button
          type="button"
          disabled={!showNext}
          onClick={() => onPageChange(page + 1)}
          className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Next
        </button>
      </div>
    </div>
  );
}