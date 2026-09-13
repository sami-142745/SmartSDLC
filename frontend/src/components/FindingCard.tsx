import { useState } from 'react';

import { Badge } from './Badge';
import { ErrorState } from './ErrorState';
import { SeverityBadge } from './SeverityBadge';
import { submitFeedback } from '../api/reviews';
import type { Finding, FeedbackAction } from '../types';
import { categoryLabel, severityLabel, sourceBadgeClasses, sourceLabel } from '../utils/severity';
import { formatPercent } from '../utils/format';

interface FindingCardProps {
  finding: Finding;
  owner: string;
  repo: string;
  number: number;
  initialFeedback?: Record<string, FeedbackAction>;
  onFeedbackChange?: (findingId: string, action: FeedbackAction) => void;
}

const SEVERITY_EDGE: Record<string, string> = {
  critical: 'border-l-rose-400/70',
  high: 'border-l-orange-400/70',
  medium: 'border-l-amber-400/60',
  low: 'border-l-sky-400/60',
  info: 'border-l-slate-400/40',
};

const SEVERITY_GLOW: Record<string, string> = {
  critical: 'hover:shadow-[0_0_28px_-12px_rgba(248,113,113,0.35)]',
  high: 'hover:shadow-[0_0_28px_-12px_rgba(251,146,60,0.3)]',
  medium: 'hover:shadow-[0_0_28px_-12px_rgba(251,191,36,0.25)]',
  low: 'hover:shadow-[0_0_28px_-12px_rgba(56,189,248,0.25)]',
  info: 'hover:shadow-[0_0_28px_-12px_rgba(148,163,184,0.2)]',
};

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
      const message =
        (err as { message?: string }).message ?? 'Could not save your feedback.';
      setFeedback({ action, submitting: false });
      setError(message);
    }
  };

  const glow = SEVERITY_GLOW[finding.severity] ?? SEVERITY_GLOW.info;
  const edge = SEVERITY_EDGE[finding.severity] ?? SEVERITY_EDGE.info;

  return (
    <div
      className={`relative overflow-hidden rounded-xl border border-white/[0.06] border-l-2 bg-surface-1/70 backdrop-blur-sm transition-all duration-200 hover:-translate-y-0.5 hover:border-white/[0.1] ${edge} ${glow} ${
        finding.severity === 'critical' ? 'critical-pulse' : ''
      }`}
    >
      <span
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/[0.08] to-transparent"
      />
      {/* Header row */}
      <div className="relative flex flex-wrap items-center gap-x-2 gap-y-1.5 px-4 py-3">
        <SeverityBadge severity={finding.severity} />
        <Badge className="border-white/[0.06] bg-white/[0.03] text-slate-400">
          {categoryLabel(finding.category)}
        </Badge>
        {finding.source === 'heuristic' && finding.heuristic_severity ? (
          <Badge className="border-teal-400/20 bg-teal-400/[0.06] text-teal-300">
            pattern &middot; {severityLabel(finding.heuristic_severity)}
          </Badge>
        ) : null}
        <Badge className={sourceBadgeClasses(finding.source)}>
          {sourceLabel(finding.source)}
        </Badge>
        <h4 className="ml-1 min-w-0 flex-1 truncate text-sm font-medium text-slate-100">
          {finding.title}
        </h4>

        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => handleFeedback('accepted')}
            disabled={feedback?.submitting}
            aria-pressed={feedback?.action === 'accepted'}
            className={`rounded-lg border px-2.5 py-1 text-xs font-medium transition-all duration-150 active:scale-[0.97] ${
              feedback?.action === 'accepted'
                ? 'border-emerald-400/40 bg-emerald-400/10 text-emerald-300 shadow-[0_0_14px_-6px_rgba(52,211,153,0.5)]'
                : 'border-white/[0.08] bg-transparent text-slate-400 hover:border-emerald-400/30 hover:text-emerald-300 hover:shadow-[0_0_14px_-8px_rgba(52,211,153,0.4)]'
            } disabled:cursor-not-allowed disabled:opacity-50`}
          >
            {feedback?.action === 'accepted' ? 'Accepted \u2713' : 'Accept'}
          </button>
          <button
            type="button"
            onClick={() => handleFeedback('dismissed')}
            disabled={feedback?.submitting}
            aria-pressed={feedback?.action === 'dismissed'}
            className={`rounded-lg border px-2.5 py-1 text-xs font-medium transition-all duration-150 active:scale-[0.97] ${
              feedback?.action === 'dismissed'
                ? 'border-rose-500/40 bg-rose-500/10 text-rose-300 shadow-[0_0_14px_-6px_rgba(244,63,94,0.5)]'
                : 'border-white/[0.08] bg-transparent text-slate-400 hover:border-rose-400/30 hover:text-rose-300 hover:shadow-[0_0_14px_-8px_rgba(244,63,94,0.4)]'
            } disabled:cursor-not-allowed disabled:opacity-50`}
          >
            {feedback?.action === 'dismissed' ? 'Dismissed \u2713' : 'Dismiss'}
          </button>
          <button
            type="button"
            onClick={() => setExpanded((value) => !value)}
            aria-label={expanded ? 'Collapse details' : 'Expand details'}
            className="ml-1 rounded-lg p-1 text-slate-500 transition-colors hover:bg-white/[0.04] hover:text-slate-200"
          >
            <svg
              viewBox="0 0 24 24"
              className={`h-4 w-4 transition-transform duration-150 ${expanded ? '' : '-rotate-90'}`}
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

      {/* Divider */}
      <div className="relative mx-4 border-t border-white/[0.05]" />

      {expanded && (
        <div className="relative px-4 py-3">
          <p className="font-mono text-xs text-slate-500">
            <span className="text-accent-indigo">{finding.file ?? 'unknown file'}</span>
            {finding.line != null ? (
              <span className="text-amber-300/80">:{finding.line}</span>
            ) : null}
            <span className="text-slate-600"> &#x00B7; confidence {formatPercent(finding.confidence)}</span>
          </p>

          {finding.code && (
            <pre className="mt-2.5 max-h-44 overflow-auto rounded-lg border border-white/[0.05] bg-surface-0 p-3 font-mono text-xs leading-5 text-slate-300">
              {finding.code}
            </pre>
          )}

          <p className="mt-2.5 text-sm leading-relaxed text-slate-400">{finding.description}</p>

          {finding.recommendation && (
            <div className="mt-2.5 flex items-start gap-2.5 rounded-lg border border-accent-indigo/10 bg-accent-indigo/[0.03] px-3.5 py-2.5">
              <svg
                viewBox="0 0 24 24"
                className="mt-0.5 h-4 w-4 shrink-0 text-accent-indigo"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
                aria-hidden="true"
              >
                <path d="m14.7 6.3 1.4-1.4 3 3-1.4 1.4M9 6.3 7.6 4.9l-3 3 1.4 1.4M12 2 9.5 9.5 2 12l7.5 2.5L12 22l2.5-7.5L22 12l-7.5-2.5L12 2Z" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              <p className="text-sm leading-relaxed text-slate-300">
                <span className="font-medium text-accent-indigo">Suggested fix: </span>
                {finding.recommendation}
              </p>
            </div>
          )}

          {error && (
            <div className="mt-3">
              <ErrorState title="Feedback not saved" message={error} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}