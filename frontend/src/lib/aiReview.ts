import type { AiReviewCategory, AiReviewSeverity, AiReviewStatus } from '../types';

/** Severity rank used for ordering; lower sorts first. Mirrors the backend. */
const SEVERITY_RANK: Record<AiReviewSeverity, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
  info: 4,
};

export function severityRank(severity: AiReviewSeverity | null | undefined): number {
  return severity ? SEVERITY_RANK[severity] : Number.MAX_SAFE_INTEGER;
}

const CATEGORY_LABELS: Record<AiReviewCategory, string> = {
  bugs: 'Bugs',
  security: 'Security',
  performance: 'Performance',
  code_quality: 'Quality',
  maintainability: 'Maintainability',
  testing: 'Testing',
};

export function categoryLabel(category: AiReviewCategory | string): string {
  return CATEGORY_LABELS[category as AiReviewCategory] ?? category;
}

const STATUS_LABELS: Record<AiReviewStatus, string> = {
  queued: 'Queued',
  in_progress: 'Reviewing',
  complete: 'Complete',
  partial: 'Partial',
  failed: 'Failed',
};

export function aiReviewStatusLabel(status: AiReviewStatus | string): string {
  return STATUS_LABELS[status as AiReviewStatus] ?? status;
}
