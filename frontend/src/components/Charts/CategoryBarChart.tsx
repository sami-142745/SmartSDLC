import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
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

const COLORS = ['#6366f1', '#0ea5e9', '#f59e0b', '#10b981', '#f43f5e', '#8b5cf6'];

export function CategoryBarChart({ data, height = 260 }: CategoryBarChartProps) {
  const bars = (Object.keys(data) as Category[])
    .map((key, index) => ({
      name: CATEGORY_LABELS[key] ?? key,
      count: data[key] ?? 0,
      fill: COLORS[index % COLORS.length],
    }))
    .filter((bar) => bar.count > 0);

  if (bars.length === 0) {
    return <p className="py-8 text-center text-sm text-slate-500">No findings yet.</p>;
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={bars} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis dataKey="name" tick={{ fontSize: 12 }} />
        <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
        <Tooltip />
        <Legend />
        <Bar dataKey="count" name="Findings" radius={[4, 4, 0, 0]}>
          {bars.map((bar) => (
            <Cell key={bar.name} fill={bar.fill} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}