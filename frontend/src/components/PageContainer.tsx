import type { ReactNode } from 'react';

interface PageContainerProps {
  children: ReactNode;
  className?: string;
  wide?: boolean;
}

export function PageContainer({ children, className = '', wide = true }: PageContainerProps) {
  return (
    <div className={`page-enter relative ${wide ? 'mx-auto w-full max-w-[1200px]' : 'w-full'} ${className}`}>
      {children}
    </div>
  );
}