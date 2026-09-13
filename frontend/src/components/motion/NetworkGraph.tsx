import { useMotionControl } from '../../hooks/useMotionControl';

interface GraphNode {
  id: string;
  x: number;
  y: number;
  color: string;
}

const NODES: GraphNode[] = [
  { id: 'AI', x: 84, y: 86, color: '#a78bfa' },
  { id: 'CODE', x: 128, y: 248, color: '#38bdf8' },
  { id: 'SECURITY', x: 348, y: 74, color: '#f87171' },
  { id: 'PR', x: 404, y: 250, color: '#fbbf24' },
  { id: 'REVIEW', x: 250, y: 158, color: '#818cf8' },
];

interface NetworkGraphProps {
  className?: string;
}

/**
 * Decorative AI network — the REVIEW hub connected to AI, CODE, SECURITY
 * and PR nodes with thin lines and small pulses traveling along them.
 * Pure SVG; pulses use SMIL and are rendered only when continuous motion
 * is allowed (no reduced-motion, fine pointer). Very low opacity, always
 * behind interactive content.
 */
export function NetworkGraph({ className = '' }: NetworkGraphProps) {
  const { animate } = useMotionControl();
  const hub = NODES[NODES.length - 1];
  const links = NODES.slice(0, -1).map((node) => {
    const d = `M ${hub.x} ${hub.y} L ${node.x} ${node.y}`;
    return { node, d };
  });

  return (
    <svg viewBox="0 0 480 320" preserveAspectRatio="xMidYMid meet" className={`network-svg ${className}`} aria-hidden>
      <defs>
        <radialGradient id="network-core" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="rgba(129,140,248,0.28)" />
          <stop offset="100%" stopColor="rgba(129,140,248,0)" />
        </radialGradient>
      </defs>

      <circle cx={hub.x} cy={hub.y} r="74" fill="url(#network-core)" />

      {links.map(({ node, d }) => (
        <g key={node.id}>
          <path d={d} stroke="rgba(103,116,241,0.22)" strokeWidth="1" fill="none" />
          {animate && (
            <>
              <circle r="2" fill="#a5b4fc" opacity="0.9">
                <animateMotion dur="6s" repeatCount="indefinite" path={d} />
              </circle>
              <circle r="1.4" fill="#c7d2fe" opacity="0.7">
                <animateMotion dur="9s" begin="1.8s" repeatCount="indefinite" path={d} />
              </circle>
            </>
          )}
        </g>
      ))}

      {NODES.map((node) => (
        <g key={node.id}>
          <circle cx={node.x} cy={node.y} r="9" fill={node.color} opacity="0.1" />
          <circle cx={node.x} cy={node.y} r="3" fill={node.color} opacity="0.85" />
          <text
            x={node.x}
            y={node.y - 10}
            fill="rgba(148,163,184,0.55)"
            fontSize="9"
            textAnchor="middle"
            fontFamily="ui-monospace, SFMono-Regular, Menlo, monospace"
          >
            {node.id}
          </text>
        </g>
      ))}
    </svg>
  );
}