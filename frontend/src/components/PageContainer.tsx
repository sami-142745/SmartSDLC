import type { ReactNode } from 'react';

import { cn } from '../lib/cn';

interface PageContainerProps {
  children: ReactNode;
  className?: string;
  wide?: boolean;
}

/**
 * Standard page shell. Content is centred and width-capped so long-form pages
 * (review, insights) stay readable while dashboards can opt out of the cap.
 */
export function PageContainer({ children, className, wide = true }: PageContainerProps) {
  return (
    <div
      className={cn(
        'relative mx-auto w-full animate-slide-up',
        wide ? 'max-w-[1360px]' : 'max-w-none',
        className,
      )}
    >
      {children}
    </div>
  );
}
