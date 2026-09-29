import { useId, useState } from 'react';
import type { ReactNode } from 'react';

import { cn } from '../../lib/cn';

const SIZES = {
  xs: 'h-5 w-5 text-[9px]',
  sm: 'h-6 w-6 text-[10px]',
  md: 'h-8 w-8 text-[11px]',
  lg: 'h-10 w-10 text-[13px]',
  xl: 'h-14 w-14 text-[18px]',
} as const;

export type AvatarSize = keyof typeof SIZES;

export function Avatar({
  name,
  src,
  size = 'md',
  className,
  ring,
}: {
  name: string;
  src?: string | null;
  size?: AvatarSize;
  className?: string;
  ring?: boolean;
}) {
  const [failed, setFailed] = useState(false);
  const initials = name
    .split(/[\s\-_.]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('');

  return (
    <span
      title={name}
      className={cn(
        'inline-flex shrink-0 select-none items-center justify-center overflow-hidden rounded-full font-semibold',
        'bg-gradient-to-br from-accent-violet/30 to-accent-cyan/20 text-accent-lavender',
        ring && 'ring-2 ring-surface-0',
        SIZES[size],
        className,
      )}
    >
      {src && !failed ? (
        <img
          src={src}
          alt=""
          loading="lazy"
          decoding="async"
          onError={() => setFailed(true)}
          className="h-full w-full object-cover"
        />
      ) : (
        <span aria-hidden>{initials || '?'}</span>
      )}
    </span>
  );
}

export interface TooltipProps {
  content: ReactNode;
  children: ReactNode;
  side?: 'top' | 'bottom';
  className?: string;
}

/**
 * CSS-first tooltip that remains reachable by keyboard: the trigger gets focus,
 * and the bubble is rendered in the DOM with `role="tooltip"`. Hover and focus
 * both reveal it via group utilities.
 */
export function Tooltip({ content, children, side = 'top', className }: TooltipProps) {
  const id = useId();
  return (
    <span className={cn('group/tt relative inline-flex', className)}>
      <span aria-describedby={id} className="inline-flex">
        {children}
      </span>
      <span
        id={id}
        role="tooltip"
        className={cn(
          'pointer-events-none absolute left-1/2 z-50 w-max max-w-xs -translate-x-1/2 scale-95',
          'rounded-lg border border-white/[0.09] bg-surface-3/95 px-2.5 py-1.5',
          'text-[11.5px] leading-snug text-ink-muted shadow-lifted backdrop-blur-md',
          'opacity-0 transition-all duration-150 ease-swift',
          'group-hover/tt:scale-100 group-hover/tt:opacity-100',
          'group-focus-within/tt:scale-100 group-focus-within/tt:opacity-100',
          side === 'top' ? 'bottom-[calc(100%+6px)]' : 'top-[calc(100%+6px)]',
        )}
      >
        {content}
      </span>
    </span>
  );
}

export function AvatarStack({
  people,
  max = 5,
  size = 'sm',
}: {
  people: Array<{ login: string; avatarUrl?: string | null }>;
  max?: number;
  size?: AvatarSize;
}) {
  const shown = people.slice(0, max);
  const overflow = people.length - shown.length;
  return (
    <div className="flex items-center">
      {shown.map((person, index) => (
        <Avatar
          key={person.login}
          name={person.login}
          src={person.avatarUrl}
          size={size}
          ring
          className={cn(index > 0 && '-ml-2')}
        />
      ))}
      {overflow > 0 ? (
        <span
          className={cn(
            '-ml-2 inline-flex items-center justify-center rounded-full bg-surface-4 font-mono font-semibold text-ink-subtle ring-2 ring-surface-0',
            SIZES[size],
          )}
        >
          +{overflow}
        </span>
      ) : null}
    </div>
  );
}
