import type { ReactNode } from 'react';

import { cn } from '../../lib/cn';

export type BadgeTone =
  | 'neutral'
  | 'brand'
  | 'accent'
  | 'success'
  | 'warning'
  | 'danger'
  | 'info';

const TONE_CLASSES: Record<BadgeTone, string> = {
  neutral: 'border-white/[0.09] bg-white/[0.04] text-ink-muted',
  brand: 'border-accent-violet/30 bg-accent-violet/10 text-accent-lavender',
  accent: 'border-accent-cyan/30 bg-accent-cyan/10 text-accent-cyan',
  success: 'border-emerald-500/25 bg-emerald-500/10 text-emerald-300',
  warning: 'border-amber-400/25 bg-amber-400/10 text-amber-300',
  danger: 'border-rose-500/25 bg-rose-500/10 text-rose-300',
  info: 'border-sky-400/25 bg-sky-400/10 text-sky-300',
};

export interface BadgeProps {
  children: ReactNode;
  tone?: BadgeTone;
  className?: string;
  /** Small leading dot; inherits the text colour. */
  dot?: boolean;
  icon?: ReactNode;
  title?: string;
}

export function Badge({
  children,
  tone = 'neutral',
  className,
  dot,
  icon,
  title,
}: BadgeProps) {
  return (
    <span title={title} className={cn('chip', TONE_CLASSES[tone], className)}>
      {dot ? <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-current" /> : null}
      {icon}
      {children}
    </span>
  );
}

/** Monospace badge for identifiers, commit SHAs, branch names. */
export function MonoBadge({
  children,
  className,
  title,
}: {
  children: ReactNode;
  className?: string;
  title?: string;
}) {
  return (
    <span
      title={title}
      className={cn(
        'chip border-white/[0.08] bg-white/[0.03] font-mono text-[10.5px] text-ink-subtle',
        className,
      )}
    >
      {children}
    </span>
  );
}
