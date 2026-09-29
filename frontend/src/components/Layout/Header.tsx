import { useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

import { useAuth } from '../../auth/AuthContext';
import { cn } from '../../lib/cn';
import { Avatar } from '../ui/Avatar';
import { Logo, LogoMark } from './Logo';
import { navLabelForPath } from './navItems';
import { useSidebar } from './SidebarContext';

function PanelIcon({ open }: { open: boolean }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true" className="h-4 w-4">
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d={open ? 'M9 4v16' : 'M3 12h18'} strokeLinecap="round" />
    </svg>
  );
}

function MenuIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true" className="h-4 w-4">
      <path d="M4 6h16M4 12h16M4 18h16" strokeLinecap="round" />
    </svg>
  );
}

/** Breadcrumb-style trail, e.g. Repositories / acme / webapp. */
function Breadcrumbs() {
  const { pathname } = useLocation();
  const segments = pathname.split('/').filter(Boolean);
  const section = navLabelForPath(pathname);

  if (segments.length === 0) return null;

  return (
    <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-1.5 text-[13px]">
      {section ? (
        <>
          <span className="shrink-0 text-ink-muted">{section}</span>
          {segments.length > 1 ? (
            <>
              <span aria-hidden className="text-ink-faint">
                /
              </span>
              <span className="truncate font-mono text-ink-subtle">
                {segments.slice(1).join(' / ')}
              </span>
            </>
          ) : null}
        </>
      ) : (
        <span className="truncate font-mono text-ink-subtle">{pathname}</span>
      )}
    </nav>
  );
}

function UserMenu() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-haspopup="menu"
        className="flex items-center gap-2 rounded-lg border border-white/[0.07] bg-white/[0.03] py-1 pl-1 pr-2 transition-colors hover:bg-white/[0.06]"
      >
        <Avatar name={user?.login ?? 'User'} src={user?.avatar_url} size="sm" />
        <span className="hidden text-[13px] font-medium text-ink-muted sm:inline">
          {user?.login ?? 'User'}
        </span>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true" className="h-3.5 w-3.5 text-ink-faint">
          <path d="m6 9 6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      {open ? (
        <div
          role="menu"
          className="glass-strong absolute right-0 z-50 mt-2 w-56 overflow-hidden p-1.5 shadow-lifted"
        >
          <div className="border-b border-white/[0.06] px-3 py-2.5">
            <p className="truncate text-[13px] font-medium text-ink">{user?.name ?? user?.login ?? 'User'}</p>
            {user?.login ? (
              <p className="truncate font-mono text-[11px] text-ink-faint">@{user.login}</p>
            ) : null}
          </div>
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              navigate('/settings');
            }}
            className="flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-left text-[13px] text-ink-muted transition-colors hover:bg-white/[0.06] hover:text-ink"
          >
            Settings
          </button>
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              logout();
              navigate('/login', { replace: true });
            }}
            className="flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-left text-[13px] text-rose-300 transition-colors hover:bg-rose-500/10"
          >
            Log out
          </button>
        </div>
      ) : null}
    </div>
  );
}

export function Header() {
  const { collapsed, toggleCollapsed, setMobileOpen } = useSidebar();

  return (
    <header className="sticky top-0 z-30 flex h-14 shrink-0 items-center gap-3 border-b border-white/[0.06] bg-surface-0/80 px-3 backdrop-blur-xl sm:px-5">
      <button
        type="button"
        onClick={() => setMobileOpen(true)}
        aria-label="Open navigation"
        className="btn-icon text-ink-subtle lg:hidden"
      >
        <MenuIcon />
      </button>

      <div className="lg:hidden">
        <LogoMark className="h-7 w-7" />
      </div>

      <div className="hidden min-w-0 lg:block">
        <Breadcrumbs />
      </div>

      <div className="ml-auto flex items-center gap-2">
        <span
          className={cn(
            'hidden items-center gap-1.5 rounded-full border border-white/[0.07] bg-white/[0.03]',
            'px-2.5 py-1 font-mono text-[9.5px] uppercase tracking-[0.16em] text-ink-faint md:inline-flex',
          )}
        >
          <span aria-hidden className="h-1 w-1 rounded-full bg-emerald-400" />
          Gemini AI
        </span>

        <button
          type="button"
          onClick={toggleCollapsed}
          aria-label={collapsed ? 'Expand navigation' : 'Collapse navigation'}
          aria-pressed={collapsed}
          className="btn-icon hidden text-ink-subtle lg:inline-flex"
        >
          <PanelIcon open={!collapsed} />
        </button>

        <UserMenu />
      </div>
    </header>
  );
}
