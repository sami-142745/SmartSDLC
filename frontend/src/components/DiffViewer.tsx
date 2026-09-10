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
  meta: 'bg-slate-100 text-slate-500',
  hunk: 'bg-sky-50 text-sky-800 font-medium',
  add: 'bg-emerald-50 text-emerald-900',
  del: 'bg-red-50 text-red-900',
  context: 'text-slate-700',
};

export function DiffViewer({ diff }: { diff: string }) {
  const [collapsed, setCollapsed] = useState(false);
  const lines = tokenizeDiff(diff);

  if (!lines.length) {
    return <p className="py-8 text-center text-sm text-slate-500">No diff available.</p>;
  }

  return (
    <div className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center justify-between border-b border-slate-200 bg-slate-50 px-4 py-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          Unified diff
        </span>
        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-500">{lines.length} lines</span>
          <button
            type="button"
            onClick={() => setCollapsed((c) => !c)}
            className="rounded-md border border-slate-300 bg-white px-2 py-1 text-xs font-medium text-slate-600 shadow-sm hover:bg-slate-100"
          >
            {collapsed ? 'Expand' : 'Collapse'}
          </button>
        </div>
      </div>
      {!collapsed && (
        <div className="max-h-[560px] overflow-auto">
          <div className="min-w-max font-mono text-[13px] leading-5">
            {lines.map((line, index) => (
              <div key={index} className={`flex px-3 ${LINE_STYLES[line.type]}`}>
                <span className="w-10 shrink-0 select-none pr-3 text-right text-xs text-slate-400">
                  {index + 1}
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