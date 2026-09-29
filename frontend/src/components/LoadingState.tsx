interface LoadingStateProps {
  label?: string;
}

/**
 * Inline busy indicator for a region of a page. Prefers `PageSkeleton` for
 * whole-page loads so the layout does not shift when data resolves.
 */
export function LoadingState({ label = 'Loading…' }: LoadingStateProps) {
  return (
    <div role="status" aria-live="polite" className="flex flex-col items-center justify-center gap-4 py-16">
      <span aria-hidden className="relative inline-flex h-9 w-9">
        <span className="absolute inset-0 inline-flex h-9 w-9 animate-spin rounded-full border-2 border-transparent border-t-accent-violet" />
        <span className="absolute inset-1 inline-flex h-7 w-7 animate-spin rounded-full border border-transparent border-t-accent-cyan [animation-duration:1.6s]" />
      </span>
      <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-ink-faint">{label}</span>
    </div>
  );
}
