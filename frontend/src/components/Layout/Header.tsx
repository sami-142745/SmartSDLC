import { useNavigate } from 'react-router-dom';

import { useAuth } from '../../auth/AuthContext';
import { initials } from '../../utils/format';

export function Header() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login', { replace: true });
  };

  return (
    <header className="flex h-16 items-center justify-between border-b border-slate-200 bg-white px-4 sm:px-6">
      <div className="flex items-center gap-2 md:hidden">
        <div className="flex h-7 w-7 items-center justify-center rounded-md bg-emerald-500 text-xs font-bold text-white">
          SD
        </div>
        <span className="text-sm font-semibold text-slate-800">SmartSDLC</span>
      </div>

      <div className="hidden text-sm text-slate-400 md:block">
        AI-assisted code review for GitHub
      </div>

      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          {user?.avatar_url ? (
            <img
              src={user.avatar_url}
              alt={user.login ?? 'user'}
              className="h-8 w-8 rounded-full"
            />
          ) : (
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-emerald-500 text-xs font-bold text-white">
              {initials(user?.login)}
            </div>
          )}
          <span className="hidden text-sm font-medium text-slate-700 sm:inline">
            {user?.login ?? 'User'}
          </span>
        </div>
        <button
          type="button"
          onClick={handleLogout}
          className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50"
        >
          Log out
        </button>
      </div>
    </header>
  );
}