import type { CSSProperties } from 'react';

interface ReviewPipelineProps {
  geminiFindings: number;
  heuristicFindings: number;
}

/**
 * Decorative AI review pipeline: shows how findings are produced, as a
 * subtle connected-node visual (Gemini AI => ANALYSIS => FINDINGS and
 * Heuristic => RULE ENGINE => FINDINGS). Purely illustrative — processing
 * is unchanged. Reduced-motion safe (pulses are CSS-animated and are
 * frozen by the global reduced-motion overrides).
 */
export function ReviewPipeline({ geminiFindings, heuristicFindings }: ReviewPipelineProps) {
  const flows = [
    {
      title: 'Gemini AI',
      color: '#a78bfa',
      text: 'text-violet-300',
      chain: ['ANALYSIS', 'FINDINGS'],
      count: geminiFindings,
    },
    {
      title: 'Heuristic',
      color: '#38bdf8',
      text: 'text-sky-300',
      chain: ['RULE ENGINE', 'FINDINGS'],
      count: heuristicFindings,
    },
  ];

  return (
    <div className="reveal is-revealed relative overflow-hidden rounded-lg border border-white/[0.06] bg-surface-1/70">
      <span
        aria-hidden
        className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-accent-indigo/40 to-transparent"
      />
      <div className="grid grid-cols-1 divide-y divide-white/[0.05] md:grid-cols-2 md:divide-x md:divide-y-0">
        {flows.map((flow) => (
          <div key={flow.title} className="relative px-5 py-4">
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2 font-mono text-[10px] font-semibold uppercase tracking-[0.18em]">
                <span
                  aria-hidden
                  className="h-1.5 w-1.5 rounded-full"
                  style={{ background: flow.color, boxShadow: `0 0 8px ${flow.color}` }}
                />
                <span className={flow.text}>{flow.title}</span>
              </span>
              <span className="font-mono text-xs tabular-nums text-slate-500">
                {flow.count} findings
              </span>
            </div>

            <div className="relative mt-3 space-y-3">
              <span
                aria-hidden
                className="absolute bottom-2 left-[4px] top-2 w-px"
                style={{
                  background: `linear-gradient(to bottom, ${flow.color}99, ${flow.color}1a)`,
                }}
              />
              <span
                aria-hidden
                className="pipeline-pulse"
                style={
                  {
                    '--pf-dur': '2.9s',
                    '--pf-dist': '72px',
                    background: flow.color,
                    boxShadow: `0 0 8px ${flow.color}`,
                  } as CSSProperties
                }
              />
              <span
                aria-hidden
                className="pipeline-pulse"
                style={
                  {
                    '--pf-dur': '2.9s',
                    '--pf-dist': '72px',
                    animationDelay: '-1.45s',
                    background: flow.color,
                    boxShadow: `0 0 8px ${flow.color}`,
                  } as CSSProperties
                }
              />

              {flow.chain.map((step, index) => {
                const isLast = index === flow.chain.length - 1;
                return (
                  <div key={step} className="flex items-center gap-2.5">
                    <span
                      aria-hidden
                      className="h-[5px] w-[5px] rounded-full"
                      style={{ background: flow.color, opacity: 0.55 }}
                    />
                    <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-slate-500">
                      {step}
                    </span>
                    {isLast && (
                      <span className="rounded-full border border-white/[0.08] bg-white/[0.03] px-1.5 py-px text-[10px] tabular-nums text-slate-400">
                        {flow.count}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}