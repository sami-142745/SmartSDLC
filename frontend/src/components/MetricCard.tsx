import type { ReactNode } from 'react';

import { cn } from '../lib/cn';
import { Sparkline } from './ui/Charts';
import type { SparkPoint } from './ui/Charts';

export type MetricTone = 'default' | 'critical' | 'high' | 'success' | 'warning';

interface MetricCardProps {
  label: string;
  value: string | number;
  icon?: ReactNode;
  tone?: MetricTone;
  hint?: string;
  /** Optional trailing delta, e.g. "+12% this week". */
  delta?: { value: string; positive: boolean };
  /** Optional inline trend line. */
  trend?: SparkPoint[];
  className?: string;
}

const VALUE_TONES: Record<MetricTone, string> = {
  default: 'text-ink',
  critical: 'text-rose-300',
  high: 'text-orange-300',
  success: 'text-emerald-300',
  warning: 'text-amber-300',
};

const ICON_TONES: Record<MetricTone, string> = {
  default: 'text-accent-lavender',
  critical: 'text-rose-400',
  high: 'text-orange-400',
  success: 'text-emerald-400',
  warning: 'text-amber-400',
};

const ACCENT_TONES: Record<MetricTone, string> = {
  default: 'from-accent-violet to-accent-indigo',
  critical: 'from-rose-500 to-rose-400',
  high: 'from-orange-500 to-orange-400',
  success: 'from-emerald-500 to-emerald-400',
  warning: 'from-amber-500 to-amber-400',
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
  delta,
  trend,
  className,
}: MetricCardProps) {
  return (
    <div className={cn('glass-subtle group relative overflow-hidden px-4 py-3.5', className)}>
      {/* Tone rail: the fastest way to scan a row of metrics by urgency. */}
      <span
        aria-hidden
        className={cn(
          'pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r to-transparent opacity-70',
          ACCENT_TONES[tone],
        )}
      />
      <span
        aria-hidden
        className="pointer-events-none absolute -right-8 -top-8 h-20 w-20 rounded-full bg-accent-violet/[0.08] opacity-0 blur-2xl transition-opacity duration-300 group-hover:opacity-100"
      />
      <div className="relative flex items-start gap-3">
        <span
          aria-hidden
          className={cn(
            'mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-white/[0.08] bg-white/[0.04] text-ink-muted transition-colors duration-200',
            ICON_TONES[tone],
          )}
        >
          {icon ?? <DefaultIcon />}
        </span>
        <div className="min-w-0 flex-1">
          <p className="eyebrow truncate">{label}</p>
          <p className="mt-1 flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
            <span className={cn('text-[22px] font-semibold leading-none tabular-nums tracking-tight', VALUE_TONES[tone])}>
              {value}
            </span>
            {delta ? (
              <span
                className={cn(
                  'font-mono text-[11px] tabular-nums',
                  delta.positive ? 'text-emerald-300' : 'text-rose-300',
                )}
              >
                {delta.value}
              </span>
            ) : null}
          </p>
          {hint ? <p className="mt-1.5 text-[11px] leading-snug text-ink-faint">{hint}</p> : null}
        </div>
        {trend && trend.length > 1 ? (
          <div className="shrink-0 self-center opacity-80">
            <Sparkline points={trend} color={tone === 'default' ? '#8B5CF6' : 'currentColor'} />
          </div>
        ) : null}
      </div>
    </div>
  );
}

/**
 * Hairline-separated metric grid. The 1px gap over a translucent background
 * produces dividers without extra borders on every cell.
 */
export function MetricGrid({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={cn(
        'grid grid-cols-1 gap-px overflow-hidden rounded-xl border border-white/[0.07] bg-white/[0.04] sm:grid-cols-2 xl:grid-cols-4',
        className,
      )}
    >
      {children}
    </div>
  );
}
