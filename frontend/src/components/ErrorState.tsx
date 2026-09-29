import type { ReactNode } from 'react';

import { Button } from './ui/Button';

interface ErrorStateProps {
  title?: string;
  message?: string;
  retry?: () => void;
  children?: ReactNode;
}

export function ErrorState({ title, message, retry, children }: ErrorStateProps) {
  return (
    <div
      role="alert"
      className="relative overflow-hidden rounded-xl border border-rose-500/20 bg-rose-500/[0.04] px-6 py-10 text-center backdrop-blur-sm"
    >
      <span
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-rose-400/30 to-transparent"
      />
      <div className="relative mx-auto flex h-12 w-12 items-center justify-center rounded-xl border border-rose-500/20 bg-rose-500/[0.06] text-rose-300">
        <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
          <path d="M12 9v4m0 4h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
      <h3 className="mt-4 text-base font-medium text-rose-200">{title ?? 'Something went wrong'}</h3>
      {message ? <p className="mx-auto mt-1.5 max-w-xl text-[13px] leading-relaxed text-rose-200/70">{message}</p> : null}
      {children}
      {retry ? (
        <Button variant="secondary" onClick={retry} className="mt-5 border-rose-400/25 text-rose-200 hover:border-rose-400/45">
          <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <path d="M4 4v6h6M20 20v-6h-6M20 9a8 8 0 0 0-14.3-3M4 15a8 8 0 0 0 14.3 3" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Try again
        </Button>
      ) : null}
    </div>
  );
}
