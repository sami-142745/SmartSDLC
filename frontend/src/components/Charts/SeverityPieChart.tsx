import { SEVERITY_CHART_COLORS } from '../../utils/severity';
import type { Severity } from '../../types';
import { Donut } from '../ui/Charts';
import type { DonutSegment } from '../ui/Charts';

interface SeverityPieChartProps {
  data: Record<string, number>;
  /** Kept for API compatibility; the donut scales with its container. */
  height?: number;
}

function humanize(key: string): string {
  return key.charAt(0).toUpperCase() + key.slice(1);
}

/**
 * Severity distribution as a donut. Replaces the previous Recharts pie: same
 * data, a fraction of the bundle cost, and colours that match the rest of the
 * product instead of a generic chart theme.
 */
export function SeverityPieChart({ data }: SeverityPieChartProps) {
  const segments: DonutSegment[] = (Object.keys(data) as Severity[])
    .filter((key) => (data[key] ?? 0) > 0)
    .map((key) => ({
      key,
      label: humanize(key),
      value: data[key] ?? 0,
      color: SEVERITY_CHART_COLORS[key] ?? '#71717a',
    }));

  if (segments.length === 0) {
    return <p className="py-8 text-center text-[13px] text-ink-faint">No findings yet.</p>;
  }

  // No centre total here: the dashboard already shows the grand total in a
  // metric card, and repeating it would be redundant.
  return (
    <Donut
      segments={segments}
      size={148}
      thickness={13}
      className="justify-center"
    />
  );
}
