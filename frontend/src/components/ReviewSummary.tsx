import { FeatureCard } from './FeatureCard';
import { SeverityBadge } from './SeverityBadge';
import { StateBadge } from './Badge';
import type { ReviewResponse } from '../types';
import { formatDate, formatCount, formatPercent } from '../utils/format';

function severityCounts(review: ReviewResponse): Record<string, number> {
  const counts: Record<string, number> = {
    critical: 0,
    high: 0,
    medium: 0,
    low: 0,
    info: 0,
  };
  for (const finding of review.findings) {
    if (finding.severity in counts) counts[finding.severity] += 1;
  }
  return counts;
}

interface ReviewSummaryProps {
  review: ReviewResponse;
}

export function ReviewSummary({ review }: ReviewSummaryProps) {
  const counts = severityCounts(review);
  const isPartial = review.status === 'gemini_unavailable';

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-slate-900">
            Review #{review.pull_request_number}
          </h3>
          <p className="mt-1 text-sm text-slate-500">
            {review.pull_request_title ?? 'Untitled pull request'}
            {review.created_at ? ` · ${formatDate(review.created_at)}` : ''}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <StateBadge state={review.status} />
          {review.review_severity && <SeverityBadge severity={review.review_severity} />}
        </div>
      </div>

      {isPartial && (
        <div className="mt-4 flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
          <span className="text-sm text-amber-800">
            AI review completed with heuristic analysis only. Gemini was unavailable, so no
            machine-learning findings were included.
          </span>
        </div>
      )}

      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <FeatureCard label="Total findings" value={formatCount(review.total_finding_count)} />
        <FeatureCard label="Heuristic" value={formatCount(review.heuristic_finding_count)} />
        <FeatureCard label="Gemini" value={formatCount(review.gemini_finding_count)} />
        <FeatureCard
          label="Score"
          value={review.review_score != null ? review.review_score.toString() : '—'}
        />
        <FeatureCard
          label="Duration"
          value={review.duration_ms != null ? `${review.duration_ms} ms` : '—'}
        />
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium uppercase tracking-wide text-slate-500">
          Severity:
        </span>
        {Object.entries(counts).map(([severity, count]) => (
          <span key={severity} className="flex items-center gap-1.5">
            <SeverityBadge severity={severity} />
            <span className="text-xs tabular-nums text-slate-600">{count}</span>
          </span>
        ))}
      </div>

      {review.commit_sha && (
        <p className="mt-3 font-mono text-xs text-slate-400">commit {review.commit_sha}</p>
      )}
    </div>
  );
}