interface EmptyStateProps {
  title: string;
  description?: string;
}

export function EmptyState({ title, description }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-white/[0.08] bg-surface-1/40 px-6 py-16 text-center backdrop-blur-sm">
      <div className="relative flex h-12 w-12 items-center justify-center rounded-xl border border-white/[0.06] bg-glass-gradient text-slate-500">
        <span
          aria-hidden
          className="pointer-events-none absolute inset-0 rounded-xl bg-[radial-gradient(60%_60%_at_50%_30%,rgba(99,102,241,0.12),transparent_75%)]"
        />
        <svg viewBox="0 0 24 24" className="relative h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
          <path d="M15 14s.5-9.5-7-9.5m0 0C5 4.5 4.5 6 4.5 6s-1-.5-1.5 2c-.5 1.5.5 2 .5 2s-.5 1.5.5 2c1 1 2 1 2 1s.5 2 3 2m4-4.5c2.5 2 3.5.5 6 2v5c-2.5 1-4 0-6-.5v-6.5Z" />
          <path d="M17 17.5c2.5 1 4 0 6-.5" />
        </svg>
      </div>
      <p className="text-sm font-medium text-slate-300">{title}</p>
      {description && <p className="max-w-md text-[13px] leading-relaxed text-slate-500">{description}</p>}
    </div>
  );
}