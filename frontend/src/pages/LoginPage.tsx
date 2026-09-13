import { Link, Navigate, useLocation } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import { getLoginUrl } from '../api/auth';
import { CinematicBackdrop } from '../components/CinematicBackdrop';
import { CodeLogo } from '../components/CodeLogo';
import { CinematicButton } from '../components/ui/CinematicButton';

const SYSTEM_STATUS = [
  { label: 'SYSTEM READY', tone: 'text-emerald-300', dot: 'bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.9)]' },
  { label: 'AI ENGINE ONLINE', tone: 'text-indigo-300', dot: 'bg-indigo-400 shadow-[0_0_10px_rgba(129,140,248,0.9)]' },
  {
    label: 'SECURITY ANALYSIS ACTIVE',
    tone: 'text-cyan-300',
    dot: 'bg-cyan-400 shadow-[0_0_10px_rgba(34,211,238,0.9)]',
  },
];

const BRAND_ROWS = [
  { label: 'GitHub', icon: 'M12 0C5.37 0 0 5.37 0 12c0 5.3 3.44 9.8 8.21 11.39.6.11.82-.26.82-.58v-2.03c-3.34.73-4.04-1.61-4.04-1.61-.55-1.39-1.34-1.76-1.34-1.76-1.09-.74.08-.73.08-.73 1.2.09 1.84 1.24 1.84 1.24 1.07 1.83 2.81 1.3 3.5 1 .1-.78.42-1.31.76-1.61-2.67-.3-5.47-1.34-5.47-5.95 0-1.31.47-2.39 1.24-3.23-.13-.3-.54-1.52.11-3.18 0 0 1.01-.32 3.3 1.23a11.5 11.5 0 0 1 6.01 0c2.29-1.55 3.29-1.23 3.29-1.23.65 1.66.24 2.88.12 3.18.77.84 1.24 1.92 1.24 3.23 0 4.62-2.8 5.64-5.48 5.94.43.37.81 1.1.81 2.22v3.29c0 .32.22.7.82.58A12 12 0 0 0 24 12c0-6.63-5.37-12-12-12Z' },
  { label: 'Gemini AI', icon: 'M12 2c1 3 4 5 6.5 6.5C16 10 13 12 12 15c-1-3-4-5-6.5-6.5C8 7 11 5 12 2Z' },
  { label: 'Security', icon: 'M12 2 4 5.5v5.2c0 4.8 3.4 9.3 8 10.3 4.6-1 8-5.5 8-10.3V5.5L12 2Zm-1 6h2v6h-2V8Z' },
  { label: 'Better Code', icon: 'M13 3 4 14h6l-1 7 9-11h-6l1-7Z' },
];

/**
 * Login — cinematic entry. Left: oversized editorial type over a dark
 * gradient; right: the giant 3D AI security core (orbit camera). A floating
 * control panel hosts the GitHub authorization CTA.
 */
