import { StateBadge } from './Badge';
import { SeverityBadge } from './SeverityBadge';
import { FeatureCard } from './FeatureCard';
import { Card, CardBody, CardHeader } from './ui/Card';
import { Donut } from './ui/Charts';
import { ScoreGauge } from './ui/ScoreGauge';
import { SEVERITY_CHART_COLORS, SEVERITY_ORDER } from '../utils/severity';
import { formatCount, formatDate } from '../utils/format';
import type { ReviewResponse } from '../types';

function severityCounts(review: ReviewResponse): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const severity of SEVERITY_ORDER) counts[severity] = 0;
  for (const finding of review.findings) {
    if (finding.severity in counts) counts[finding.severity] += 1;
  }
  return counts;
}

interface ReviewSummaryProps {
  review: ReviewResponse;
}

/**
 * Headline verdict for a single review: overall score, severity mix, and the
 * provenance of the findings.
 */
export function ReviewSummary({ review }: ReviewSummaryProps) {
  const counts = severityCounts(review);
  const isPartial = review.status === 'gemini_unavailable';
  // The backend may return either the 0-1 or the 0-100 score; normalise both
  // so the gauge is always meaningful.
  const rawScore = review.review_score_100 ?? review.review_score ?? 0;
  const score = rawScore > 0 && rawScore <= 1 ? rawScore * 100 : rawScore;

  const segments = SEVERITY_ORDER.filter((severity) => (counts[severity] ?? 0) > 0).map(
    (severity) => ({
      key: severity,
      label: severity.charAt(0).toUpperCase() + severity.slice(1),
      value: counts[severity],
      color: SEVERITY_CHART_COLORS[severity],
    }),
  );

  return (
    <Card edge className="overflow-hidden">
      <CardHeader
        title={`Review #${review.pull_request_number}`}
        description={
          <>
            {review.pull_request_title ?? 'Untitled pull request'}
            {review.created_at ? ` \u00b7 ${formatDate(review.created_at)}` : ''}
          </>
        }
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <StateBadge state={review.status} />
            {review.review_severity ? <SeverityBadge severity={review.review_severity} /> : null}
          </div>
        }
      />

      <CardBody className="space-y-5">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 font-mono text-[11.5px]">
          <span className="text-accent-lavender">
            {review.owner}/{review.repository}
          </span>
          {review.commit_sha ? <span className="text-ink-faint">commit {review.commit_sha}</span> : null}
        </div>

        {isPartial ? (
          <div className="flex items-start gap-2.5 rounded-lg border border-amber-400/15 bg-amber-400/[0.05] px-4 py-3">
            <svg viewBox="0 0 24 24" className="mt-0.5 h-4 w-4 shrink-0 text-amber-300" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path d="M12 9v4m0 4h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <span className="text-[13px] leading-relaxed text-amber-200/90">
              AI review completed with heuristic analysis only. Gemini was unavailable, so no
              machine-learning findings were included.
            </span>
          </div>
        ) : null}

        {review.score_explanation ? (
          <div className="rounded-lg border border-white/[0.06] bg-surface-2/60 px-4 py-3">
            <p className="text-[13px] leading-relaxed text-ink-muted">{review.score_explanation}</p>
            {review.score_breakdown && Object.keys(review.score_breakdown).length > 0 ? (
              <p className="mt-2 text-[11.5px] text-ink-faint">
                Penalty breakdown:&nbsp;
                {Object.entries(review.score_breakdown)
                  .filter(([, n]) => (n as number) > 0)
                  .map(([sev, n]) => `${n} ${sev}`)
                  .join(' \u00b7 ') || 'no penalties'}
              </p>
            ) : null}
          </div>
        ) : null}

        <div className="grid grid-cols-1 gap-5 lg:grid-cols-[auto_1fr]">
          <div className="flex items-center justify-center lg:border-r lg:border-white/[0.06] lg:pr-6">
            <ScoreGauge score={score} label="Overall score" size={124} caption="of 100" />
          </div>

          <div className="min-w-0 space-y-4">
            {segments.length > 0 ? (
              <Donut
                segments={segments}
                size={132}
                thickness={12}
                centerValue={formatCount(review.total_finding_count)}
                centerLabel="findings"
              />
            ) : null}

            <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
              <FeatureCard label="Total findings" value={formatCount(review.total_finding_count)} />
              <FeatureCard label="AI findings" value={formatCount(review.gemini_finding_count)} />
              <FeatureCard label="Heuristic" value={formatCount(review.heuristic_finding_count)} />
              <FeatureCard
                label="Duration"
                value={review.duration_ms != null ? `${review.duration_ms} ms` : '\u2014'}
              />
            </div>
          </div>
        </div>
      </CardBody>
    </Card>
  );
}
