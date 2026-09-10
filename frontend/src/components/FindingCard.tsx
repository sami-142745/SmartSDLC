import { useState } from 'react';

import { Badge } from './Badge';
import { ErrorState } from './ErrorState';
import { SeverityBadge } from './SeverityBadge';
import { submitFeedback } from '../api/reviews';
import type { Finding, FeedbackAction } from '../types';
import { categoryLabel, sourceBadgeClasses, sourceLabel } from '../utils/severity';
import { formatPercent } from '../utils/format';

interface FindingCardProps {
  finding: Finding;
  owner: string;
  repo: string;
  number: number;
  /** Feedback already stored for this finding, keyed by finding id. */
  initialFeedback?: Record<string, FeedbackAction>;
  onFeedbackChange?: (findingId: string, action: FeedbackAction) => void;
}

export function FindingCard({
  finding,
  owner,
  repo,
  number,
  initialFeedback = {},
  onFeedbackChange,
}: FindingCardProps) {
  const [feedback, setFeedback] = useState<{ action: FeedbackAction; submitting: boolean } | null>(
    initialFeedback[finding.id]
      ? { action: initialFeedback[finding.id], submitting: false }
      : null,
  );
  const [error, setError] = useState<string | null>(null);

  const handleFeedback = async (action: FeedbackAction) => {
    if (feedback?.action === action) return;
    setError(null);
    setFeedback((prev) => ({ action: prev?.action ?? action, submitting: true }));
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

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="text-sm font-semibold text-slate-900">{finding.title}</h4>
            <SeverityBadge severity={finding.severity} />
            <Badge className="bg-slate-100 text-slate-600 border-slate-300">
              {categoryLabel(finding.category)}
            </Badge>
            <Badge className={sourceBadgeClasses(finding.source)}>
              {sourceLabel(finding.source)}
            </Badge>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            {finding.file ?? 'unknown file'}
            {finding.line != null ? `:${finding.line}` : ''} · confidence{' '}
            {formatPercent(finding.confidence)}
          </p>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <button
            type="button"
            onClick={() => handleFeedback('accepted')}
            disabled={feedback?.submitting}
            className={`rounded-md border px-2.5 py-1.5 text-xs font-medium shadow-sm ${
              feedback?.action === 'accepted'
                ? 'border-emerald-400 bg-emerald-50 text-emerald-700'
                : 'border-slate-300 bg-white text-slate-600 hover:bg-emerald-50'
            } disabled:cursor-not-allowed disabled:opacity-50`}
          >
            {feedback?.action === 'accepted' ? 'Accepted ✓' : 'Accept'}
          </button>
          <button
            type="button"
            onClick={() => handleFeedback('dismissed')}
            disabled={feedback?.submitting}
            className={`rounded-md border px-2.5 py-1.5 text-xs font-medium shadow-sm ${
              feedback?.action === 'dismissed'
                ? 'border-red-400 bg-red-50 text-red-700'
                : 'border-slate-300 bg-white text-slate-600 hover:bg-red-50'
            } disabled:cursor-not-allowed disabled:opacity-50`}
          >
            {feedback?.action === 'dismissed' ? 'Dismissed ✓' : 'Dismiss'}
          </button>
        </div>
      </div>

      {finding.code && (
        <pre className="mt-3 max-h-40 overflow-auto rounded-md bg-slate-900 p-3 font-mono text-xs text-slate-100">
          {finding.code}
        </pre>
      )}

      <p className="mt-3 text-sm text-slate-700">{finding.description}</p>

      {finding.recommendation && (
        <div className="mt-3 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
          <span className="font-semibold text-slate-700">Suggested fix: </span>
          {finding.recommendation}
        </div>
      )}

      {error && (
        <div className="mt-3">
          <ErrorState title="Feedback not saved" message={error} />
        </div>
      )}
    </div>
  );
}