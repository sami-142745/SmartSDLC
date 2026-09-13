import { Link } from 'react-router-dom';

import { CinematicBackdrop } from '../components/CinematicBackdrop';
import { AmbientParticles } from '../components/motion/AmbientParticles';
import { NetworkGraph } from '../components/motion/NetworkGraph';
import { Parallax } from '../components/motion/Parallax';

export function NotFoundPage() {
  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-surface-0 px-4 text-center text-slate-200">
      <CinematicBackdrop variant="aura" className="opacity-40" />
      <Parallax depth={1.3} className="pointer-events-none absolute inset-0">
        <div
          aria-hidden
          className="absolute inset-x-0 bottom-0 h-[44%] opacity-35 [mask-image:radial-gradient(70%_100%_at_50%_100%,black,transparent_80%)]"
        >
          <NetworkGraph className="h-full w-full" />
        </div>
        <AmbientParticles count={24} maxAlpha={0.3} color="#a5b4fc" className="absolute inset-0 h-full w-full" />
      </Parallax>

      {/* massive rotating portal */}
      <div aria-hidden className="pointer-events-none absolute inset-0 flex items-center justify-center">
        <div className="portal h-[560px] w-[560px] sm:h-[660px] sm:w-[660px]">
          <div className="portal-ring" />
          <div className="portal-ring-2" />
          <div className="portal-ring-3" />
          <div className="portal-core" />
          <div className="portal-distort" />
        </div>
      </div>

      {/* orbiting system telemetry */}
      <div aria-hidden className="orbit-labels pointer-events-none absolute inset-0 hidden md:block">
        <div className="orbital-meter absolute left-[16%] top-[22%]">
          <div className="holo-panel px-3 py-1.5">
            <p className="hud-tag">Route undefined</p>
          </div>
        </div>
        <div className="orbital-meter absolute bottom-[20%] right-[14%]">
          <div className="holo-panel px-3 py-1.5">
            <p className="hud-tag">No signal on this vector</p>
          </div>
        </div>
      </div>

      <div className="relative z-10 flex flex-col items-center">
        <p className="hud-tag hud-tag-accent flex items-center gap-2">
          <span aria-hidden className="h-1 w-8 bg-indigo-400/50" />
          Lost in the review queue
          <span aria-hidden className="h-1 w-8 bg-indigo-400/50" />
        </p>
        <h1 className="hero-display mt-4 text-slate-50">
          <span className="h-grad block">404</span>
        </h1>
        <p className="mt-3 text-slate-400">That page does not exist.</p>
        <Link to="/dashboard" className="btn-primary mt-8">
          Back to dashboard
        </Link>
      </div>
    </div>
  );
}