import type { ReactNode } from 'react';

interface MetricCardProps {
  label: string;
  value: string | number;
  icon?: ReactNode;
  tone?: 'default' | 'critical' | 'high' | 'success';
  hint?: string;
}

const VALUE_TONES: Record<NonNullable<MetricCardProps['tone']>, string> = {
  default: 'text-slate-100',
  critical: 'text-rose-300',
  high: 'text-orange-300',
  success: 'text-emerald-300',
};

const ICON_TONES: Record<NonNullable<MetricCardProps['tone']>, string> = {
  default: 'text-accent-indigo',
  critical: 'text-rose-400',
  high: 'text-orange-400',
  success: 'text-emerald-400',
};

const ACCENT_TONES: Record<NonNullable<MetricCardProps['tone']>, string> = {
  default: 'from-accent-indigo to-accent-violet',
  critical: 'from-rose-500 to-rose-400',
  high: 'from-orange-500 to-orange-400',
  success: 'from-emerald-500 to-emerald-400',
};

const GLOW_TONES: Record<NonNullable<MetricCardProps['tone']>, string> = {
  default: 'hover:shadow-[0_0_28px_-14px_rgba(99,102,241,0.45)]',
  critical: 'hover:shadow-[0_0_28px_-14px_rgba(248,113,113,0.4)]',
  high: 'hover:shadow-[0_0_28px_-14px_rgba(251,146,60,0.4)]',
  success: 'hover:shadow-[0_0_28px_-14px_rgba(52,211,153,0.4)]',
};

function DefaultIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">
      <path d="M4 6h16v12H4V6Zm2 3.5h8v2H6v-2Zm0 4h12v1H6v-1Zm4-3h8v1H10v-1Z" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function MetricCard({
  label,
  value,
  icon,
  tone = 'default',
  hint,
}: MetricCardProps) {
  return (
    <div
      className={`group metric-tile relative overflow-hidden bg-surface-1/80 px-4 py-3.5 hover:bg-surface-2/[0.6] ${GLOW_TONES[tone]}`}
    >
      <span
        aria-hidden
        className={`pointer-events-none absolute inset-x-0 top-0 h-[2px] bg-gradient-to-r to-transparent opacity-60 transition-opacity duration-200 group-hover:opacity-100 ${ACCENT_TONES[tone]}`}
      />
      <span
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-glass-gradient opacity-0 transition-opacity duration-200 group-hover:opacity-100"
      />
      <span
        aria-hidden
        className="pointer-events-none absolute -right-10 -top-10 h-24 w-24 rounded-full bg-accent-indigo/[0.06] blur-2xl opacity-0 transition-opacity duration-300 group-hover:opacity-100"
      />
      <div className="relative flex items-start gap-3">
        <span
          aria-hidden
          className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-white/[0.08] bg-white/[0.03] transition-all duration-200 group-hover:-translate-y-0.5 ${ICON_TONES[tone]}`}
        >
          {icon ?? <DefaultIcon />}
        </span>
        <div className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500 group-hover:text-slate-400">
            {label}
          </p>
          <p className={`mt-1 flex items-baseline gap-2 text-xl font-semibold leading-none tabular-nums tracking-tight ${VALUE_TONES[tone]}`}>
            {value}
          </p>
          {hint && <p className="mt-1.5 text-[11px] leading-snug text-slate-500">{hint}</p>}
        </div>
      </div>
    </div>
  );
}

export function MetricGrid({ children }: { children: ReactNode }) {
  return (
    <div className="grid grid-cols-1 gap-px overflow-hidden rounded-xl border border-white/[0.06] bg-white/[0.04] shadow-elevated sm:grid-cols-2 xl:grid-cols-3">
      {children}
    </div>
  );
}