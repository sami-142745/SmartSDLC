import { cn } from '../../lib/cn';

export type SpinnerSize = 'xs' | 'sm' | 'md' | 'lg';

const SIZE_CLASSES: Record<SpinnerSize, string> = {
  xs: 'h-3 w-3 border',
  sm: 'h-3.5 w-3.5 border-2',
  md: 'h-5 w-5 border-2',
  lg: 'h-8 w-8 border-[3px]',
};

export function Spinner({
  size = 'md',
  className,
  label,
}: {
  size?: SpinnerSize;
  className?: string;
  /** Accessible label. Pass null to hide the spinner from assistive tech. */
  label?: string | null;
}) {
  return (
    <span
      role={label ? 'status' : undefined}
      aria-label={label ?? undefined}
      aria-hidden={label ? undefined : true}
      className={cn(
        'inline-block shrink-0 animate-spin-slow rounded-full border-current border-t-transparent opacity-80',
        SIZE_CLASSES[size],
        className,
      )}
    />
  );
}
