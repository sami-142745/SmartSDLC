import { NavLink } from 'react-router-dom';

import { CodeLogo } from '../CodeLogo';

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Command Center', icon: 'M3 13h8V3H3v10Zm0 8h8v-6H3v6Zm10 0h8V11h-8v10Zm0-18v6h8V3h-8Z' },
  { to: '/repositories', label: 'Repositories', icon: 'M2 5a3 3 0 0 1 3-3h4l2 2h8a3 3 0 0 1 3 3v10a3 3 0 0 1-3 3H5a3 3 0 0 1-3-3V5Z' },
  { to: '/pull-requests', label: 'Pull Requests', icon: 'M7 21a2 2 0 1 0 0-4 2 2 0 0 0 0 4Zm10-12a2 2 0 1 0 0-4 2 2 0 0 0 0 4ZM7 3a2 2 0 1 0 0 4 2 2 0 0 0 0-4Zm10 12a2 2 0 1 0 0 4 2 2 0 0 0 0-4Z' },
  { to: '/history', label: 'Review History', icon: 'M12 4a8 8 0 1 1 0 16 8 8 0 0 1 0-16Zm0 2a6 6 0 1 0 0 12 6 6 0 0 0 0-12Zm-1 2h1.5v4.6l2.7 1.6-.8 1.3-3.4-2V8Z' },
  { to: '/documents', label: 'Documentation', icon: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6Zm-1 1.5V8h4.5M8 13h8v-2H8v2Zm0 4h5v-2H8v2Z' },
  { to: '/insights', label: 'Insights', icon: 'M3 3h2v14h14v2H3V3Zm4 12a2 2 0 1 1 4 0 2 2 0 0 1-4 0Zm6-6a2 2 0 1 1 4 0 2 2 0 0 1-4 0ZM4 5h6v2H4V5Zm2-2h8v2H6V3Z' },
  { to: '/feedback', label: 'Feedback Loop', icon: 'M4 4h16a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H8l-4 4V4Zm3 5v2h10V9H7Zm0 4v2h6v-2H7Z' },
  { to: '/workflows', label: 'Workflows', icon: 'M4 4h5v5H4V4Zm2 2v1h1V6H6Zm9-2h5v5h-5V4Zm2 2v1h1V6h-1ZM4 15h5v5H4v-5Zm2 2v1h1v-1H6Zm9-2h5v5h-5v-5Zm2 2v1h1v-1h-1ZM12 7a1 1 0 1 1 0 2 1 1 0 0 1 0-2Zm0 8a1 1 0 1 1 0 2 1 1 0 0 1 0-2Zm-4 0h8v-4H8v4Z' },
  { to: '/settings', label: 'Settings', icon: 'M8.1 2h7.8l1 2.6a6.3 6.3 0 0 1 2 1.2l2.7-.2 2.6 4.6-2 1.6a6.3 6.3 0 0 1 0 2.4l2 1.6-2.6 4.6-2.7-.2a6.3 6.3 0 0 1-2 1.2l-1 2.6H8.1l-1-2.6a6.3 6.3 0 0 1-2-1.2l-2.7.2-2.6-4.6 2-1.6a6.3 6.3 0 0 1 0-2.4l-2-1.6L2.4 7l2.7.2a6.3 6.3 0 0 1 2-1.2L8.1 2Zm1.5 2-.8 2a4.8 4.8 0 0 0-3 1.8l-2-.2-1 1.8 1.6 1.2a4.8 4.8 0 0 0 0 3.6L2.8 15l1 1.8 2-.2a4.8 4.8 0 0 0 3 1.8l.8 2h1.8l.8-2a4.8 4.8 0 0 0 3-1.8l2 .2 1-1.8-1.6-1.2a4.8 4.8 0 0 0 0-3.6L17 9l-1-1.8-2 .2a4.8 4.8 0 0 0-3-1.8l-.8-2H9.6ZM12 9a3 3 0 1 1 0 6 3 3 0 0 1 0-6Zm0 2a1 1 0 1 0 0 2 1 1 0 0 0 0-2Z' },
];

