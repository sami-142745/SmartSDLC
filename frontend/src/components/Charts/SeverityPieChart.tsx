import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';

import { SEVERITY_CHART_COLORS } from '../../utils/severity';
import type { Severity } from '../../types';

interface SeverityPieChartProps {
  data: Record<string, number>;
  height?: number;
}

const TOOLTIP_STYLE = {
  background: 'rgba(13,15,26,0.92)',
  border: '1px solid rgba(255,255,255,0.1)',
  borderRadius: 10,
  color: '#cbd5e1',
  fontSize: 12,
  boxShadow: '0 16px 40px -10px rgba(0,0,0,0.75), 0 0 0 1px rgba(99,102,241,0.12)',
  backdropFilter: 'blur(12px)',
};

export function SeverityPieChart({ data, height = 220 }: SeverityPieChartProps) {
  const slices = (Object.keys(data) as Severity[])
    .filter((key) => (data[key] ?? 0) > 0)
    .map((key) => ({
      name: key.charAt(0).toUpperCase() + key.slice(1),
      value: data[key] ?? 0,
      color: SEVERITY_CHART_COLORS[key] ?? '#94a3b8',
    }));

  if (slices.length === 0) {
    return <p className="py-8 text-center text-sm text-slate-500">No findings yet.</p>;
  }

  return (
    <div className="relative">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 rounded-full bg-[radial-gradient(closest-side,rgba(99,102,241,0.07),transparent_72%)]"
      />
      <ResponsiveContainer width="100%" height={height}>
        <PieChart>
          <defs>
            {slices.map((slice) => (
              <radialGradient key={`glow-${slice.name}`} id={`pie-glow-${slice.name}`} cx="50%" cy="42%" r="70%">
                <stop offset="0%" stopColor={slice.color} stopOpacity="0.16" />
                <stop offset="100%" stopColor={slice.color} stopOpacity="0" />
              </radialGradient>
            ))}
          </defs>
          <Pie
            data={slices}
            dataKey="value"
            nameKey="name"
            cx="50%"
            cy="50%"
            innerRadius={58}
            outerRadius={86}
            paddingAngle={2.5}
            stroke="rgba(8,9,18,0.9)"
            strokeWidth={2}
          >
            {slices.map((slice, index) => (
              <Cell
                key={slice.name}
                fill={slice.color}
                style={{ filter: `drop-shadow(0 0 6px ${slice.color}44)` }}
              />
            ))}
          </Pie>
          <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(value) => [value, 'Findings']} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}