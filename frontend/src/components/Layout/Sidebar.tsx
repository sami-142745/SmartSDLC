import { useEffect } from 'react';
import { NavLink, useLocation } from 'react-router-dom';

import { cn } from '../../lib/cn';
import { useSidebar } from './SidebarContext';
import { Logo } from './Logo';
import { NAV_GROUPS } from './navItems';
import type { NavItem } from './navItems';

function NavLinkItem({ item, collapsed }: { item: NavItem; collapsed: boolean }) {
  return (
    <NavLink
      to={item.to}
      title={collapsed ? item.label : undefined}
      className={({ isActive }) =>
        cn(
          'group/nav relative flex items-center gap-3 rounded-lg transition-all duration-150 ease-swift',
          collapsed ? 'h-10 w-10 justify-center' : 'px-3 py-2',
          isActive
            ? 'bg-white/[0.07] text-ink shadow-[inset_0_0_18px_-14px_rgba(139,92,246,0.7)]'
            : 'text-ink-subtle hover:bg-white/[0.035] hover:text-ink-muted',
        )
      }
    >
      {({ isActive }) => (
        <>
          {isActive ? (
            <span
              aria-hidden
              className="absolute left-0 top-1/2 h-5 w-[2px] -translate-y-1/2 rounded-full bg-brand-gradient"
            />
          ) : null}
          <svg
            viewBox="0 0 24 24"
            fill="currentColor"
            aria-hidden="true"
            className={cn(
              'h-[18px] w-[18px] shrink-0 transition-colors',
              isActive ? 'text-accent-lavender' : 'text-ink-faint group-hover/nav:text-ink-subtle',
            )}
          >
            <path d={item.icon} />
          </svg>
          {collapsed ? (
            <span className="sr-only">{item.label}</span>
          ) : (
            <span className="truncate text-[13px] font-medium">{item.label}</span>
          )}
        </>
      )}
    </NavLink>
  );
}

export interface SidebarProps {
  /** Off-canvas drawer on small screens. */
  mobile?: boolean;
}

export function Sidebar({ mobile = false }: SidebarProps) {
  const { collapsed, setCollapsed, closeMobile } = useSidebar();
  const location = useLocation();

  // Navigating on mobile should dismiss the drawer.
  useEffect(() => {
    if (mobile) closeMobile();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname]);

  return (
    <div
      className={cn(
        'flex h-full flex-col border-r border-white/[0.06] bg-surface-0/80 backdrop-blur-2xl',
        collapsed ? 'w-[4.5rem]' : 'w-[15.5rem]',
      )}
    >
      <div
        className={cn(
          'flex h-14 shrink-0 items-center border-b border-white/[0.05]',
          collapsed ? 'justify-center px-0' : 'gap-2.5 px-4',
        )}
      >
        <Logo collapsed={collapsed} />
      </div>

      <nav
        aria-label="Main"
        className="scrollbar-thin flex-1 overflow-y-auto px-2.5 py-3"
      >
        {NAV_GROUPS.map((group) => (
          <div key={group.id} className="mb-1 last:mb-0">
            {collapsed ? (
              <div aria-hidden className="mx-auto my-2 h-px w-6 bg-white/[0.06]" />
            ) : (
              <p className="px-3 pb-1.5 pt-3 font-mono text-[9.5px] uppercase tracking-[0.18em] text-ink-faint/80">
                {group.label}
              </p>
            )}
            <ul className="space-y-0.5">
              {group.items.map((item) => (
                <li key={item.to}>
                  <NavLinkItem item={item} collapsed={collapsed} />
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>

      {!collapsed ? (
        <div className="shrink-0 border-t border-white/[0.05] px-4 py-3">
          <div className="flex items-center gap-2">
            <span aria-hidden className="relative flex h-1.5 w-1.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-400" />
            </span>
            <span className="font-mono text-[9.5px] uppercase tracking-[0.18em] text-ink-faint">
              AI engine online
            </span>
          </div>
        </div>
      ) : null}
    </div>
  );
}
