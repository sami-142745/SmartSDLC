const STAGES = [
  { id: '01', label: 'Connect' },
  { id: '02', label: 'Understand' },
  { id: '03', label: 'Analyze' },
  { id: '04', label: 'Detect' },
  { id: '05', label: 'Explain' },
  { id: '06', label: 'Improve' },
  { id: '07', label: 'Ship' },
];

/**
 * Decorative but informative "journey" rail that summarizes how a review
 * flows through SmartSDLC. Real semantic list — screen-reader friendly.
 */
export function JourneyRail() {
  return (
    <nav
      aria-label="How a review flows through SmartSDLC"
      className="journey-rail relative overflow-hidden rounded-lg border border-white/[0.05] bg-surface-1/40 px-4 py-3"
    >
      <ol className="flex flex-wrap items-center gap-y-2.5">
        {STAGES.map((stage, index) => (
          <li key={stage.id} className="flex items-center">
            <span className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.16em] text-slate-500">
              <span className="text-accent-indigo/80">{stage.id}</span>
              <span className="text-slate-300">{stage.label}</span>
            </span>
            {index < STAGES.length - 1 && (
              <span
                aria-hidden
                className="ml-2.5 mr-2.5 block h-px w-7 overflow-hidden rounded-full bg-white/[0.06]"
              >
                <span className="journey-flow block h-px w-full bg-gradient-to-r from-accent-indigo/80 to-accent-violet/80" />
              </span>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}