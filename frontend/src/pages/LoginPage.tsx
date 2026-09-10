import { Link, Navigate, useLocation } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import { getLoginUrl } from '../api/auth';

export function LoginPage() {
  const { token, initialized } = useAuth();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from;

  if (initialized && token) {
    return <Navigate to={from ?? '/dashboard'} replace />;
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-900 px-4 py-12">
      <div className="w-full max-w-md">
        <div className="rounded-2xl border border-slate-700 bg-slate-800 p-8 shadow-xl">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-500 text-lg font-bold text-white">
              SD
            </div>
            <div>
              <h1 className="text-xl font-semibold text-white">SmartSDLC</h1>
              <p className="text-sm text-slate-400">AI-assisted code review</p>
            </div>
          </div>

          <div className="mt-6 space-y-2 text-sm text-slate-300">
            <p className="font-medium text-white">Secure, AI-powered GitHub code review:</p>
            <ul className="list-inside list-disc space-y-1">
              <li>Heuristic + Gemini model analysis of every pull request</li>
              <li>Security, bugs, performance, and maintainability findings</li>
              <li>Accept or dismiss findings to tune future reviews</li>
            </ul>
          </div>

          <a
            href={getLoginUrl()}
            className="mt-8 flex w-full items-center justify-center gap-2 rounded-lg bg-slate-100 px-4 py-3 text-sm font-semibold text-slate-900 shadow-sm transition-colors hover:bg-white"
          >
            Continue with GitHub
          </a>

          <p className="mt-4 text-center text-xs text-slate-500">
            Authorizing lets SmartSDLC access your repositories and pull requests.
            <br />
            <Link to="/login" className="text-sky-400">
              Learn about permissions
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}