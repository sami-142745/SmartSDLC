import type { ReactNode } from 'react';

interface ErrorStateProps {
  title?: string;
  message?: string;
  retry?: () => void;
  children?: ReactNode;
}

export function ErrorState({ title, message, retry, children }: ErrorStateProps) {
  return (
    <div
      className="rounded-lg border border-red-200 bg-red-50 px-6 py-8 text-center"
      role="alert"
    >
      <h3 className="text-base font-semibold text-red-800">
        {title ?? 'Something went wrong'}
      </h3>
      {message && <p className="mt-1 text-sm text-red-700">{message}</p>}
      {children}
      {retry && (
        <button
          type="button"
          onClick={retry}
          className="mt-4 inline-flex items-center rounded-md border border-red-300 bg-white px-3 py-1.5 text-sm font-medium text-red-700 shadow-sm hover:bg-red-100"
        >
          Try again
        </button>
      )}
    </div>
  );
}