import { useEffect, useMemo, useState } from 'react';

interface ScoreRingProps {
  value: number;
  label?: string;
  sublabel?: string;
  size?: number;
  color?: 'brand' | 'success' | 'danger';
}

function ringColor(color: ScoreRingProps['color']) {
  switch (color) {
    case 'success':
      return ['#34d399', '#6ee7b7'];
    case 'danger':
      return ['#f87171', '#fb923c'];
    default:
      return ['#6366f1', '#8b5cf6'];
  }
}

function Ticks() {
  const ticks = useMemo(() => {
    const items: React.CSSProperties[] = [];
    for (let i = 0; i < 26; i++) {
      const angle = (i / 26) * 360;
      items.push({ transform: `rotate(${angle}deg)` });
    }
    return items;
  }, []);
  return (
    <>
      {ticks.map((style, i) => (
        <span
          key={i}
          aria-hidden
          className="absolute left-1/2 top-1/2 h-full w-px"
          style={style}
        >
          <span className="absolute left-1/2 top-2 h-1.5 w-px -translate-x-1/2 bg-white/[0.08]" />
        </span>
      ))}
    </>
  );
}

export function ScoreRing({ value, label, sublabel, size = 160, color = 'brand' }: ScoreRingProps) {
  const [offset, setOffset] = useState(0);
  const clamped = Math.max(0, Math.min(100, value));
  const radius = 62;
  const circumference = 2 * Math.PI * radius;
  const [start, end] = ringColor(color);

  useEffect(() => {
    const frame = requestAnimationFrame(() => {
      setOffset(circumference * (1 - clamped / 100));
    });
    return () => cancelAnimationFrame(frame);
  }, [clamped, circumference]);

  return (
    <div
      className="relative inline-flex flex-col items-center"
      style={{ width: size, height: size }}
    >
      <svg width={size} height={size} viewBox="0 0 160 160" role="img" aria-hidden="true">
        <defs>
          <linearGradient id="score-grad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor={start} />
            <stop offset="100%" stopColor={end} />
          </linearGradient>
          <radialGradient id="score-glow" cx="50%" cy="42%" r="62%">
            <stop offset="0%" stopColor={start} stopOpacity="0.2" />
            <stop offset="100%" stopColor={start} stopOpacity="0" />
          </radialGradient>
          <radialGradient id="score-holo" cx="50%" cy="38%" r="70%">
            <stop offset="0%" stopColor={start} stopOpacity="0.1" />
            <stop offset="60%" stopColor={end} stopOpacity="0.04" />
            <stop offset="100%" stopColor={end} stopOpacity="0" />
          </radialGradient>
        </defs>

        {/* holographic background wash */}
        <circle cx="80" cy="80" r={radius + 10} fill="url(#score-glow)" />

        {/* outer track */}
        <circle
          cx="80"
          cy="80"
          r={radius + 9}
          fill="none"
          stroke="rgba(255,255,255,0.03)"
          strokeWidth="1"
        />

        {/* base ring */}
        <circle
          cx="80"
          cy="80"
          r={radius}
          fill="url(#score-holo)"
          stroke="rgba(255,255,255,0.045)"
          strokeWidth="6"
        />

        {/* progress */}
        <circle
          cx="80"
          cy="80"
          r={radius}
          fill="none"
          stroke="url(#score-grad)"
          strokeWidth="6"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          transform="rotate(-90 80 80)"
          style={{ transition: 'stroke-dashoffset 1.2s cubic-bezier(0.16,1,0.3,1)' }}
        />

        {/* inner decorative ring */}
        <circle
          cx="80"
          cy="80"
          r={radius - 14}
          fill="none"
          stroke={start}
          strokeOpacity="0.12"
          strokeWidth="1"
          strokeDasharray="2 4"
        />
      </svg>

      {/* tick marks */}
      <div className="pointer-events-none absolute inset-0">
        <Ticks />
      </div>

      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-3xl font-semibold tabular-nums tracking-tight text-slate-50">
          {Math.round(clamped)}
        </span>
        {label && (
          <span className="mt-1 text-center text-[10px] font-medium uppercase leading-tight tracking-[0.16em] text-slate-500">
            {label}
          </span>
        )}
        {sublabel && (
          <span className="mt-0.5 font-mono text-[10px] text-slate-600">{sublabel}</span>
        )}
      </div>
    </div>
  );
}