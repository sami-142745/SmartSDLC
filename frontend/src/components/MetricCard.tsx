import type { ReactNode } from 'react';

interface MetricCardProps {
  label: string;
  value: string | number;
  tone?: 'default' | 'critical' | 'high' | 'success';
  hint?: string;
}

const TONES: Record<NonNullable<MetricCardProps['tone']>, string> = {
  default: 'border-slate-200',
  critical: 'border-red-300',
  high: 'border-orange-300',
  success: 'border-emerald-300',
};

const VALUE_TONES: Record<NonNullable<MetricCardProps['tone']>, string> = {
  default: 'text-slate-900',
  critical: 'text-red-700',
  high: 'text-orange-700',
  success: 'text-emerald-700',
};

export function MetricCard({ label, value, tone = 'default', hint }: MetricCardProps) {
  return (
    <div
      className={`rounded-xl border ${TONES[tone]} bg-white p-4 shadow-sm ${hint ? '' : ''}`}
    >
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className={`mt-1 text-2xl font-semibold tabular-nums ${VALUE_TONES[tone]}`}>{value}</p>
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </div>
  );
}

export function MetricGrid({ children }: { children: ReactNode }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
      {children}
    </div>
  );
}