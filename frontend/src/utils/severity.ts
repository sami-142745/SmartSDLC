import type { Category, Severity } from '../types';

export const SEVERITY_ORDER: Severity[] = ['critical', 'high', 'medium', 'low', 'info'];

export const SEVERITY_LABELS: Record<Severity, string> = {
  critical: 'Critical',
  high: 'High',
  medium: 'Medium',
  low: 'Low',
  info: 'Info',
};

export const SEVERITY_BADGE_CLASSES: Record<Severity, string> = {
  critical: 'border-rose-500/25 bg-rose-500/[0.06] text-rose-300',
  high: 'border-orange-400/25 bg-orange-400/[0.06] text-orange-300',
  medium: 'border-amber-400/25 bg-amber-400/[0.06] text-amber-300',
  low: 'border-sky-400/25 bg-sky-400/[0.06] text-sky-300',
  info: 'border-slate-500/30 bg-slate-500/[0.06] text-slate-400',
};

export const SEVERITY_CHART_COLORS: Record<Severity, string> = {
  critical: '#f87171',
  high: '#fb923c',
  medium: '#fbbf24',
  low: '#38bdf8',
  info: '#94a3b8',
};

export const CATEGORY_ORDER: Category[] = [
  'security',
  'bug',
  'performance',
  'complexity',
  'maintainability',
  'style',
];

export const CATEGORY_LABELS: Record<Category, string> = {
  security: 'Security',
  bug: 'Bug',
  performance: 'Performance',
  complexity: 'Complexity',
  maintainability: 'Maintainability',
  style: 'Style',
};

export function severityLabel(value: string | null | undefined): string {
  if (value && value in SEVERITY_LABELS) return SEVERITY_LABELS[value as Severity];
  return 'Info';
}

export function severityBadgeClasses(value: string | null | undefined): string {
  if (value && value in SEVERITY_BADGE_CLASSES) {
    return SEVERITY_BADGE_CLASSES[value as Severity];
  }
  return SEVERITY_BADGE_CLASSES.info;
}

export function severityDotColor(value: string | null | undefined): string {
  switch (value) {
    case 'critical':
      return '#f87171';
    case 'high':
      return '#fb923c';
    case 'medium':
      return '#fbbf24';
    case 'low':
      return '#38bdf8';
    default:
      return '#94a3b8';
  }
}

export function categoryLabel(value: string | null | undefined): string {
  if (value && value in CATEGORY_LABELS) return CATEGORY_LABELS[value as Category];
  return value ?? 'Other';
}

export function sourceLabel(value: string | null | undefined): string {
  if (value === 'gemini') return 'Gemini';
  if (value === 'heuristic') return 'Heuristic';
  if (value === 'combined') return 'Combined';
  return value ?? 'Unknown';
}

export function sourceBadgeClasses(value: string | null | undefined): string {
  if (value === 'gemini') return 'border-violet-400/25 bg-violet-400/[0.06] text-violet-300';
  if (value === 'heuristic') return 'border-sky-400/25 bg-sky-400/[0.06] text-sky-300';
  if (value === 'combined') return 'border-accent-indigo/25 bg-accent-indigo/[0.06] text-accent-indigo';
  return 'border-slate-500/30 bg-slate-500/[0.06] text-slate-400';
}
