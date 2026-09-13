import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { CATEGORY_LABELS } from '../../utils/severity';
import type { Category } from '../../types';

interface CategoryBarChartProps {
  data: Record<string, number>;
  height?: number;
}

const COLORS: Record<string, string> = {
  Security: '#818cf8',
  Bug: '#fb7185',
  Performance: '#38bdf8',
  Complexity: '#a78bfa',
  Maintainability: '#fbbf24',
  Style: '#94a3b8',
};

const TOOLTIP_STYLE = {
  background: 'rgba(13,15,26,0.92)',
  border: '1px solid rgba(255,255,255,0.1)',
  borderRadius: 10,
  color: '#cbd5e1',
  fontSize: 12,
  boxShadow: '0 16px 40px -10px rgba(0,0,0,0.75), 0 0 0 1px rgba(99,102,241,0.12)',
  backdropFilter: 'blur(12px)',
};

export function CategoryBarChart({ data, height = 220 }: CategoryBarChartProps) {
  const bars = (Object.keys(data) as Category[])
    .map((key) => {
      const name = CATEGORY_LABELS[key] ?? key;
      return {
        name,
        count: data[key] ?? 0,
        fill: COLORS[name] ?? '#818cf8',
      };
    })
    .filter((bar) => bar.count > 0);

  if (bars.length === 0) {
    return <p className="py-8 text-center text-sm text-slate-500">No findings yet.</p>;
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={bars} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
        <defs>
          {bars.map((bar) => (
            <linearGradient key={`grad-${bar.name}`} id={`bar-grad-${bar.name}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={bar.fill} stopOpacity="0.92" />
              <stop offset="100%" stopColor={bar.fill} stopOpacity="0.45" />
            </linearGradient>
          ))}
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.07)" vertical={false} />
        <XAxis dataKey="name" tick={{ fill: '#64748b', fontSize: 11 }} tickLine={false} axisLine={{ stroke: 'rgba(148,163,184,0.1)' }} />
        <YAxis allowDecimals={false} tick={{ fill: '#64748b', fontSize: 11 }} tickLine={false} axisLine={false} />
        <Tooltip
          contentStyle={TOOLTIP_STYLE}
          cursor={{ fill: 'rgba(255,255,255,0.025)' }}
          formatter={(value) => [value, 'Findings']}
        />
        <Bar dataKey="count" name="Findings" radius={[4, 4, 0, 0]} maxBarSize={40}>
          {bars.map((bar) => (
            <Cell
              key={bar.name}
              fill={`url(#bar-grad-${bar.name})`}
              style={{ filter: `drop-shadow(0 0 8px ${bar.fill}40)` }}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}