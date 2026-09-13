import { Outlet, useLocation } from 'react-router-dom';
import { AnimatePresence } from 'framer-motion';

import { AppBackground } from '../Background';
import { CinematicBackdrop } from '../CinematicBackdrop';
import { isTestEnv } from '../../lib/env';
import { Parallax } from '../motion/Parallax';
import { PageTransition } from '../ui/PageTransition';
import { Header } from './Header';
import { MobileNav, Sidebar } from './Sidebar';

export function Layout() {
  const location = useLocation();

  return (
    <div className="relative flex min-h-screen flex-col bg-surface-0 text-slate-200 md:flex-row">
      <Parallax depth={0.4} className="absolute inset-0">
        <AppBackground />
      </Parallax>
      <CinematicBackdrop className="[mask-image:radial-gradient(125%_92%_at_50%_38%,black_18%,black_62%,transparent_100%)]" />
      <Sidebar />
      <div className="relative z-10 flex min-w-0 flex-1 flex-col">
        <Header />
        <MobileNav />
        <main className="relative flex-1 px-6 py-8 lg:px-10 lg:py-10">
          <div
            aria-hidden
            className="pointer-events-none absolute inset-x-8 top-0 h-px bg-gradient-to-r from-transparent via-accent-indigo/20 to-transparent"
          />
          <div className="mx-auto w-full max-w-[1200px]">
            {isTestEnv() ? (
              <Outlet />
            ) : (
              <AnimatePresence mode="wait" initial={false}>
                <PageTransition key={location.pathname}>
                  <Outlet />
                </PageTransition>
              </AnimatePresence>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}