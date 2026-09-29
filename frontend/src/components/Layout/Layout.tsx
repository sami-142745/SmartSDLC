import { Outlet, useLocation } from 'react-router-dom';
import { useEffect } from 'react';

import { isTestEnv } from '../../lib/env';
import { Ambient } from './Ambient';
import { Header } from './Header';
import { Sidebar } from './Sidebar';
import { SidebarProvider, useSidebar } from './SidebarContext';

/** Announce route changes to screen readers after a client-side navigation. */
function RouteAnnouncer() {
  const location = useLocation();
  useEffect(() => {
    const main = document.getElementById('main-content');
    main?.setAttribute('data-route', location.pathname);
  }, [location.pathname]);
  return null;
}

function Shell() {
  const { mobileOpen, setMobileOpen } = useSidebar();
  const location = useLocation();

  return (
    <div className="app-canvas flex min-h-screen">
      <Ambient />

      {/* Desktop rail */}
      <div className="sticky top-0 hidden h-screen shrink-0 lg:block">
        <Sidebar />
      </div>

      {/* Mobile drawer */}
      <div
        className={mobileOpen ? 'fixed inset-0 z-50 lg:hidden' : 'pointer-events-none fixed inset-0 z-50 lg:hidden'}
        aria-hidden={!mobileOpen}
      >
        <button
          type="button"
          tabIndex={mobileOpen ? 0 : -1}
          aria-label="Close navigation"
          onClick={() => setMobileOpen(false)}
          className={`absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity duration-200 ${
            mobileOpen ? 'opacity-100' : 'opacity-0'
          }`}
        />
        <div
          className={`absolute inset-y-0 left-0 shadow-lifted transition-transform duration-200 ease-swift ${
            mobileOpen ? 'translate-x-0' : '-translate-x-full'
          }`}
        >
          <Sidebar mobile />
        </div>
      </div>

      <div className="relative z-10 flex min-w-0 flex-1 flex-col">
        <Header />
        <main id="main-content" tabIndex={-1} className="flex-1 px-4 py-6 outline-none sm:px-6 lg:px-8 lg:py-8">
          <div className="mx-auto w-full max-w-[1400px]">
            {isTestEnv() ? (
              <Outlet />
            ) : (
              <div key={location.key} className="animate-fade-in">
                <Outlet />
              </div>
            )}
          </div>
        </main>
      </div>

      <RouteAnnouncer />
    </div>
  );
}

export function Layout() {
  return (
    <SidebarProvider>
      <a
        href="#main-content"
        className="sr-only-focusable fixed left-4 top-4 z-[100] rounded-lg border border-white/10 bg-surface-2 px-3 py-2 text-[13px] text-ink"
      >
        Skip to content
      </a>
      <Shell />
    </SidebarProvider>
  );
}
