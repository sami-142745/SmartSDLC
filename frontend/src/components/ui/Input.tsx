import { forwardRef } from 'react';
import type { InputHTMLAttributes, SelectHTMLAttributes, TextareaHTMLAttributes } from 'react';

import { cn } from '../../lib/cn';

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  invalid?: boolean;
  /** Icon rendered inside the field, before the text. */
  leading?: React.ReactNode;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { invalid, leading, className, ...rest },
  ref,
) {
  if (!leading) {
    return (
      <input
        ref={ref}
        aria-invalid={invalid || undefined}
        className={cn('field', invalid && 'field-invalid', className)}
        {...rest}
      />
    );
  }

  return (
    <span className="relative block">
      <span
        aria-hidden
        className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint"
      >
        {leading}
      </span>
      <input
        ref={ref}
        aria-invalid={invalid || undefined}
        className={cn('field pl-9', invalid && 'field-invalid', className)}
        {...rest}
      />
    </span>
  );
});

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  invalid?: boolean;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { invalid, className, rows = 4, ...rest },
  ref,
) {
  return (
    <textarea
      ref={ref}
      rows={rows}
      aria-invalid={invalid || undefined}
      className={cn('field resize-y font-mono text-[12.5px] leading-6', invalid && 'field-invalid', className)}
      {...rest}
    />
  );
});

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  invalid?: boolean;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { invalid, className, children, ...rest },
  ref,
) {
  return (
    <select
      ref={ref}
      aria-invalid={invalid || undefined}
      className={cn('field', invalid && 'field-invalid', className)}
      {...rest}
    >
      {children}
    </select>
  );
});

/**
 * Label + control + optional hint/error, wired up with matching ids so screen
 * readers announce the description and validation state correctly.
 */
export function Field({
  id,
  label,
  hint,
  error,
  children,
  className,
  required,
}: {
  id: string;
  label: React.ReactNode;
  hint?: React.ReactNode;
  error?: React.ReactNode;
  children: (props: {
    id: string;
    'aria-describedby': string | undefined;
    'aria-invalid': boolean | undefined;
  }) => React.ReactNode;
  className?: string;
  required?: boolean;
}) {
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(' ') || undefined;

  return (
    <div className={cn('flex flex-col gap-1.5', className)}>
      <label htmlFor={id} className="section-title">
        {label}
        {required ? <span className="ml-0.5 text-rose-400">*</span> : null}
      </label>
      {children({ id, 'aria-describedby': describedBy, 'aria-invalid': error ? true : undefined })}
      {hint ? (
        <p id={hintId} className="text-[11.5px] leading-relaxed text-ink-faint">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} className="text-[11.5px] leading-relaxed text-rose-300">
          {error}
        </p>
      ) : null}
    </div>
  );
}
