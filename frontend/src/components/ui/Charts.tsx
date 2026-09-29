import { useId } from 'react';
import type { ReactNode } from 'react';

import { cn } from '../../lib/cn';

export interface DonutSegment {
  key: string;
  label: string;
  value: number;
  color: string;
}

export interface DonutProps {
  segments: DonutSegment[];
  size?: number;
  thickness?: number;
  /** Rendered in the middle of the ring. */
  centerLabel?: ReactNode;
  centerValue?: ReactNode;
  className?: string;
  /** Show a legend beside the ring. */
  legend?: boolean;
}

/**
 * Pure-SVG donut chart. Avoids a charting-library dependency for the single
 * most common visual in the product, and stays crisp at any size.
 */
export function Donut({
  segments,
  size = 168,
  thickness = 14,
  centerLabel,
  centerValue,
  className,
  legend = true,
}: DonutProps) {
  const gradientId = useId();
  const total = segments.reduce((sum, segment) => sum + segment.value, 0);
  const radius = (size - thickness) / 2;
  const circumference = 2 * Math.PI * radius;
  const center = size / 2;

  let offset = 0;
  const arcs = segments.map((segment) => {
    const fraction = total > 0 ? segment.value / total : 0;
    const length = fraction * circumference;
    const arc = {
      ...segment,
      dash: `${length} ${circumference - length}`,
      offset: -offset,
      percent: fraction,
    };
    offset += length;
    return arc;
  });

  return (
    <div className={cn('flex flex-wrap items-center gap-6', className)}>
      <div className="relative shrink-0" style={{ width: size, height: size }}>
        <svg
          width={size}
          height={size}
          viewBox={`0 0 ${size} ${size}`}
          role="img"
          aria-label={`Distribution: ${segments
            .filter((segment) => segment.value > 0)
            .map((segment) => `${segment.label} ${segment.value}`)
            .join(', ')}`}
        >
          <defs>
            {arcs.map((arc) => (
              <linearGradient
                key={arc.key}
                id={`${gradientId}-${arc.key}`}
                x1="0%"
                y1="0%"
                x2="100%"
                y2="100%"
              >
                <stop offset="0%" stopColor={arc.color} stopOpacity="0.75" />
                <stop offset="100%" stopColor={arc.color} stopOpacity="1" />
              </linearGradient>
            ))}
          </defs>
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke="rgba(255,255,255,0.05)"
            strokeWidth={thickness}
          />
          {arcs.map((arc) =>
            arc.value > 0 ? (
              <circle
                key={arc.key}
                cx={center}
                cy={center}
                r={radius}
                fill="none"
                stroke={`url(#${gradientId}-${arc.key})`}
                strokeWidth={thickness}
                strokeDasharray={arc.dash}
                strokeDashoffset={arc.offset}
                strokeLinecap="butt"
                transform={`rotate(-90 ${center} ${center})`}
                className="transition-[stroke-dasharray,stroke-dashoffset] duration-700 ease-swift"
              />
            ) : null,
          )}
        </svg>
        {(centerValue || centerLabel) && (
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">
            {centerValue ? (
              <span className="text-2xl font-semibold tabular-nums tracking-tight text-ink">
                {centerValue}
              </span>
            ) : null}
            {centerLabel ? (
              <span className="mt-0.5 text-[10px] uppercase tracking-[0.14em] text-ink-faint">
                {centerLabel}
              </span>
            ) : null}
          </div>
        )}
      </div>

      {legend ? (
        <ul className="min-w-[8rem] flex-1 space-y-1.5">
          {arcs.map((arc) => (
            <li key={arc.key} className="flex items-center gap-2.5 text-[12px]">
              <span
                aria-hidden
                className="h-2 w-2 shrink-0 rounded-[3px]"
                style={{ backgroundColor: arc.color, boxShadow: `0 0 8px -1px ${arc.color}` }}
              />
              <span className="min-w-0 flex-1 truncate text-ink-muted">{arc.label}</span>
              <span className="shrink-0 font-mono tabular-nums text-ink-subtle">{arc.value}</span>
              <span className="w-10 shrink-0 text-right font-mono tabular-nums text-ink-faint">
                {Math.round(arc.percent * 100)}%
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

export interface BarDatum {
  key: string;
  label: string;
  value: number;
  color?: string;
}

/** Horizontal bar list — used for category distributions and top-N rankings. */
export function BarList({
  data,
  max,
  className,
  showValues = true,
  unit,
}: {
  data: BarDatum[];
  max?: number;
  className?: string;
  showValues?: boolean;
  /** Appended to each value, e.g. "findings", so counts read as quantities. */
  unit?: string;
}) {
  const peak = max ?? Math.max(...data.map((datum) => datum.value), 1);
  return (
    <ul className={cn('space-y-2.5', className)}>
      {data.map((datum) => {
        const percent = peak > 0 ? (datum.value / peak) * 100 : 0;
        return (
          <li key={datum.key} className="group">
            <div className="flex items-baseline justify-between gap-3 text-[12px]">
              <span className="min-w-0 truncate text-ink-muted">{datum.label}</span>
              {showValues ? (
                <span className="shrink-0 font-mono tabular-nums text-ink-subtle">
                  {unit ? `${datum.value} ${unit}` : datum.value}
                </span>
              ) : null}
            </div>
            <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-white/[0.05]">
              <div
                className="h-full rounded-full transition-[width] duration-700 ease-swift"
                style={{
                  width: `${Math.max(percent, datum.value > 0 ? 2 : 0)}%`,
                  backgroundColor: datum.color ?? '#8B5CF6',
                  boxShadow: `0 0 10px -2px ${datum.color ?? '#8B5CF6'}`,
                }}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}

export interface SparkPoint {
  label: string;
  value: number;
}

/** Minimal inline trend line for stat cards. */
export function Sparkline({
  points,
  color = '#8B5CF6',
  height = 34,
  className,
}: {
  points: SparkPoint[];
  color?: string;
  height?: number;
  className?: string;
}) {
  if (points.length < 2) return null;
  const width = 120;
  const values = points.map((point) => point.value);
  const max = Math.max(...values);
  const min = Math.min(...values);
  const range = max - min || 1;

  const coords = points.map((point, index) => {
    const x = (index / (points.length - 1)) * width;
    const y = height - ((point.value - min) / range) * (height - 6) - 3;
    return { x, y };
  });

  const line = coords.map((c, i) => `${i === 0 ? 'M' : 'L'}${c.x.toFixed(1)},${c.y.toFixed(1)}`).join(' ');
  const area = `${line} L${width},${height} L0,${height} Z`;

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      className={cn('overflow-visible', className)}
      aria-hidden="true"
    >
      <defs>
        <linearGradient id={`spark-${color.replace('#', '')}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.28" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#spark-${color.replace('#', '')})`} />
      <path
        d={line}
        fill="none"
        stroke={color}
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx={coords[coords.length - 1].x} cy={coords[coords.length - 1].y} r="2.5" fill={color} />
    </svg>
  );
}
