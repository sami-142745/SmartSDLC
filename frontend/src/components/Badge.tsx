import type { ReactNode } from 'react';

import { cn } from '../lib/cn';

interface BadgeProps {
  children: ReactNode;
  className?: string;
}

/**
 * Thin wrapper over the design-system `Badge` so domain components can keep
 * overriding colours via `className` where a semantic mapping does not exist.
 */
export function Badge({ children, className }: BadgeProps) {
  return <span className={cn('chip', className)}>{children}</span>;
}

/**
 * Maps every review/workflow state the backend can emit to a colour. Unknown
 * states fall back to neutral rather than silently inheriting the previous tone.
 */
const STATE_TONES: Record<string, { classes: string; label: string }> = {
  open: { classes: 'border-emerald-500/25 bg-emerald-500/10 text-emerald-300', label: 'open' },
  closed: { classes: 'border-white/[0.09] bg-white/[0.04] text-ink-subtle', label: 'closed' },
  merged: { classes: 'border-accent-violet/30 bg-accent-violet/10 text-accent-lavender', label: 'merged' },
  draft: { classes: 'border-white/[0.09] bg-white/[0.04] text-ink-subtle', label: 'draft' },
  complete: { classes: 'border-emerald-500/25 bg-emerald-500/10 text-emerald-300', label: 'complete' },
  completed: { classes: 'border-emerald-500/25 bg-emerald-500/10 text-emerald-300', label: 'completed' },
  pending: { classes: 'border-white/[0.09] bg-white/[0.04] text-ink-subtle', label: 'pending' },
  queued: { classes: 'border-sky-400/25 bg-sky-400/10 text-sky-300', label: 'queued' },
  running: { classes: 'border-sky-400/25 bg-sky-400/10 text-sky-300', label: 'running' },
  in_progress: { classes: 'border-sky-400/25 bg-sky-400/10 text-sky-300', label: 'in progress' },
  gemini_unavailable: { classes: 'border-amber-400/25 bg-amber-400/10 text-amber-300', label: 'gemini unavailable' },
  unavailable: { classes: 'border-amber-400/25 bg-amber-400/10 text-amber-300', label: 'unavailable' },
  failed: { classes: 'border-rose-500/25 bg-rose-500/10 text-rose-300', label: 'failed' },
  error: { classes: 'border-rose-500/25 bg-rose-500/10 text-rose-300', label: 'error' },
  cancelled: { classes: 'border-white/[0.09] bg-white/[0.04] text-ink-faint', label: 'cancelled' },
};

export function stateTone(state: string) {
  return STATE_TONES[state] ?? { classes: STATE_TONES.pending.classes, label: state.replace(/_/g, ' ') };
}

export function StateBadge({ state }: { state: string }) {
  const tone = stateTone(state);
  return (
    <Badge className={cn(tone.classes, 'capitalize')}>
      <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-current" />
      {tone.label}
    </Badge>
  );
}
