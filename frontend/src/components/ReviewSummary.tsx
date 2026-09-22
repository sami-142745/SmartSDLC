import { FeatureCard } from './FeatureCard';
import { SeverityBadge } from './SeverityBadge';
import { StateBadge } from './Badge';
import type { ReviewResponse } from '../types';
import { formatDate, formatCount } from '../utils/format';

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
    <section className="relative overflow-hidden rounded-2xl border border-white/[0.07] bg-glass-gradient p-5 sm:p-6">
      <span
        aria-hidden
        className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-accent-indigo/50 to-transparent"
      />
      <span
        aria-hidden
        className="pointer-events-none absolute -right-20 -top-24 h-48 w-64 rounded-full bg-accent-indigo/[0.06] blur-[70px]"
      />
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold tracking-tight text-slate-50">
            Review #{review.pull_request_number}
          </h3>
          <p className="mt-1 text-sm text-slate-500">
            {review.pull_request_title ?? 'Untitled pull request'}
            {review.created_at ? ` \u00B7 ${formatDate(review.created_at)}` : ''}
          </p>
          <p className="mt-1 font-mono text-xs text-accent-indigo">
            {review.owner}/{review.repository}
          </p>
          {review.commit_sha && (
            <p className="mt-0.5 font-mono text-xs text-slate-600">commit {review.commit_sha}</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <StateBadge state={review.status} />
          {review.review_severity && <SeverityBadge severity={review.review_severity} />}
        </div>
      </div>

      {isPartial && (
        <div className="mt-4 flex items-start gap-2 border border-amber-400/15 bg-amber-400/[0.04] px-4 py-3">
          <svg viewBox="0 0 24 24" className="mt-0.5 h-4 w-4 shrink-0 text-amber-300" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <path d="M12 9v4m0 4h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span className="text-sm text-amber-200/90">
            AI review completed with heuristic analysis only. Gemini was unavailable, so no
            machine-learning findings were included.
          </span>
        </div>
      )}

      <div className="mt-6">
        {review.score_explanation && (
          <div className="rounded-xl border border-white/[0.05] bg-surface-2/70 px-4 py-3">
            <p className="text-sm leading-relaxed text-slate-300">{review.score_explanation}</p>
            {review.score_breakdown && Object.keys(review.score_breakdown).length > 0 && (
              <p className="mt-2 text-xs text-slate-500">
                Penalty breakdown:&nbsp;
                {Object.entries(review.score_breakdown)
                  .filter(([, n]) => (n as number) > 0)
                  .map(([sev, n]) => `${n} ${sev}`)
                  .join(' \u00B7 ') || 'no penalties'}
              </p>
            )}
          </div>
        )}

        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
            <span className="eyebrow">Severity</span>
            {(Object.keys(counts) as Array<keyof typeof counts>).map((severity) => (
              <span key={severity} className="flex items-center gap-1.5">
                <SeverityBadge severity={severity} />
                <span className="text-xs font-semibold tabular-nums text-slate-300">
                  {counts[severity]}
                </span>
              </span>
            ))}
          </div>

          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <FeatureCard label="Total findings" value={formatCount(review.total_finding_count)} />
            <FeatureCard label="AI findings" value={formatCount(review.gemini_finding_count)} />
            <FeatureCard label="Heuristic" value={formatCount(review.heuristic_finding_count)} />
            <FeatureCard
              label="Duration"
              value={review.duration_ms != null ? `${review.duration_ms} ms` : '\u2014'}
            />
          </div>

          <div className="flex flex-wrap gap-x-5 gap-y-1.5 text-xs text-slate-500">
            <span className="inline-flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-violet-400" /> Gemini AI analysis
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-sky-400" /> Heuristic rules
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-rose-400" /> Severity classified
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}
