import { NavLink } from 'react-router-dom';

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Dashboard', icon: 'M3 13h8V3H3v10Zm0 8h8v-6H3v6Zm10 0h8V11h-8v10Zm0-18v6h8V3h-8Z' },
  { to: '/repositories', label: 'Repositories', icon: 'M2 5a3 3 0 0 1 3-3h4l2 2h8a3 3 0 0 1 3 3v10a3 3 0 0 1-3 3H5a3 3 0 0 1-3-3V5Z' },
  { to: '/pull-requests', label: 'Pull Requests', icon: 'M7 21a2 2 0 1 0 0-4 2 2 0 0 0 0 4Zm10-12a2 2 0 1 0 0-4 2 2 0 0 0 0 4ZM7 3a2 2 0 1 0 0 4 2 2 0 0 0 0-4Zm10 12a2 2 0 1 0 0 4 2 2 0 0 0 0-4Z' },
  { to: '/history', label: 'Review History', icon: 'M12 4a8 8 0 1 1 0 16 8 8 0 0 1 0-16Zm0 2a6 6 0 1 0 0 12 6 6 0 0 0 0-12Zm-1 2h1.5v4.6l2.7 1.6-.8 1.3-3.4-2V8Z' },
  { to: '/feedback', label: 'Feedback', icon: 'M4 4h16a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H8l-4 4V4Zm3 5v2h10V9H7Zm0 4v2h6v-2H7Z' },
  { to: '/settings', label: 'Settings', icon: 'M8.1 2h7.8l1 2.6a6.3 6.3 0 0 1 2 1.2l2.7-.2 2.6 4.6-2 1.6a6.3 6.3 0 0 1 0 2.4l2 1.6-2.6 4.6-2.7-.2a6.3 6.3 0 0 1-2 1.2l-1 2.6H8.1l-1-2.6a6.3 6.3 0 0 1-2-1.2l-2.7.2-2.6-4.6 2-1.6a6.3 6.3 0 0 1 0-2.4l-2-1.6L2.4 7l2.7.2a6.3 6.3 0 0 1 2-1.2L8.1 2Zm1.5 2-.8 2a4.8 4.8 0 0 0-3 1.8l-2-.2-1 1.8 1.6 1.2a4.8 4.8 0 0 0 0 3.6L2.8 15l1 1.8 2-.2a4.8 4.8 0 0 0 3 1.8l.8 2h1.8l.8-2a4.8 4.8 0 0 0 3-1.8l2 .2 1-1.8-1.6-1.2a4.8 4.8 0 0 0 0-3.6L17 9l-1-1.8-2 .2a4.8 4.8 0 0 0-3-1.8l-.8-2H9.6ZM12 9a3 3 0 1 1 0 6 3 3 0 0 1 0-6Zm0 2a1 1 0 1 0 0 2 1 1 0 0 0 0-2Z' },
];

const linkBase = 'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors';

function NavLinkItem({ to, label, icon }: { to: string; label: string; icon: string }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `${linkBase} ${isActive ? 'bg-slate-800 text-white' : 'text-slate-300 hover:bg-slate-800/50 hover:text-white'}`
      }
    >
      <svg className="h-5 w-5 shrink-0" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
        <path d={icon} />
      </svg>
      {label}
    </NavLink>
  );
}

export function Sidebar() {
  return (
    <>
      {/* Desktop sidebar */}
      <aside className="hidden w-60 shrink-0 flex-col border-r border-slate-800 bg-slate-900 md:flex">
        <div className="flex h-16 items-center gap-2 px-5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500 text-sm font-bold text-white">
            SD
          </div>
          <span className="text-base font-semibold text-white">SmartSDLC</span>
        </div>
        <nav className="flex-1 space-y-1 px-3 py-4">
          {NAV_ITEMS.map((item) => (
            <NavLinkItem key={item.to} {...item} />
          ))}
        </nav>
      </aside>
    </>
  );
}

export function MobileNav() {
  return (
    <nav className="flex gap-1 overflow-x-auto border-b border-slate-800 bg-slate-900 px-2 py-2 md:hidden">
      {NAV_ITEMS.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          className={({ isActive }) =>
            `whitespace-nowrap rounded-md px-3 py-1.5 text-xs font-medium ${
              isActive ? 'bg-slate-800 text-white' : 'text-slate-300'
            }`
          }
        >
          {item.label}
        </NavLink>
      ))}
    </nav>
  );
}