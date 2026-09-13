import { Badge } from './Badge';
import type { Finding } from '../types';
import { categoryLabel } from '../utils/severity';

const CATEGORY_TONES: Record<string, string> = {
  security: 'border-rose-400/25 bg-rose-400/[0.06] text-rose-300',
  bug: 'border-amber-400/25 bg-amber-400/[0.06] text-amber-300',
  performance: 'border-emerald-400/25 bg-emerald-400/[0.06] text-emerald-300',
  complexity: 'border-violet-400/25 bg-violet-400/[0.06] text-violet-300',
  maintainability: 'border-sky-400/25 bg-sky-400/[0.06] text-sky-300',
};

interface HeuristicSummaryProps {
  findings: Finding[];
}

export function HeuristicSummary({ findings }: HeuristicSummaryProps) {
  if (findings.length === 0) return null;

  const counts = new Map<string, number>();
  let critical = 0;
  let high = 0;
  let medium = 0;
  for (const finding of findings) {
    counts.set(finding.category, (counts.get(finding.category) ?? 0) + 1);
    if (finding.heuristic_severity === 'critical') critical += 1;
    else if (finding.heuristic_severity === 'high') high += 1;
    else if (finding.heuristic_severity === 'medium') medium += 1;
  }

  return (
    <section className="holo-panel p-4 sm:p-5">
      <div className="flex flex-wrap items-center gap-2.5">
        <span aria-hidden className="relative flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-sky-400 opacity-50" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-sky-400 shadow-[0_0_8px_rgba(56,189,248,0.8)]" />
        </span>
        <h3 className="section-title">Automated scans</h3>
        <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-slate-500">
          {findings.length} rule match{findings.length === 1 ? '' : 'es'}
        </span>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {[...counts.entries()].map(([category, count]) => (
          <Badge
            key={category}
            className={CATEGORY_TONES[category] ?? 'border-slate-500/25 bg-slate-500/[0.06] text-slate-400'}
          >
            {categoryLabel(category)} &middot; {count}
          </Badge>
        ))}
        {critical > 0 && (
          <Badge className="border-rose-500/25 bg-rose-500/[0.06] text-rose-300">
            {critical} critical pattern{critical === 1 ? '' : 's'}
          </Badge>
        )}
        {high > 0 && (
          <Badge className="border-orange-400/25 bg-orange-400/[0.06] text-orange-300">
            {high} high pattern{high === 1 ? '' : 's'}
          </Badge>
        )}
        {medium > 0 && (
          <Badge className="border-amber-400/25 bg-amber-400/[0.06] text-amber-300">
            {medium} medium pattern{medium === 1 ? '' : 's'}
          </Badge>
        )}
      </div>
    </section>
  );
}