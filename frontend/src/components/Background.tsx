/**
 * Cinematic ambient backdrop — "futuristic AI command center" feel.
 * Deep navy base, large atmospheric orbs, faint technical grid, a soft
 * starfield, drifting light particles, and a gentle center glow.
 *
 * Pure decoration: aria-hidden, pointer-events-none, reduced-motion safe.
 */

interface Star {
  left: string;
  top: string;
  size: number;
  opacity: number;
  duration: number;
  delay: number;
  glow: boolean;
}

function mulberry32(seed: number) {
  let a = seed;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const STARS: Star[] = (() => {
  const rnd = mulberry32(20260910);
  return Array.from({ length: 56 }, (_, i) => ({
    left: `${Math.round(rnd() * 98)}%`,
    top: `${Math.round(rnd() * 92)}%`,
    size: rnd() > 0.82 ? 2.4 : rnd() > 0.5 ? 1.6 : 1,
    opacity: 0.2 + rnd() * 0.4,
    duration: 4 + rnd() * 7,
    delay: rnd() * 6,
    glow: i % 9 === 0,
  }));
})();

const PARTICLES = [
  { left: '7%', top: '24%', size: 3, opacity: 0.5, duration: 22, delay: 0 },
  { left: '18%', top: '70%', size: 4, opacity: 0.38, duration: 28, delay: 2 },
  { left: '44%', top: '12%', size: 2, opacity: 0.42, duration: 20, delay: 1.5 },
  { left: '63%', top: '38%', size: 3, opacity: 0.4, duration: 30, delay: 3.5 },
  { left: '82%', top: '14%', size: 2, opacity: 0.5, duration: 24, delay: 0.8 },
  { left: '91%', top: '68%', size: 4, opacity: 0.34, duration: 26, delay: 4.5 },
  { left: '36%', top: '86%', size: 2, opacity: 0.36, duration: 25, delay: 5.5 },
];

export function AppBackground() {
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
      <div className="bg-tech-grid absolute inset-0 [background-size:44px_44px]" />
      <div className="bg-orb bg-orb-indigo" />
      <div className="bg-orb bg-orb-blue" />
      <div className="bg-orb bg-orb-violet" />
      <div className="bg-center-glow" />
      {STARS.map((s, i) => (
        <span
          key={i}
          className="bg-star"
          style={
            {
              left: s.left,
              top: s.top,
              width: s.size,
              height: s.size,
              boxShadow: s.glow ? '0 0 6px 1px rgba(99,102,241,0.35)' : 'none',
              '--star-o': s.opacity,
              '--star-dur': `${s.duration}s`,
              '--star-delay': `${s.delay}s`,
            } as React.CSSProperties
          }
        />
      ))}
      {PARTICLES.map((p) => (
        <span
          key={`${p.left}-${p.top}`}
          className="bg-particle"
          style={{
            left: p.left,
            top: p.top,
            width: p.size,
            height: p.size,
            opacity: p.opacity,
            animationDuration: `${p.duration}s`,
            animationDelay: `${p.delay}s`,
          }}
        />
      ))}
    </div>
  );
}