import { cn } from '../../lib/cn';

/**
 * Base skeleton block. Compose these into page-shaped placeholders so loading
 * states mirror the real layout and avoid layout shift on hydration.
 */
export function Skeleton({ className, style }: { className?: string; style?: React.CSSProperties }) {
  return <div aria-hidden className={cn('skeleton', className)} style={style} />;
}

export function SkeletonText({
  lines = 3,
  className,
  widths,
}: {
  lines?: number;
  className?: string;
  /** Per-line width percentages; defaults to a natural ragged rhythm. */
  widths?: number[];
}) {
  // Ragged widths read as prose rather than a uniform grey block.
  const rhythm = [100, 92, 76, 88, 64, 95, 70, 84];
  return (
    <div className={cn('space-y-2', className)}>
      {Array.from({ length: lines }, (_, index) => (
        <Skeleton
          key={index}
          style={{ width: `${widths?.[index] ?? rhythm[index % rhythm.length]}%` }}
          className="h-3"
        />
      ))}
    </div>
  );
}

export function SkeletonStat() {
  return (
    <div className="glass-subtle px-4 py-3.5">
      <Skeleton className="h-2.5 w-20" />
      <Skeleton className="mt-2.5 h-6 w-14" />
    </div>
  );
}

export function SkeletonCard({ className }: { className?: string }) {
  return (
    <div className={cn('glass px-5 py-4', className)}>
      <div className="flex items-center gap-3">
        <Skeleton className="h-8 w-8 rounded-lg" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-3 w-2/5" />
          <Skeleton className="h-2.5 w-3/5" />
        </div>
      </div>
      <div className="mt-4 space-y-2">
        <Skeleton className="h-2.5 w-full" />
        <Skeleton className="h-2.5 w-4/5" />
      </div>
    </div>
  );
}

export function SkeletonRows({ rows = 5, className }: { rows?: number; className?: string }) {
  return (
    <div className={cn('space-y-2', className)}>
      {Array.from({ length: rows }, (_, index) => (
        <div
          key={index}
          className="glass-subtle flex items-center gap-3 px-4 py-3"
          // eslint-disable-next-line react/no-array-index-key
        >
          <Skeleton className="h-7 w-7 shrink-0 rounded-full" />
          <div className="flex-1 space-y-1.5">
            <Skeleton className="h-2.5 w-1/3" />
            <Skeleton className="h-2 w-1/2" />
          </div>
          <Skeleton className="h-5 w-14 rounded-md" />
        </div>
      ))}
    </div>
  );
}

export function SkeletonTable({ rows = 6, columns = 4 }: { rows?: number; columns?: number }) {
  return (
    <div className="t-table-wrap">
      <table className="t-table">
        <thead className="t-table-head">
          <tr>
            {Array.from({ length: columns }, (_, index) => (
              <th key={index} className="t-table-th">
                <Skeleton className="h-2.5 w-16" />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: rows }, (_, rowIndex) => (
            <tr key={rowIndex}>
              {Array.from({ length: columns }, (_, colIndex) => (
                <td key={colIndex} className="t-table-td">
                  <Skeleton className={cn('h-2.5', colIndex === 0 ? 'w-2/3' : 'w-1/2')} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/**
 * Full-page loading shell used by routes that have not resolved their primary
 * data yet. Announced politely so screen readers are told the page is busy.
 */
export function PageSkeleton({ label = 'Loading' }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="space-y-6">
      <span className="sr-only">{label}</span>
      <div className="space-y-3">
        <Skeleton className="h-3 w-28" />
        <Skeleton className="h-8 w-2/3 max-w-md" />
        <Skeleton className="h-3 w-1/2 max-w-sm" />
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }, (_, index) => (
          <SkeletonStat key={index} />
        ))}
      </div>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <SkeletonCard />
        </div>
        <SkeletonCard />
      </div>
    </div>
  );
}
