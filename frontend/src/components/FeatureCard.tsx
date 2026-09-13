interface FeatureCardProps {
  label: string;
  value: string;
}

export function FeatureCard({ label, value }: FeatureCardProps) {
  return (
    <div className="group relative overflow-hidden rounded-xl border border-white/[0.06] bg-surface-1 px-4 py-3.5 transition-all duration-200 hover:-translate-y-0.5 hover:border-white/[0.11] hover:bg-surface-2/70 hover:shadow-[0_12px_28px_-16px_rgba(0,0,0,0.6)]">
      <span
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/[0.1] to-transparent opacity-0 transition-opacity duration-200 group-hover:opacity-100"
      />
      <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500 transition-colors group-hover:text-slate-400">
        {label}
      </p>
      <p className="mt-1 text-lg font-semibold tabular-nums tracking-tight text-slate-100 transition-colors group-hover:text-white">
        {value}
      </p>
    </div>
  );
}