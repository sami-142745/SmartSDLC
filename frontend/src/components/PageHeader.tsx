import type { ReactNode } from 'react';

import { cn } from '../lib/cn';

interface PageHeaderProps {
  eyebrow?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  className?: string;
}

/**
 * Consistent page intro: an optional breadcrumb-style eyebrow, the page title,
 * supporting copy, and right-aligned primary actions.
 */
export function PageHeader({ eyebrow, title, description, actions, className }: PageHeaderProps) {
  return (
    <div className={cn('flex flex-wrap items-start justify-between gap-4 pb-1', className)}>
      <div className="min-w-0">
        {eyebrow ? <p className="eyebrow flex items-center gap-2">{eyebrow}</p> : null}
        <h1 className="mt-1.5 text-2xl font-semibold tracking-tight text-ink sm:text-[28px]">
          {title}
        </h1>
        {description ? (
          <p className="mt-1.5 max-w-2xl text-[13px] leading-relaxed text-ink-subtle">
            {description}
          </p>
        ) : null}
      </div>
      {actions ? (
        <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>
      ) : null}
    </div>
  );
}
