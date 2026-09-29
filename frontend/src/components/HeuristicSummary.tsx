import type { Finding } from '../types';
import { categoryLabel, SEVERITY_LABELS } from '../utils/severity';
import { Badge } from './Badge';
import { cn } from '../lib/cn';

const CATEGORY_TONES: Record<string, string> = {
  security: 'border-rose-400/25 bg-rose-400/[0.07] text-rose-300',
  bug: 'border-amber-400/25 bg-amber-400/[0.07] text-amber-300',
  performance: 'border-emerald-400/25 bg-emerald-400/[0.07] text-emerald-300',
  complexity: 'border-accent-violet/25 bg-accent-violet/[0.08] text-accent-lavender',
  maintainability: 'border-sky-400/25 bg-sky-400/[0.07] text-sky-300',
};

const SEVERITY_TONES: Record<string, string> = {
  critical: 'border-rose-500/25 bg-rose-500/[0.07] text-rose-300',
  high: 'border-orange-400/25 bg-orange-400/[0.07] text-orange-300',
  medium: 'border-amber-400/25 bg-amber-400/[0.07] text-amber-300',
  low: 'border-sky-400/25 bg-sky-400/[0.07] text-sky-300',
};

interface HeuristicSummaryProps {
  findings: Finding[];
  className?: string;
}

/**
 * Roll-up of the deterministic (pattern-matching) scanner results, shown
 * alongside AI findings so reviewers can tell the two sources apart at a glance.
 */
export function HeuristicSummary({ findings, className }: HeuristicSummaryProps) {
  if (findings.length === 0) return null;

  const counts = new Map<string, number>();
  const bySeverity = new Map<string, number>();
  for (const finding of findings) {
    counts.set(finding.category, (counts.get(finding.category) ?? 0) + 1);
    if (finding.heuristic_severity) {
      bySeverity.set(
        finding.heuristic_severity,
        (bySeverity.get(finding.heuristic_severity) ?? 0) + 1,
      );
    }
  }

  return (
    <section className={cn('glass px-4 py-4 sm:px-5', className)}>
      <div className="flex flex-wrap items-center gap-2.5">
        <span aria-hidden className="relative flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-sky-400 opacity-50" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-sky-400" />
        </span>
        <h3 className="section-title">Automated scans</h3>
        <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-faint">
          {findings.length} rule match{findings.length === 1 ? '' : 'es'}
        </span>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {[...counts.entries()].map(([category, count]) => (
          <Badge key={category} className={CATEGORY_TONES[category] ?? CATEGORY_TONES.maintainability}>
            {categoryLabel(category)} &middot; {count}
          </Badge>
        ))}
        {[...bySeverity.entries()].map(([severity, count]) => (
          <Badge key={severity} className={SEVERITY_TONES[severity] ?? SEVERITY_TONES.low}>
            {count} {SEVERITY_LABELS[severity as keyof typeof SEVERITY_LABELS]?.toLowerCase() ?? severity}{' '}
            pattern{count === 1 ? '' : 's'}
          </Badge>
        ))}
      </div>
    </section>
  );
}
