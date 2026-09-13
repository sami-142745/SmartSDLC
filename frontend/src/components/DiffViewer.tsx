import { useState } from 'react';

type DiffLineType = 'meta' | 'hunk' | 'add' | 'del' | 'context';

interface DiffLine {
  type: DiffLineType;
  content: string;
}

function tokenizeDiff(diff: string): DiffLine[] {
  return diff.split('\n').map((line) => {
    if (line.startsWith('@@')) return { type: 'hunk', content: line };
    if (line.startsWith('+') && !line.startsWith('+++')) return { type: 'add', content: line };
    if (line.startsWith('-') && !line.startsWith('---')) return { type: 'del', content: line };
    if (line.startsWith('diff ') || line.startsWith('index ') || line.startsWith('---') || line.startsWith('+++')) {
      return { type: 'meta', content: line };
    }
    return { type: 'context', content: line };
  });
}

const LINE_STYLES: Record<DiffLineType, string> = {
  meta: 'bg-transparent text-slate-600',
  hunk: 'bg-accent-indigo/[0.06] text-accent-indigo font-medium',
  add: 'bg-emerald-500/[0.06] text-emerald-300',
  del: 'bg-rose-500/[0.06] text-rose-300',
  context: 'text-slate-400',
};

const GUTTER: Record<DiffLineType, string> = {
  meta: '',
  hunk: '',
  add: '+',
  del: '-',
  context: ' ',
};

export function DiffViewer({ diff }: { diff: string }) {
  const [collapsed, setCollapsed] = useState(false);
  const lines = tokenizeDiff(diff);

  if (!lines.length) {
    return <p className="py-8 text-center text-sm text-slate-500">No diff available.</p>;
  }

  return (
    <div className="overflow-hidden border border-white/[0.06] bg-surface-0">
      <div className="flex items-center justify-between border-b border-white/[0.06] bg-surface-2/50 px-4 py-2.5">
        <span className="font-mono text-xs text-slate-400">unified diff</span>
        <div className="flex items-center gap-3">
          <span className="font-mono text-xs tabular-nums text-slate-600">{lines.length} lines</span>
          <button
            type="button"
            onClick={() => setCollapsed((c) => !c)}
            className="btn-secondary px-2.5 py-1 text-xs"
          >
            {collapsed ? 'Expand' : 'Collapse'}
          </button>
        </div>
      </div>
      {!collapsed && (
        <div className="max-h-[560px] overflow-auto">
          <div className="min-w-max font-mono text-[13px] leading-5">
            {lines.map((line, index) => (
              <div key={index} className={`flex ${LINE_STYLES[line.type]}`}>
                <span className="w-10 shrink-0 select-none pr-3 text-right text-xs text-slate-600">
                  {index + 1}
                </span>
                <span
                  className={`w-5 shrink-0 select-none pr-3 text-right ${
                    line.type === 'add'
                      ? 'text-emerald-400/60'
                      : line.type === 'del'
                        ? 'text-rose-400/60'
                        : 'text-transparent'
                  }`}
                >
                  {GUTTER[line.type]}
                </span>
                <span className="whitespace-pre-wrap break-all">{line.content || ' '}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
