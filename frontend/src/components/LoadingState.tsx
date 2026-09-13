interface LoadingStateProps {
  label?: string;
}

export function LoadingState({ label = 'Loading\u2026' }: LoadingStateProps) {
  return (
    <div
      className="flex flex-col items-center justify-center gap-4 py-16 text-center"
      role="status"
    >
      <span className="relative inline-flex h-9 w-9">
        <span className="absolute inset-0 inline-flex h-9 w-9 animate-spin rounded-full border-2 border-transparent border-t-accent-indigo" />
        <span className="absolute inset-1 inline-flex h-7 w-7 animate-spin rounded-full border border-transparent border-t-accent-violet [animation-duration:1.6s]" />
        <span
          aria-hidden
          className="absolute inset-0 -m-2 rounded-full bg-accent-indigo/[0.08] blur-md animate-pulse-subtle"
        />
      </span>
      <span className="font-mono text-xs uppercase tracking-[0.18em] text-slate-400">{label}</span>
    </div>
  );
}