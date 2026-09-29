import { forwardRef } from 'react';
import type { HTMLAttributes, ReactNode } from 'react';

import { cn } from '../../lib/cn';

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  /** `glass` for elevated panels, `flat` for dense data surfaces, `bare` for layout-only wrappers. */
  tone?: 'glass' | 'flat' | 'bare';
  interactive?: boolean;
  /** Adds the top hairline highlight that sells the glassmorphism read. */
  edge?: boolean;
}

const TONE_CLASSES: Record<NonNullable<CardProps['tone']>, string> = {
  glass: 'glass',
  flat: 'rounded-xl border border-white/[0.07] bg-surface-1/60',
  bare: '',
};

export const Card = forwardRef<HTMLDivElement, CardProps>(function Card(
  { tone = 'glass', interactive, edge, className, children, ...rest },
  ref,
) {
  return (
    <div
      ref={ref}
      className={cn(
        TONE_CLASSES[tone],
        edge && 'glass-edge',
        interactive && 'interactive',
        className,
      )}
      {...rest}
    >
      {children}
    </div>
  );
});

export function CardHeader({
  title,
  description,
  actions,
  icon,
  className,
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  icon?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        'flex flex-wrap items-start justify-between gap-3 border-b border-white/[0.06] px-5 py-4',
        className,
      )}
    >
      <div className="flex min-w-0 items-start gap-3">
        {icon ? (
          <span
            aria-hidden
            className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-white/[0.08] bg-white/[0.04] text-accent-lavender"
          >
            {icon}
          </span>
        ) : null}
        <div className="min-w-0">
          <h2 className="section-title truncate">{title}</h2>
          {description ? (
            <p className="mt-0.5 text-[12px] leading-relaxed text-ink-subtle">{description}</p>
          ) : null}
        </div>
      </div>
      {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
    </div>
  );
}

export function CardBody({
  children,
  className,
  padded = true,
}: {
  children: ReactNode;
  className?: string;
  padded?: boolean;
}) {
  return (
    <div className={cn(padded && 'px-5 py-4', className)}>{children}</div>
  );
}

export function CardFooter({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={cn(
        'flex flex-wrap items-center gap-3 border-t border-white/[0.06] px-5 py-3.5 text-[12px] text-ink-subtle',
        className,
      )}
    >
      {children}
    </div>
  );
}

/** Small stat readout used inside cards and page headers. */
export function InlineStat({
  label,
  value,
  tone = 'default',
}: {
  label: string;
  value: ReactNode;
  tone?: 'default' | 'positive' | 'warning' | 'critical';
}) {
  const toneClass = {
    default: 'text-ink',
    positive: 'text-emerald-300',
    warning: 'text-amber-300',
    critical: 'text-rose-300',
  }[tone];

  return (
    <div>
      <p className="eyebrow">{label}</p>
      <p className={cn('mt-1 text-lg font-semibold tabular-nums tracking-tight', toneClass)}>{value}</p>
    </div>
  );
}
