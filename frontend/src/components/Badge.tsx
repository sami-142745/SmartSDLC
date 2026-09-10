import type { ReactNode } from 'react';

interface BadgeProps {
  children: ReactNode;
  className?: string;
}

export function Badge({ children, className = '' }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${className}`}
    >
      {children}
    </span>
  );
}

export function StateBadge({ state }: { state: string }) {
  const map: Record<string, string> = {
    open: 'bg-emerald-100 text-emerald-800 border-emerald-300',
    closed: 'bg-red-100 text-red-800 border-red-300',
    merged: 'bg-violet-100 text-violet-800 border-violet-300',
    complete: 'bg-emerald-100 text-emerald-800 border-emerald-300',
    gemini_unavailable: 'bg-amber-100 text-amber-800 border-amber-300',
    failed: 'bg-red-100 text-red-800 border-red-300',
    running: 'bg-sky-100 text-sky-800 border-sky-300',
  };
  const cls = map[state] ?? 'bg-slate-100 text-slate-700 border-slate-300';
  return <Badge className={cls}>{state.replace('_', ' ')}</Badge>;
}