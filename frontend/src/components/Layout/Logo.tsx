import { Link } from 'react-router-dom';

import { cn } from '../../lib/cn';

/**
 * Brand mark. The glyph is an inline SVG rather than an asset so it inherits
 * currentColor and stays crisp at any size.
 */
export function LogoMark({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        'inline-flex shrink-0 items-center justify-center rounded-lg bg-brand-gradient text-white shadow-glow-sm',
        className ?? 'h-8 w-8',
      )}
      aria-hidden="true"
    >
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-[55%] w-[55%]">
        <path d="m9 6-6 6 6 6M15 6l6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </span>
  );
}

export function Logo({ collapsed = false, className }: { collapsed?: boolean; className?: string }) {
  return (
    <Link
      to="/dashboard"
      className={cn('group/logo flex items-center rounded-lg', collapsed ? '' : 'gap-2.5', className)}
      aria-label="SmartSDLC dashboard"
    >
      <LogoMark />
      {collapsed ? null : (
        <span className="min-w-0">
          <span className="block truncate text-[13.5px] font-semibold leading-tight tracking-tight text-ink">
            SmartSDLC
          </span>
          <span className="block truncate font-mono text-[9px] uppercase leading-tight tracking-[0.16em] text-ink-faint">
            AI review ops
          </span>
        </span>
      )}
    </Link>
  );
}
