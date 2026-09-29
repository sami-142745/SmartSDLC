import { cn } from '../../lib/cn';

export type ScoreTone = 'excellent' | 'good' | 'fair' | 'poor';

export const SCORE_TONE_COLOR: Record<ScoreTone, string> = {
  excellent: '#34D399',
  good: '#A3E635',
  fair: '#FBBF24',
  poor: '#FB7185',
};

/** Map a 0-100 score to a tone using the same thresholds as the CI gates. */
export function scoreTone(score: number): ScoreTone {
  if (score >= 90) return 'excellent';
  if (score >= 75) return 'good';
  if (score >= 60) return 'fair';
  return 'poor';
}

export interface ScoreGaugeProps {
  /** 0-100. Values outside the range are clamped. */
  score: number;
  label?: string;
  size?: number;
  thickness?: number;
  className?: string;
  /** Drawn beneath the score, e.g. "/100" or a finding count. */
  caption?: string;
}

/**
 * Radial score gauge. Pure SVG so it animates smoothly and stays crisp, and so
 * the accessible value is exposed as text rather than as a bare graphic.
 */
export function ScoreGauge({
  score,
  label,
  size = 132,
  thickness = 10,
  className,
  caption,
}: ScoreGaugeProps) {
  const clamped = Math.max(0, Math.min(100, Number.isFinite(score) ? score : 0));
  const tone = scoreTone(clamped);
  const color = SCORE_TONE_COLOR[tone];
  const radius = (size - thickness) / 2;
  const circumference = 2 * Math.PI * radius;
  const filled = (clamped / 100) * circumference;
  const center = size / 2;

  return (
    <div className={cn('flex flex-col items-center gap-2', className)}>
      <div className="relative" style={{ width: size, height: size }}>
        <svg
          width={size}
          height={size}
          viewBox={`0 0 ${size} ${size}`}
          role="img"
          aria-label={`${label ? `${label}: ` : ''}${Math.round(clamped)} out of 100`}
        >
          {/* Tick marks every 10 points give the ring a sense of scale. */}
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke="rgba(255,255,255,0.06)"
            strokeWidth={thickness}
          />
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={thickness}
            strokeLinecap="round"
            strokeDasharray={`${filled} ${circumference - filled}`}
            transform={`rotate(-90 ${center} ${center})`}
            style={{
              filter: `drop-shadow(0 0 6px ${color}66)`,
              transition: 'stroke-dasharray 800ms cubic-bezier(0.16,1,0.3,1)',
            }}
          />
        </svg>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span
            className="text-3xl font-semibold tabular-nums tracking-tight"
            style={{ color }}
          >
            {Math.round(clamped)}
          </span>
          {caption ? (
            <span className="mt-0.5 text-[10px] uppercase tracking-[0.12em] text-ink-faint">
              {caption}
            </span>
          ) : null}
        </div>
      </div>
      {label ? <span className="text-[12px] font-medium text-ink-muted">{label}</span> : null}
    </div>
  );
}

/** Thin horizontal progress/meter used for sub-scores and target tracking. */
export function Meter({
  value,
  max = 100,
  color,
  className,
  label,
  showValue = false,
  height = 6,
}: {
  value: number;
  max?: number;
  color?: string;
  className?: string;
  label?: string;
  showValue?: boolean;
  height?: number;
}) {
  const percent = max > 0 ? Math.max(0, Math.min(100, (value / max) * 100)) : 0;
  const resolved = color ?? SCORE_TONE_COLOR[scoreTone(percent)];

  return (
    <div className={className}>
      {label || showValue ? (
        <div className="mb-1.5 flex items-baseline justify-between gap-3 text-[12px]">
          {label ? <span className="truncate text-ink-muted">{label}</span> : <span />}
          {showValue ? (
            <span className="shrink-0 font-mono tabular-nums text-ink-subtle">
              {Math.round(value)}
              {max !== 100 ? ` / ${max}` : ''}
            </span>
          ) : null}
        </div>
      ) : null}
      <div
        role="progressbar"
        aria-valuenow={Math.round(value)}
        aria-valuemin={0}
        aria-valuemax={max}
        aria-label={label}
        className="overflow-hidden rounded-full bg-white/[0.06]"
        style={{ height }}
      >
        <div
          className="h-full rounded-full transition-[width] duration-700 ease-swift"
          style={{
            width: `${percent}%`,
            backgroundColor: resolved,
            boxShadow: `0 0 10px -2px ${resolved}`,
          }}
        />
      </div>
    </div>
  );
}
