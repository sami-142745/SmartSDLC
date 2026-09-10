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
  critical: 'bg-red-100 text-red-800 border-red-300',
  high: 'bg-orange-100 text-orange-800 border-orange-300',
  medium: 'bg-yellow-100 text-yellow-800 border-yellow-300',
  low: 'bg-blue-100 text-blue-800 border-blue-300',
  info: 'bg-slate-100 text-slate-700 border-slate-300',
};

export const SEVERITY_CHART_COLORS: Record<Severity, string> = {
  critical: '#dc2626',
  high: '#ea580c',
  medium: '#eab308',
  low: '#2563eb',
  info: '#6b7280',
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
  if (value === 'gemini') return 'bg-violet-100 text-violet-800 border-violet-300';
  if (value === 'heuristic') return 'bg-teal-100 text-teal-800 border-teal-300';
  if (value === 'combined') return 'bg-indigo-100 text-indigo-800 border-indigo-300';
  return 'bg-slate-100 text-slate-700 border-slate-300';
}