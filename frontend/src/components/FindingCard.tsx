import { useState } from 'react';

import { Badge } from './Badge';
import { ErrorState } from './ErrorState';
import { SeverityBadge } from './SeverityBadge';
import { submitFeedback } from '../api/reviews';
import type { Finding, FeedbackAction } from '../types';
import { categoryLabel, severityLabel, sourceBadgeClasses, sourceLabel } from '../utils/severity';
import { formatPercent } from '../utils/format';
import { cn } from '../lib/cn';

interface FindingCardProps {
  finding: Finding;
  owner: string;
  repo: string;
  number: number;
  initialFeedback?: Record<string, FeedbackAction>;
  onFeedbackChange?: (findingId: string, action: FeedbackAction) => void;
}

/** Left rail colour carries severity so a list can be triaged without reading. */
const SEVERITY_EDGE: Record<string, string> = {
  critical: 'border-l-rose-400/70',
  high: 'border-l-orange-400/70',
  medium: 'border-l-amber-400/60',
  low: 'border-l-sky-400/60',
  info: 'border-l-white/25',
};

function FeedbackButton({
  label,
  active,
  submitting,
  onClick,
  activeClasses,
  idleClasses,
}: {
  label: string;
  active: boolean;
  submitting: boolean;
  onClick: () => void;
  activeClasses: string;
  idleClasses: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={submitting}
      aria-pressed={active}
      className={cn(
        'rounded-md border px-2.5 py-1 text-[11.5px] font-medium transition-all duration-150 active:scale-[0.97]',
        'disabled:cursor-not-allowed disabled:opacity-50',
        active ? activeClasses : idleClasses,
      )}
    >
      {/* Accessible name is exactly the visible text ("Accept" / "Accepted ✓");
          `aria-pressed` already conveys the state to assistive tech. */}
      {label}
    </button>
  );
}

export function FindingCard({
  finding,
  owner,
  repo,
  number,
  initialFeedback = {},
  onFeedbackChange,
}: FindingCardProps) {
  const [expanded, setExpanded] = useState(true);
  const [feedback, setFeedback] = useState<{ action: FeedbackAction; submitting: boolean } | null>(
    initialFeedback[finding.id]
      ? { action: initialFeedback[finding.id], submitting: false }
      : null,
  );
  const [error, setError] = useState<string | null>(null);

  const handleFeedback = async (action: FeedbackAction) => {
    if (feedback?.action === action) return;
    setError(null);
    setFeedback({ action: feedback?.action ?? action, submitting: true });
    try {
      await submitFeedback(owner, repo, number, finding.id, action);
      setFeedback({ action, submitting: false });
      onFeedbackChange?.(finding.id, action);
    } catch (err) {
      setError((err as { message?: string }).message ?? 'Could not save your feedback.');
      setFeedback({ action, submitting: false });
    }
  };

  const accepted = feedback?.action === 'accepted';
  const dismissed = feedback?.action === 'dismissed';
  const submitting = feedback?.submitting ?? false;

  return (
    <article
      className={cn(
        'glass-subtle overflow-hidden border-l-2 transition-shadow duration-200 hover:shadow-lifted',
        SEVERITY_EDGE[finding.severity] ?? SEVERITY_EDGE.info,
      )}
    >
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1.5 px-4 py-3">
        <SeverityBadge severity={finding.severity} />
        <Badge className="border-white/[0.07] bg-white/[0.03] text-ink-muted">
          {categoryLabel(finding.category)}
        </Badge>
        {finding.source === 'heuristic' && finding.heuristic_severity ? (
          <Badge className="border-accent-cyan/25 bg-accent-cyan/[0.07] text-accent-cyan">
            pattern &middot; {severityLabel(finding.heuristic_severity)}
          </Badge>
        ) : null}
        <Badge className={sourceBadgeClasses(finding.source)}>{sourceLabel(finding.source)}</Badge>

        <h4 className="ml-1 min-w-0 flex-1 truncate text-[13.5px] font-medium text-ink">
          {finding.title}
        </h4>

        <div className="flex items-center gap-1.5">
          <FeedbackButton
            label={accepted ? 'Accepted \u2713' : 'Accept'}
            active={accepted}
            submitting={submitting}
            onClick={() => handleFeedback('accepted')}
            activeClasses="border-emerald-400/40 bg-emerald-400/10 text-emerald-300"
            idleClasses="border-white/[0.08] text-ink-subtle hover:border-emerald-400/30 hover:text-emerald-300"
          />
          <FeedbackButton
            label={dismissed ? 'Dismissed \u2713' : 'Dismiss'}
            active={dismissed}
            submitting={submitting}
            onClick={() => handleFeedback('dismissed')}
            activeClasses="border-rose-500/40 bg-rose-500/10 text-rose-300"
            idleClasses="border-white/[0.08] text-ink-subtle hover:border-rose-400/30 hover:text-rose-300"
          />
          <button
            type="button"
            onClick={() => setExpanded((value) => !value)}
            aria-expanded={expanded}
            aria-label={expanded ? 'Collapse details' : 'Expand details'}
            className="ml-0.5 rounded-md p-1 text-ink-faint transition-colors hover:bg-white/[0.05] hover:text-ink-muted"
          >
            <svg
              viewBox="0 0 24 24"
              className={cn('h-4 w-4 transition-transform duration-150', !expanded && '-rotate-90')}
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              aria-hidden="true"
            >
              <path d="m6 9 6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </div>
      </div>

      {expanded ? (
        <div className="border-t border-white/[0.05] px-4 py-3">
          <p className="font-mono text-[11.5px] text-ink-faint">
            <span className="text-accent-lavender">{finding.file ?? 'unknown file'}</span>
            {finding.line != null ? (
              <span className="text-amber-300/80">:{finding.line}</span>
            ) : null}
            <span> &middot; confidence {formatPercent(finding.confidence)}</span>
          </p>

          {finding.code ? (
            <pre className="scrollbar-thin mt-2.5 max-h-44 overflow-auto rounded-lg border border-white/[0.05] bg-surface-0 p-3 font-mono text-[11.5px] leading-5 text-ink-muted">
              {finding.code}
            </pre>
          ) : null}

          <p className="mt-2.5 text-[13px] leading-relaxed text-ink-muted">{finding.description}</p>

          {finding.recommendation ? (
            <div className="mt-2.5 flex items-start gap-2.5 rounded-lg border border-accent-violet/15 bg-accent-violet/[0.04] px-3.5 py-2.5">
              <svg
                viewBox="0 0 24 24"
                className="mt-0.5 h-4 w-4 shrink-0 text-accent-lavender"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
                aria-hidden="true"
              >
                <path d="m14.7 6.3 1.4-1.4 3 3-1.4 1.4M9 6.3 7.6 4.9l-3 3 1.4 1.4M12 2 9.5 9.5 2 12l7.5 2.5L12 22l2.5-7.5L22 12l-7.5-2.5L12 2Z" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              <p className="text-[13px] leading-relaxed text-ink-muted">
                <span className="font-medium text-accent-lavender">Suggested fix: </span>
                {finding.recommendation}
              </p>
            </div>
          ) : null}

          {error ? (
            <div className="mt-3">
              <ErrorState title="Feedback not saved" message={error} />
            </div>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}
