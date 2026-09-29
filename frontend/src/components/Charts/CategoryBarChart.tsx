import { CATEGORY_LABELS } from '../../utils/severity';
import type { Category } from '../../types';
import { BarList } from '../ui/Charts';
import type { BarDatum } from '../ui/Charts';

interface CategoryBarChartProps {
  data: Record<string, number>;
  /** Kept for API compatibility. */
  height?: number;
}

const COLORS: Record<string, string> = {
  Security: '#fb7185',
  Bug: '#fbbf24',
  Performance: '#22d3ee',
  Complexity: '#a78bfa',
  Maintainability: '#34d399',
  Style: '#a1a1aa',
};

/**
 * Finding counts per category. A labelled bar list communicates the same
 * ranking as a column chart while staying legible at narrow widths and
 * screen-reader friendly (each row is a real list item with a value).
 */
export function CategoryBarChart({ data }: CategoryBarChartProps) {
  const bars: BarDatum[] = (Object.keys(data) as Category[])
    .map((key) => {
      const name = CATEGORY_LABELS[key] ?? key;
      return {
        key,
        label: name,
        value: data[key] ?? 0,
        color: COLORS[name] ?? '#8B5CF6',
      };
    })
    .filter((bar) => bar.value > 0)
    .sort((a, b) => b.value - a.value);

  if (bars.length === 0) {
    return <p className="py-8 text-center text-[13px] text-ink-faint">No findings yet.</p>;
  }

  return <BarList data={bars} unit="findings" />;
}
