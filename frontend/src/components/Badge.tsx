import type { ReactNode } from 'react';

interface BadgeProps {
  children: ReactNode;
  className?: string;
}

export function Badge({ children, className = '' }: BadgeProps) {
  return (
    <span className={`chip relative inline-flex items-center gap-1.5 ${className}`}>
      {children}
    </span>
  );
}

const STATE_CLASSES: Record<string, string> = {
  open: 'border-emerald-500/20 bg-emerald-500/[0.06] text-emerald-300',
  closed: 'border-slate-500/30 bg-slate-500/[0.06] text-slate-400',
  merged: 'border-violet-400/25 bg-violet-400/[0.06] text-violet-300',
  complete: 'border-emerald-500/20 bg-emerald-500/[0.06] text-emerald-300',
  gemini_unavailable: 'border-amber-400/25 bg-amber-400/[0.06] text-amber-300',
  failed: 'border-rose-500/25 bg-rose-500/[0.06] text-rose-300',
  running: 'border-sky-400/25 bg-sky-400/[0.06] text-sky-300',
};

export function StateBadge({ state }: { state: string }) {
  const cls = STATE_CLASSES[state] ?? 'border-slate-500/30 bg-slate-500/[0.06] text-slate-400';
  return <Badge className={cls}>{state.replace('_', ' ')}</Badge>;
}