export function LoginPage() {
  const { token, initialized } = useAuth();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from;

  if (initialized && token) {
    return <Navigate to={from ?? '/dashboard'} replace />;
  }

  return (
    <div className="relative flex min-h-screen flex-col overflow-hidden bg-[#02030A] text-slate-200">
      {/* Full-bleed 3D AI security core — camera orbits */}
      <div aria-hidden className="fixed inset-0">
        <CinematicBackdrop variant="core" />
      </div>

      {/* Cinematic split overlay: dark zone for type (left / bottom on mobile) */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-gradient-to-r from-[#02030A] via-[#04060f]/80 to-transparent lg:via-[#03050b]/55"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-gradient-to-b from-[#02030A]/70 via-transparent to-[#02030A] lg:from-[#02030A] lg:via-transparent lg:to-transparent"
      />
      <div aria-hidden className="pointer-events-none absolute inset-0 bg-tech-grid [background-size:56px_56px] opacity-60 [mask-image:linear-gradient(90deg,black,transparent_70%)]" />

      {/* Header */}
      <header className="relative z-20 mx-auto flex w-full max-w-[1400px] items-center justify-between gap-4 px-6 pb-2 pt-8 lg:px-12">
        <div className="flex items-center gap-3 hero-enter stagger-1">
          <CodeLogo className="h-10 w-10 text-sm" showWordmark={false} />
          <div className="leading-tight">
            <p className="font-mono text-[10px] font-bold uppercase tracking-[0.26em] text-slate-100">
              SmartSDLC
            </p>
            <p className="mt-0.5 hidden font-mono text-[9px] uppercase tracking-[0.2em] text-slate-500 sm:block">
              AI security operating system
            </p>
          </div>
        </div>

        <div className="hero-enter stagger-2 flex items-center gap-2">
          <span className="relative flex h-2 w-2" aria-hidden>
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]" />
          </span>
          <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-slate-300">
            System · Online
          </span>
        </div>
      </header>

      {/* Main split */}
      <main className="relative z-10 mx-auto grid w-full max-w-[1400px] flex-1 grid-cols-1 items-end gap-4 px-6 pb-6 pt-14 lg:grid-cols-2 lg:items-center lg:px-12 lg:pb-10">
        {/* Editorial type + control panel */}
        <div className="flex flex-col">
          <p className="hero-enter stagger-1 mb-6 flex items-center gap-3 font-mono text-[10px] font-semibold uppercase tracking-[0.26em] text-indigo-300">
            <span aria-hidden className="h-px w-10 bg-indigo-400/60" />
            AI security for the engineering pipeline
          </p>

          <h1 className="hero-display hero-enter stagger-2 text-slate-50">
            <span className="block">INTELLIGENCE</span>
            <span className="block">FOR THE</span>
            <span className="h-grad block">SOFTWARE LIFECYCLE</span>
          </h1>

          <p className="hero-enter stagger-3 mt-7 max-w-md text-sm leading-relaxed text-slate-400">
            A cinematic security layer over your repositories and pull
            requests — heuristic rules fused with Gemini AI, reviewing every
            change before it ships.
          </p>

          {/* Floating control panel */}
          <div className="hero-enter stagger-4 mt-10 max-w-md">
            <div className="holo-panel p-5 sm:p-6">
              <div className="flex items-center justify-between">
                <p className="hud-tag flex items-center gap-2">
                  <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.9)]" />
                  Control interface
                </p>
                <p className="font-mono text-[9px] uppercase tracking-[0.18em] text-slate-600">
                  v0.1.0
                </p>
              </div>

              <div className="mt-4 space-y-2.5">
                {SYSTEM_STATUS.map((status) => (
                  <div key={status.label} className="flex items-center justify-between border-b border-white/[0.05] pb-2.5 last:border-0">
                    <div className="flex items-center gap-2.5">
                      <span aria-hidden className={`h-1.5 w-1.5 rounded-full ${status.dot}`} />
                      <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-slate-400">
                        {status.label}
                      </span>
                    </div>
                    <span aria-hidden className={`font-mono text-[9px] ${status.tone}`}>●</span>
                  </div>
                ))}
              </div>

              <CinematicButton
                href={getLoginUrl()}
                className="group relative mt-6 flex w-full items-center justify-center gap-2 overflow-hidden rounded-xl border border-white/[0.12] bg-gradient-to-r from-indigo-500/90 via-violet-500/80 to-indigo-500/90 px-6 py-3.5 text-sm font-semibold text-white shadow-[0_18px_50px_-20px_rgba(99,102,241,0.9),inset_0_1px_0_rgba(255,255,255,0.15)] transition-all duration-200 hover:shadow-[0_22px_60px_-18px_rgba(99,102,241,1),inset_0_1px_0_rgba(255,255,255,0.2)]"
                strength={0.35}
              >
                <span aria-hidden className="absolute inset-0 translate-x-[-120%] bg-gradient-to-r from-transparent via-white/[0.18] to-transparent transition-transform duration-700 group-hover:translate-x-[130%]" />
                <svg viewBox="0 0 24 24" className="h-[18px] w-[18px]" fill="currentColor" aria-hidden="true">
                  <path d="M12 0C5.37 0 0 5.37 0 12c0 5.3 3.44 9.8 8.21 11.39.6.11.82-.26.82-.58v-2.03c-3.34.73-4.04-1.61-4.04-1.61-.55-1.39-1.34-1.76-1.34-1.76-1.09-.74.08-.73.08-.73 1.2.09 1.84 1.24 1.84 1.24 1.07 1.83 2.81 1.3 3.5 1 .1-.78.42-1.31.76-1.61-2.67-.3-5.47-1.34-5.47-5.95 0-1.31.47-2.39 1.24-3.23-.13-.3-.54-1.52.11-3.18 0 0 1.01-.32 3.3 1.23a11.5 11.5 0 0 1 6.01 0c2.29-1.55 3.29-1.23 3.29-1.23.65 1.66.24 2.88.12 3.18.77.84 1.24 1.92 1.24 3.23 0 4.62-2.8 5.64-5.48 5.94.43.37.81 1.1.81 2.22v3.29c0 .32.22.7.82.58A12 12 0 0 0 24 12c0-6.63-5.37-12-12-12Z" />
                </svg>
                Continue with GitHub
              </CinematicButton>

              <p className="mt-3 text-center text-xs text-slate-500">
                OAuth 2.0 · JWT session ·{' '}
                <Link to="/login" className="text-indigo-300 transition-colors hover:text-indigo-200">
                  Learn about permissions
                </Link>
              </p>
            </div>
          </div>
        </div>

        {/* Right visual slice — the 3D core lives here */}
        <div className="relative hidden lg:block" aria-hidden="true">
          <p className="absolute bottom-0 right-0 z-10 font-mono text-[9px] uppercase tracking-[0.26em] text-slate-600 [writing-mode:vertical-rl]">
            AI security core · live
          </p>
        </div>
      </main>

      {/* Bottom brand strip */}
      <footer className="relative z-20 mx-auto w-full max-w-[1400px] px-6 pb-8 lg:px-12">
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-white/[0.06] pt-5">
          {BRAND_ROWS.map((row, index) => (
            <span key={row.label} className="flex items-center gap-2">
              {index > 0 && <span aria-hidden className="mr-1 h-1 w-px bg-white/[0.12]" />}
              <svg viewBox="0 0 24 24" className={`h-3 w-3 ${row.label === 'Gemini AI' || row.label === 'Better Code' ? 'text-indigo-400' : 'text-slate-500'}`} fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">
                <path d={row.icon} strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              <span className="font-mono text-[9px] uppercase tracking-[0.18em] text-slate-500">
                {row.label}
              </span>
            </span>
          ))}
          <span className="ml-auto hidden font-mono text-[9px] uppercase tracking-[0.18em] text-slate-600 sm:block">
            Secure · Analyze · Improve · Ship
          </span>
        </div>
      </footer>
    </div>
  );
}