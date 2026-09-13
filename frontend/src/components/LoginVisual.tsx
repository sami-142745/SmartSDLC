/**
 * Cinematic login decoration — a futuristic "digital landscape":
 * a curved planetary horizon with a receding tech grid, plus floating
 * translucent code / AI review panels. Pure CSS/SVG, aria-hidden,
 * pointer-events-none, reduced-motion safe, hidden on small screens.
 */
export function LoginVisual() {
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 hidden overflow-hidden md:block">
      {/* Planetary horizon */}
      <div className="bg-horizon">
        <div className="bg-horizon-grid" />
        <div className="bg-horizon-arc" />
        <div className="bg-horizon-glow" />
        <div className="bg-horizon-light" />
      </div>

      {/* Aurora accent above the horizon */}
      <div className="absolute bottom-[16%] left-1/2 h-[300px] w-[760px] max-w-full -translate-x-1/2 rounded-full bg-accent-violet/[0.05] blur-[110px]" />

      {/* Left: secure code panel */}
      <FloatingPanel
        className="float-panel-tilt-left left-[5%] top-[19%] w-[240px]"
        delay="0s"
      >
        <PanelBar />
        <pre className="dir-ltr font-mono text-[11px] leading-relaxed">
          <span className="text-violet-400">def</span>{' '}
          <span className="text-sky-300">secure_code</span>
          <span className="text-slate-500">():</span>
          {'\n'}
          <span className="pl-4 text-slate-600">&#x2502;</span>{' '}
          <span className="text-violet-400">return</span>{' '}
          <span className="text-emerald-300/90">safer</span>
        </pre>
      </FloatingPanel>

      {/* Left: pull request stats panel */}
      <FloatingPanel
        className="float-panel-tilt-left left-[8%] bottom-[19%] w-[212px]"
        delay="3.2s"
        style={{ animationDelay: '3.2s' }}
      >
        <PanelBar />
        <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-slate-500">
          # Pull Request
        </p>
        <div className="mt-2 flex items-baseline gap-3 font-mono text-sm">
          <span className="text-emerald-400">+124</span>
          <span className="text-rose-400">&#x2212;18</span>
        </div>
      </FloatingPanel>

      {/* Right: AI review complete panel */}
      <FloatingPanel
        className="float-panel-tilt-right right-[5%] top-[17%] w-[232px]"
        delay="1.6s"
        style={{ animationDelay: '1.6s' }}
      >
        <div className="flex items-center justify-between">
          <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-indigo-300">
            AI Review Complete
          </p>
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.7)]" />
        </div>
        <ul className="mt-3 space-y-1.5 font-mono text-[11px]">
          <ResultRow label="Critical" count={3} color="#f87171" />
          <ResultRow label="High" count={2} color="#fb923c" />
          <ResultRow label="Medium" count={1} color="#fbbf24" />
          <ResultRow label="Low" count={4} color="#38bdf8" />
        </ul>
      </FloatingPanel>

      {/* Right: promise panel */}
      <FloatingPanel
        className="float-panel-tilt-right right-[9%] bottom-[18%] w-[188px]"
        delay="4.6s"
        style={{ animationDelay: '4.6s' }}
      >
        <ul className="space-y-2 font-mono text-xs">
          <PromiseRow label="Safer" />
          <PromiseRow label="Faster" />
          <PromiseRow label="Stronger" accent />
        </ul>
      </FloatingPanel>
    </div>
  );
}

function FloatingPanel({
  children,
  className = '',
  style,
  delay,
}: {
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
  delay?: string;
}) {
  return (
    <div
      className={`float-panel ${className}`}
      style={{ animationDelay: delay, ...style }}
    >
      {children}
    </div>
  );
}

function PanelBar() {
  return (
    <div className="mb-3 flex items-center gap-1.5">
      <span className="h-1.5 w-1.5 rounded-full bg-white/[0.14]" />
      <span className="h-1.5 w-1.5 rounded-full bg-white/[0.1]" />
      <span className="h-1.5 w-1.5 rounded-full bg-indigo-400/50" />
    </div>
  );
}

function ResultRow({ label, count, color }: { label: string; count: number; color: string }) {
  return (
    <li className="flex items-center justify-between">
      <span className="flex items-center gap-2 text-slate-400">
        <span className="h-1.5 w-1.5 rounded-full" style={{ background: color, boxShadow: `0 0 6px ${color}` }} />
        {label}
      </span>
      <span className="text-slate-500">{count}</span>
    </li>
  );
}

function PromiseRow({ label, accent = false }: { label: string; accent?: boolean }) {
  return (
    <li className="flex items-center gap-2">
      <span className={accent ? 'text-emerald-400' : 'text-slate-500'}>&#x2713;</span>
      <span className={accent ? 'text-emerald-300/90' : 'text-slate-400'}>{label}</span>
    </li>
  );
}