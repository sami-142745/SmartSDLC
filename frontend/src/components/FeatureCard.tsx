import { cn } from '../lib/cn';

interface FeatureCardProps {
  label: string;
  value: string;
  tone?: 'default' | 'success' | 'warning' | 'critical';
  className?: string;
}

const VALUE_TONES = {
  default: 'text-ink',
  success: 'text-emerald-300',
  warning: 'text-amber-300',
  critical: 'text-rose-300',
} as const;

/** Compact labelled readout used inside panels. */
export function FeatureCard({ label, value, tone = 'default', className }: FeatureCardProps) {
  return (
    <div className={cn('glass-subtle px-4 py-3', className)}>
      <p className="eyebrow truncate">{label}</p>
      <p className={cn('mt-1 text-[17px] font-semibold tabular-nums tracking-tight', VALUE_TONES[tone])}>
        {value}
      </p>
    </div>
  );
}
