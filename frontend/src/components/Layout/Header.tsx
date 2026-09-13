import { useLocation, useNavigate } from 'react-router-dom';

import { useAuth } from '../../auth/AuthContext';
import { CodeLogo } from '../CodeLogo';
import { initials } from '../../utils/format';

const PAGE_TITLES: Array<{ match: RegExp; title: string }> = [
  { match: /^\/dashboard$/, title: 'Command Center' },
  { match: /^\/repositories\//, title: 'Repository Intelligence' },
  { match: /^\/repositories$/, title: 'Repositories' },
  { match: /^\/pull-requests\//, title: 'Pull Request Analysis' },
  { match: /^\/pull-requests$/, title: 'Pull Requests' },
  { match: /^\/reviews\//, title: 'AI Security Analysis' },
  { match: /^\/history$/, title: 'Security Review History' },
  { match: /^\/feedback$/, title: 'Feedback Loop' },
  { match: /^\/settings$/, title: 'System Settings' },
];

function pageTitle(pathname: string): string {
  for (const { match, title } of PAGE_TITLES) {
    if (match.test(pathname)) return title;
  }
  return 'SmartSDLC';
}

export function Header() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = () => {
    logout();
    navigate('/login', { replace: true });
  };

  return (
    <header className="relative z-10 flex h-16 items-center justify-between gap-3 border-b border-white/[0.06] bg-surface-0/50 px-4 backdrop-blur-xl sm:px-8">
      <div className="flex min-w-0 flex-col">
        <span className="mb-1 hidden items-center gap-2 font-mono text-[9px] uppercase tracking-[0.24em] text-slate-600 md:flex">
          <span aria-hidden className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-400">
            <span className="absolute inset-0 animate-ping rounded-full bg-emerald-400/50" />
          </span>
          SmartSDLC security operations
        </span>
        <span className="flex items-center gap-2.5 md:hidden">
          <CodeLogo showWordmark={false} className="h-7 w-7 rounded-lg text-[10px]" />
          <span className="text-sm font-bold tracking-tight text-slate-100">SmartSDLC</span>
        </span>
        <h2 className="hidden truncate text-[15px] font-semibold leading-none tracking-[-0.015em] text-slate-50 md:block">
          {pageTitle(location.pathname)}
        </h2>
      </div>

      <div className="flex items-center gap-3">
        <span
          aria-hidden
          className="hidden items-center gap-1.5 rounded-full border border-white/[0.06] bg-surface-2/60 px-2.5 py-1 font-mono text-[9px] uppercase tracking-[0.16em] text-slate-500 lg:flex"
        >
          <span className="h-1 w-1 rounded-full bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.9)]" />
          Gemini AI
        </span>
        <div className="flex items-center gap-2 rounded-full border border-white/[0.07] bg-surface-2/60 py-1 pl-1 pr-3 shadow-elevated backdrop-blur-md">
          {user?.avatar_url ? (
            <img
              src={user.avatar_url}
              alt={user.login ?? 'user'}
              className="h-6 w-6 rounded-full ring-1 ring-accent-indigo/40"
            />
          ) : (
            <div className="flex h-6 w-6 items-center justify-center rounded-full bg-brand-gradient text-[10px] font-bold text-white shadow-[0_0_10px_rgba(99,102,241,0.5)]">
              {initials(user?.login)}
            </div>
          )}
          <span className="hidden text-sm font-medium text-slate-200 sm:inline">
            {user?.login ?? 'User'}
          </span>
        </div>
        <button
          type="button"
          onClick={handleLogout}
          className="btn-secondary px-3 py-1.5 text-sm transition-all hover:border-white/[0.16] hover:shadow-[0_0_20px_-8px_rgba(99,102,241,0.4)]"
        >
          Log out
        </button>
      </div>
    </header>
  );
}