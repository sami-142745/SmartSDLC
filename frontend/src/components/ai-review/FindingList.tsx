import { AI_REVIEW_CATEGORIES, AI_REVIEW_FILE_LEVEL_LINE } from '../../types';
import { cn } from '../../lib/cn';
import { categoryLabel } from '../../lib/aiReview';
import type {
  AiReviewCategory,
  AiReviewFinding,
  AiReviewSeverity,
} from '../../types';

const CATEGORY_CLASSES: Record<AiReviewCategory, string> = {
  bugs: 'border-rose-500/25 bg-rose-500/10 text-rose-300',
  security: 'border-orange-500/25 bg-orange-500/10 text-orange-300',
  performance: 'border-amber-500/25 bg-amber-500/10 text-amber-300',
  code_quality: 'border-sky-500/25 bg-sky-500/10 text-sky-300',
  maintainability: 'border-indigo-500/25 bg-indigo-500/10 text-indigo-300',
  testing: 'border-emerald-500/25 bg-emerald-500/10 text-emerald-300',
};

const SEVERITY_RANK: Record<AiReviewSeverity, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
  info: 4,
};

/** Mirrors the backend's default ordering so both views agree. */
export function sortAiReviewFindings(
  findings: AiReviewFinding[],
  sort: 'severity' | 'confidence' | 'category' | 'file' | 'line' = 'severity',
): AiReviewFinding[] {
  const copy = [...findings];
  switch (sort) {
    case 'confidence':
      copy.sort((a, b) => b.confidence - a.confidence || SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity]);
      break;
    case 'category':
      copy.sort(
        (a, b) =>
          AI_REVIEW_CATEGORIES.indexOf(a.category) - AI_REVIEW_CATEGORIES.indexOf(b.category) ||
          SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity],
      );
      break;
    case 'file':
      copy.sort(
        (a, b) => a.file.localeCompare(b.file) || a.line - b.line || SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity],
      );
      break;
    case 'line':
      copy.sort(
        (a, b) => a.file.localeCompare(b.file) || a.line - b.line || SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity],
      );
      break;
    default:
      copy.sort((a, b) => SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity] || b.confidence - a.confidence);
  }
  return copy;
}

export interface FindingListProps {
  findings: AiReviewFinding[];
  activeFindingId: string | null;
  onSelect: (finding: AiReviewFinding) => void;
  sort: 'severity' | 'confidence' | 'category' | 'file' | 'line';
  onSortChange: (sort: FindingListProps['sort']) => void;
}

/**
 * Right pane of the review workspace.
 *
 * Findings are listed rather than overlaid on the diff so the reviewer can
 * triage the whole set, then jump to any one of them. `line === 0` is the
 * backend's file-level sentinel, and those entries say "whole file" rather
 * than pretending to point at line 0.
 */
export function FindingList({
  findings,
  activeFindingId,
  onSelect,
  sort,
  onSortChange,
}: FindingListProps) {
  if (findings.length === 0) {
    return (
      <p className="px-4 py-8 text-center text-[12.5px] text-ink-faint">
        No findings for the current filters.
      </p>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between gap-2 border-b border-white/[0.05] px-3 py-2">
        <span className="eyebrow">Findings</span>
        <div className="flex items-center gap-2">
          <span className="font-mono text-[10.5px] tabular-nums text-ink-faint">
            {findings.length}
          </span>
          <label className="sr-only" htmlFor="ai-review-sort">
            Sort findings
          </label>
          <select
            id="ai-review-sort"
            value={sort}
            onChange={(event) => onSortChange(event.target.value as FindingListProps['sort'])}
            className="rounded-md border border-white/[0.09] bg-surface-2 px-2 py-1 font-mono text-[10.5px] text-ink-muted outline-none focus-visible:shadow-focus"
          >
            <option value="severity">Severity</option>
            <option value="confidence">Confidence</option>
            <option value="category">Category</option>
            <option value="file">File</option>
            <option value="line">Line</option>
          </select>
        </div>
      </div>

      <ul className="flex flex-1 flex-col gap-2 overflow-y-auto p-2" role="list">
        {findings.map((finding) => {
          const active = finding.finding_id === activeFindingId;
          const fileLevel = finding.line === AI_REVIEW_FILE_LEVEL_LINE;
          return (
            <li key={finding.finding_id}>
              <button
                type="button"
                onClick={() => onSelect(finding)}
                aria-current={active ? 'true' : undefined}
                className={cn(
                  'w-full rounded-lg border p-3 text-left transition-colors',
                  active
                    ? 'border-accent-violet/50 bg-accent-violet/[0.08]'
                    : 'border-white/[0.06] bg-surface-1/40 hover:border-white/[0.12] hover:bg-white/[0.03]',
                )}
              >
                <span className="flex flex-wrap items-center gap-1.5">
                  <span
                    className={cn(
                      'rounded border px-1.5 py-0.5 font-mono text-[9.5px] uppercase tracking-wide',
                      CATEGORY_CLASSES[finding.category],
                    )}
                  >
                    {categoryLabel(finding.category)}
                  </span>
                  <span className="inline-flex items-center gap-1.5 rounded border border-white/12 bg-white/[0.04] px-1.5 py-0.5 font-mono text-[9.5px] uppercase tracking-wide">
                    <SeverityPip severity={finding.severity} />
                  </span>
                  {finding.source !== 'ai' ? (
                    <span className="rounded border border-white/12 bg-white/[0.04] px-1.5 py-0.5 font-mono text-[9.5px] uppercase tracking-wide text-ink-faint">
                      {finding.source}
                    </span>
                  ) : null}
                </span>

                <span className="mt-2 block text-[13px] font-medium leading-snug text-ink">
                  {finding.title}
                </span>
                <span className="mt-1 block text-[12px] leading-relaxed text-ink-muted">
                  {finding.description}
                </span>

                <span className="mt-2 flex items-center gap-2 font-mono text-[10.5px] text-ink-faint">
                  <span className="min-w-0 truncate" title={finding.file}>
                    {finding.file}
                  </span>
                  <span aria-hidden>·</span>
                  <span className="shrink-0 tabular-nums">
                    {fileLevel ? 'whole file' : `L${finding.line}`}
                  </span>
                  <span aria-hidden>·</span>
                  <span className="shrink-0 tabular-nums">
                    {Math.round(finding.confidence * 100)}% conf
                  </span>
                </span>

                {finding.suggestion ? (
                  <span className="mt-2 block rounded-md border border-white/[0.06] bg-surface-0/60 px-2.5 py-1.5 text-[12px] leading-relaxed text-ink-subtle">
                    {finding.suggestion}
                  </span>
                ) : null}
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function SeverityPip({ severity }: { severity: AiReviewSeverity }) {
  return (
    <span className="inline-flex items-center gap-1 text-ink-muted">
      <SeverityDot severity={severity} />
      {severity}
    </span>
  );
}

function SeverityDot({ severity }: { severity: AiReviewSeverity }) {
  const color =
    severity === 'critical'
      ? '#F43F5E'
      : severity === 'high'
        ? '#FB923C'
        : severity === 'medium'
          ? '#FBBF24'
          : severity === 'low'
            ? '#38BDF8'
            : '#94A3B8';
  return (
    <span
      aria-hidden
      className="h-1.5 w-1.5 rounded-full"
      style={{ backgroundColor: color, boxShadow: `0 0 6px ${color}` }}
    />
  );
}
