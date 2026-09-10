import { useState } from 'react';

import { API_BASE_URL, http } from '../api/client';
import { useAuth } from '../auth/AuthContext';

export function SettingsPage() {
  const { user } = useAuth();
  const [health, setHealth] = useState<'idle' | 'checking' | 'ok' | 'down'>('idle');

  const checkHealth = async () => {
    setHealth('checking');
    try {
      await http.get('/health');
      setHealth('ok');
    } catch {
      setHealth('down');
    }
  };

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Settings</h1>
        <p className="mt-1 text-sm text-slate-500">
          Your account and connection details.
        </p>
      </div>

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-500">
          GitHub account
        </h2>
        <div className="flex items-center gap-4">
          {user?.avatar_url ? (
            <img src={user.avatar_url} alt={user.login ?? 'user'} className="h-14 w-14 rounded-full" />
          ) : (
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-emerald-500 text-lg font-bold text-white">
              {(user?.login ?? '?').slice(0, 2).toUpperCase()}
            </div>
          )}
          <div className="text-sm">
            <p className="text-base font-semibold text-slate-900">
              {user?.name || user?.login || 'Unknown user'}
            </p>
            <p className="text-slate-500">@{user?.login ?? '—'}</p>
            {user?.email && <p className="mt-0.5 text-slate-500">{user.email}</p>}
            {user?.github_id != null && (
              <p className="mt-0.5 text-xs text-slate-400">GitHub ID {user.github_id}</p>
            )}
          </div>
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-500">
          Connection
        </h2>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="text-sm text-slate-700">
            <p className="font-mono text-xs text-slate-500">{API_BASE_URL}</p>
            <p className="mt-1">
              Status:{' '}
              {health === 'ok' ? (
                <span className="font-medium text-emerald-600">Backend reachable</span>
              ) : health === 'down' ? (
                <span className="font-medium text-red-600">Backend unreachable</span>
              ) : health === 'checking' ? (
                <span className="text-slate-500">Checking…</span>
              ) : (
                <span className="text-slate-500">Not checked yet</span>
              )}
            </p>
          </div>
          <button
            type="button"
            onClick={checkHealth}
            disabled={health === 'checking'}
            className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Check connection
          </button>
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
          Security
        </h2>
        <p className="text-sm text-slate-600">
          You are signed in with a SmartSDLC session token. Your GitHub OAuth access token and any
          AI provider keys stay on the backend and are never exposed to this app. Sign out from the
          header to clear your session from this browser.
        </p>
      </section>
    </div>
  );
}