import { SeverityBadge } from '../SeverityBadge';
import { cn } from '../../lib/cn';
import { aiReviewStatusLabel } from '../../lib/aiReview';
import type { AiReview, AiReviewStatus, AiReviewAiStatus } from '../../types';

const STATUS_CLASSES: Record<AiReviewStatus, string> = {
  queued: 'border-white/15 bg-white/[0.05] text-ink-muted',
  in_progress: 'border-sky-500/30 bg-sky-500/10 text-sky-300',
  complete: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',
  partial: 'border-amber-500/30 bg-amber-500/10 text-amber-300',
  failed: 'border-rose-500/30 bg-rose-500/10 text-rose-300',
};

/**
 * Why the model leg did or did not contribute. `complete` needs no
 * explanation; the other three all mean the reviewer is looking at fewer
 * findings than a full pass would have produced, so each says so plainly.
 */
const AI_STATUS_NOTE: Record<AiReviewAiStatus, string | null> = {
  complete: null,
  unavailable: 'The model was unreachable, so these findings come from static analysis only.',
  malformed: 'The model returned output that did not match the expected format and was discarded.',
  skipped: 'The model was not run, because there was no reviewable text diff to send.',
};

export interface AssessmentPanelProps {
  review: AiReview;
  className?: string;
}

/**
 * Headline panel for the review: the labelled score, the six assessment
 * dimensions, and the lifecycle state of the run.
 *
 * The label is fixed text rather than a computed value. An "AI review
 * assessment" score covers the diff under review, not the health of the
 * repository, and the disclaimer is what stops a reader from treating 72/100
 * as a verdict on the codebase.
 */
export function AssessmentPanel({ review, className }: AssessmentPanelProps) {
  const { summary } = review;
  const aiNote = AI_STATUS_NOTE[review.ai_status];

  return (
    <section
      className={cn(
        'rounded-xl border border-white/[0.07] bg-surface-1/60 p-4 shadow-elevated',
        className,
      )}
      aria-label="AI review assessment"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="eyebrow">{summary.assessment_label}</p>
          <div className="mt-1.5 flex items-baseline gap-2">
            <span className="font-mono text-3xl font-semibold tabular-nums text-ink">
              {summary.assessment_score}
            </span>
            <span className="font-mono text-[12px] text-ink-faint">/100</span>
            <SeverityBadge severity={summary.assessment_severity} />
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span
            className={cn(
              'rounded-full border px-2.5 py-1 font-mono text-[10.5px] uppercase tracking-wide',
              STATUS_CLASSES[review.status],
            )}
          >
            {aiReviewStatusLabel(review.status)}
          </span>
          {review.ai_status !== 'complete' ? (
            <span className="rounded-full border border-white/15 bg-white/[0.04] px-2.5 py-1 font-mono text-[10.5px] uppercase tracking-wide text-ink-muted">
              AI {review.ai_status.replace('_', ' ')}
            </span>
          ) : null}
        </div>
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3">
        {summary.metrics.map((metric) => (
          <div key={metric.dimension} className="min-w-0">
            <dt className="flex items-baseline justify-between gap-2">
              <span className="truncate text-[11.5px] text-ink-subtle" title={metric.label}>
                {metric.label}
              </span>
              <span className="font-mono text-[11.5px] tabular-nums text-ink-muted">
                {metric.score}
              </span>
            </dt>
            <dd className="mt-1.5 h-1 overflow-hidden rounded-full bg-white/[0.06]">
              <span
                className="block h-full rounded-full bg-accent-violet/70"
                style={{ width: `${Math.max(0, Math.min(100, metric.score))}%` }}
              />
            </dd>
            <p className="mt-1 font-mono text-[10.5px] text-ink-faint">
              {metric.finding_count} finding{metric.finding_count === 1 ? '' : 's'}
            </p>
          </div>
        ))}
      </dl>

      <dl className="mt-4 flex flex-wrap gap-x-5 gap-y-1 border-t border-white/[0.05] pt-3 font-mono text-[11px] text-ink-faint">
        <div className="flex gap-1.5">
          <dt>files</dt>
          <dd className="tabular-nums text-ink-subtle">{summary.files_reviewed}</dd>
        </div>
        <div className="flex gap-1.5">
          <dt>added</dt>
          <dd className="tabular-nums text-emerald-400/85">+{summary.lines_added}</dd>
        </div>
        <div className="flex gap-1.5">
          <dt>deleted</dt>
          <dd className="tabular-nums text-rose-400/85">-{summary.lines_deleted}</dd>
        </div>
        <div className="flex gap-1.5">
          <dt>findings</dt>
          <dd className="tabular-nums text-ink-subtle">{summary.total_findings}</dd>
        </div>
      </dl>

      {aiNote ? (
        <p className="mt-3 rounded-lg border border-amber-500/20 bg-amber-500/[0.07] px-3 py-2 text-[12px] leading-relaxed text-amber-200/90">
          {aiNote}
        </p>
      ) : null}

      <p className="mt-3 text-[11.5px] leading-relaxed text-ink-faint">
        {summary.assessment_disclaimer}
      </p>
    </section>
  );
}
