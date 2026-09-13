import type { ReactNode } from 'react';

interface PageHeaderProps {
  eyebrow?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
}

export function PageHeader({ eyebrow, title, description, actions }: PageHeaderProps) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-4 pb-1">
      <div className="min-w-0">
        {eyebrow && (
          <p className="tech-label flex items-center gap-2.5">
            {eyebrow}
          </p>
        )}
        <h1 className="mt-1.5 page-hero-title">{title}</h1>
        {description && <p className="page-hero-subtitle">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}