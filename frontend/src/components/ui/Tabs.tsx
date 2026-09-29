import { useId, useRef, useState } from 'react';
import type { KeyboardEvent, ReactNode } from 'react';

import { cn } from '../../lib/cn';

export interface TabItem<T extends string> {
  value: T;
  label: ReactNode;
  /** Optional count rendered as a muted trailing chip. */
  count?: number;
  disabled?: boolean;
}

export interface TabsProps<T extends string> {
  items: TabItem<T>[];
  value: T;
  onChange: (value: T) => void;
  'aria-label': string;
  variant?: 'segmented' | 'underline';
  className?: string;
  size?: 'sm' | 'md';
}

/**
 * Accessible tab group implementing the WAI-ARIA tabs pattern with roving
 * focus: Left/Right (or Up/Down) move between tabs, Home/End jump to the ends.
 */
export function Tabs<T extends string>({
  items,
  value,
  onChange,
  variant = 'segmented',
  className,
  size = 'md',
  ...rest
}: TabsProps<T>) {
  const baseId = useId();
  const listRef = useRef<HTMLDivElement>(null);
  const [focusValue, setFocusValue] = useState<T | null>(null);

  const enabled = items.filter((item) => !item.disabled);
  const activeIndex = Math.max(
    enabled.findIndex((item) => item.value === value),
    0,
  );

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const horizontal = variant === 'segmented' || size !== 'sm';
    const nextKey = horizontal ? 'ArrowRight' : 'ArrowDown';
    const prevKey = horizontal ? 'ArrowLeft' : 'ArrowUp';

    let nextIndex: number | null = null;
    if (event.key === nextKey) nextIndex = (activeIndex + 1) % enabled.length;
    else if (event.key === prevKey) nextIndex = (activeIndex - 1 + enabled.length) % enabled.length;
    else if (event.key === 'Home') nextIndex = 0;
    else if (event.key === 'End') nextIndex = enabled.length - 1;
    else return;

    event.preventDefault();
    const next = enabled[nextIndex];
    if (!next) return;
    onChange(next.value);
    setFocusValue(next.value);
    // Move DOM focus to the newly selected tab for a seamless keyboard flow.
    window.requestAnimationFrame(() => {
      listRef.current
        ?.querySelector<HTMLButtonElement>(`#${CSS.escape(`${baseId}-${next.value}`)}`)
        ?.focus();
    });
  };

  const containerClass = cn(
    'inline-flex',
    variant === 'segmented' ? 'gap-0.5 rounded-lg border border-white/[0.07] bg-white/[0.03] p-0.5' : 'gap-1 border-b border-white/[0.07]',
    className,
  );

  return (
    <div
      ref={listRef}
      role="tablist"
      aria-label={rest['aria-label']}
      onKeyDown={handleKeyDown}
      className={containerClass}
    >
      {items.map((item) => {
        const selected = item.value === value;
        const isSegmented = variant === 'segmented';
        return (
          <button
            key={item.value}
            id={`${baseId}-${item.value}`}
            type="button"
            role="tab"
            aria-selected={selected}
            aria-controls={`${baseId}-panel-${item.value}`}
            tabIndex={(focusValue ?? value) === item.value ? 0 : -1}
            disabled={item.disabled}
            onClick={() => onChange(item.value)}
            className={cn(
              'relative inline-flex items-center gap-1.5 whitespace-nowrap font-medium transition-all duration-150 ease-swift',
              'disabled:pointer-events-none disabled:opacity-40',
              size === 'sm' ? 'px-2.5 py-1 text-[12px]' : 'px-3.5 py-1.5 text-[13px]',
              isSegmented ? 'rounded-md' : 'rounded-t-md -mb-px border-b-2',
              selected
                ? cn(
                    isSegmented
                      ? 'bg-white/[0.08] text-ink shadow-sm'
                      : 'border-accent-violet text-ink',
                  )
                : cn(
                    isSegmented
                      ? 'text-ink-subtle hover:bg-white/[0.04] hover:text-ink-muted'
                      : 'border-transparent text-ink-subtle hover:text-ink-muted',
                  ),
            )}
          >
            {item.label}
            {item.count != null ? (
              <span
                className={cn(
                  'rounded px-1 py-px font-mono text-[10px] tabular-nums',
                  selected ? 'bg-white/[0.12] text-ink-muted' : 'bg-white/[0.05] text-ink-faint',
                )}
              >
                {item.count}
              </span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}

export interface TabPanelProps {
  value: string;
  active: string;
  children: ReactNode;
  className?: string;
}

export function TabPanel({ value, active, children, className }: TabPanelProps) {
  if (value !== active) return null;
  return (
    <div role="tabpanel" tabIndex={0} className={cn('outline-none', className)}>
      {children}
    </div>
  );
}
