import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip, Legend } from 'recharts';

import { SEVERITY_CHART_COLORS } from '../../utils/severity';
import type { Severity } from '../../types';

interface SeverityPieChartProps {
  data: Record<string, number>;
  height?: number;
}

export function SeverityPieChart({ data, height = 260 }: SeverityPieChartProps) {
  const slices = (Object.keys(data) as Severity[])
    .filter((key) => (data[key] ?? 0) > 0)
    .map((key) => ({
      name: key.charAt(0).toUpperCase() + key.slice(1),
      value: data[key] ?? 0,
      color: SEVERITY_CHART_COLORS[key] ?? '#6b7280',
    }));

  if (slices.length === 0) {
    return <p className="py-8 text-center text-sm text-slate-500">No findings yet.</p>;
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Pie
          data={slices}
          dataKey="value"
          nameKey="name"
          cx="50%"
          cy="50%"
          outerRadius={90}
          label={({ name, value }) => `${name}: ${value}`}
        >
          {slices.map((slice) => (
            <Cell key={slice.name} fill={slice.color} />
          ))}
        </Pie>
        <Tooltip />
        <Legend />
      </PieChart>
    </ResponsiveContainer>
  );
}