function NavLinkItem({ to, label, icon }: { to: string; label: string; icon: string }) {
  return (
    <NavLink
      to={to}
      aria-label={label}
      title={label}
      className={({ isActive }) =>
        `group/nav relative flex h-10 w-10 items-center justify-center rounded-lg transition-all duration-200 ${
          isActive
            ? 'bg-gradient-to-br from-accent-indigo/[0.18] to-accent-violet/[0.1] text-accent-lavender'
            : 'text-slate-500 hover:bg-white/[0.04] hover:text-slate-200'
        } ${
          isActive
            ? 'shadow-[0_0_0_1px_rgba(99,102,241,0.3),0_0_22px_-8px_rgba(99,102,241,0.6),inset_0_0_18px_-14px_rgba(99,102,241,0.7)]'
            : ''
        }`
      }
    >
      {({ isActive }) => (
        <>
          {isActive && (
            <>
              <span
                aria-hidden
                className="absolute inset-0 rounded-lg opacity-40 [mask-image:radial-gradient(75%_75%_at_50%_30%,black,transparent)]"
                style={{
                  background:
                    'radial-gradient(ellipse 60% 45% at 50% 20%, rgba(129,140,248,0.28), transparent 80%)',
                }}
              />
              <span
                aria-hidden
                className="absolute -left-[6px] top-1/2 h-[58%] w-[2px] -translate-y-1/2 rounded-full bg-brand-gradient shadow-[0_0_10px_rgba(129,140,248,0.8)]"
              />
            </>
          )}
          <svg
            viewBox="0 0 24 24"
            fill="currentColor"
            aria-hidden="true"
            className={`relative z-10 h-[18px] w-[18px] transition-all ${
              isActive ? 'drop-shadow-[0_0_8px_rgba(99,102,241,0.6)]' : ''
            }`}
          >
            <path d={icon} />
          </svg>
          <span
            role="tooltip"
            className="pointer-events-none absolute left-full z-30 ml-3 hidden whitespace-nowrap rounded-lg border border-white/[0.08] bg-surface-3/95 px-2.5 py-1.5 text-xs font-medium text-slate-200 shadow-elevated opacity-0 backdrop-blur-md transition-opacity duration-100 group-hover/nav:opacity-100 xl:block"
          >
            {label}
          </span>
        </>
      )}
    </NavLink>
  );
}

export function Sidebar() {
  return (
    <aside className="relative z-20 hidden w-[4.5rem] shrink-0 flex-col border-r border-white/[0.06] bg-surface-0/70 backdrop-blur-2xl md:flex">
      <div aria-hidden className="pointer-events-none absolute inset-0 bg-glass-gradient" />
      <div className="relative flex h-16 items-center justify-center border-b border-white/[0.05]">
        <span aria-label="SmartSDLC" className="group/logo relative">
          <CodeLogo showWordmark={false} className="h-9 w-9 rounded-xl text-xs transition-all group-hover/logo:shadow-glow-md" />
        </span>
      </div>

      <nav className="relative flex flex-1 flex-col items-center gap-1.5 px-2 py-4">
        {NAV_ITEMS.map((item) => (
          <NavLinkItem key={item.to} {...item} />
        ))}
      </nav>

      <div className="relative flex flex-col items-center gap-3 px-2 pb-6">
        <span className="h-px w-7 bg-white/[0.06]" />
        <div className="flex flex-col items-center gap-2.5">
          <span className="relative flex h-2 w-2" aria-hidden>
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-50" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]" />
          </span>
          <p
            className="whitespace-nowrap font-mono text-[9px] uppercase tracking-[0.28em] text-slate-600 [writing-mode:vertical-rl]"
            style={{ transform: 'rotate(180deg)' }}
          >
            AI engine online
          </p>
        </div>
      </div>
    </aside>
  );
}

export function MobileNav() {
  return (
    <nav className="relative z-20 flex gap-1 overflow-x-auto border-b border-white/[0.06] bg-surface-0/80 px-2 py-2 backdrop-blur-xl md:hidden">
      {NAV_ITEMS.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          className={({ isActive }) =>
            `flex shrink-0 items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
              isActive
                ? 'bg-gradient-to-br from-accent-indigo/20 to-accent-violet/10 text-accent-lavender shadow-[0_0_16px_-6px_rgba(99,102,241,0.6)]'
                : 'text-slate-400 hover:bg-white/[0.04] hover:text-white'
            }`
          }
        >
          {({ isActive }) => (
            <>
              <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" className="h-3.5 w-3.5">
                <path d={item.icon} />
              </svg>
              <span className="whitespace-nowrap">{item.label}</span>
              {isActive && (
                <span
                  aria-hidden
                  className="h-1 w-1 rounded-full bg-accent-lavender shadow-[0_0_6px_rgba(196,181,253,0.9)]"
                />
              )}
            </>
          )}
        </NavLink>
      ))}
    </nav>
  );
}