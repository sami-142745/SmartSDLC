import { useState } from 'react';
import type { ReactNode } from 'react';

import { getWebhookEvents } from '../api/webhooks';
import { API_BASE_URL, http } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { PageContainer } from '../components/PageContainer';
import { useAsync } from '../hooks/useAsync';
import type { WebhookEvent } from '../types';
import { formatDate, initials, truncate } from '../utils/format';

function SettingsSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="holo-panel holo-panel-press p-5 sm:p-6">
      <p className="tech-label inline-flex items-center gap-2">
        <span className="h-1 w-1 rounded-full bg-accent-indigo/70" />
        {title}
      </p>
      <div className="mt-5">{children}</div>
    </section>
  );
}

function WebhookDeliveries() {
  const events = useAsync(() => getWebhookEvents({ page: 1, per_page: 25 }), []);

  return (
    <div>
      {events.loading ? (
        <p className="text-sm text-slate-500">Loading deliveries\u2026</p>
      ) : events.error || !events.data ? (
        <p className="text-sm text-rose-300">Could not load webhook deliveries.</p>
      ) : events.data.items.length === 0 ? (
        <p className="text-sm text-slate-500">No webhook deliveries recorded yet.</p>
      ) : (
        <ul className="divide-y divide-white/[0.04]">
          {events.data.items.map((event) => (
            <EventRow key={event.id} event={event} />
          ))}
        </ul>
      )}
    </div>
  );
}

function EventRow({ event }: { event: WebhookEvent }) {
  return (
    <li className="flex flex-wrap items-center justify-between gap-x-6 gap-y-1 py-2.5">
      <div className="min-w-0">
        <p className="text-sm text-slate-200">
          <span className="font-mono text-xs uppercase tracking-[0.12em] text-accent-indigo">
            {event.event}
          </span>
          <span className="mx-1.5 text-slate-600">/</span>
          {event.action}
          {event.repository && (
            <span className="text-slate-500">
              {' '}
              · {event.repository}
              {event.pull_number != null && <span> #{event.pull_number}</span>}
            </span>
          )}
        </p>
        <p className="mt-0.5 font-mono text-[11px] text-slate-600">
          {event.delivery_id ? truncate(event.delivery_id, 24) : 'no delivery id'}
          {event.payload_hash_prefix ? ` · ${event.payload_hash_prefix}` : ''}
        </p>
      </div>
      <p className="shrink-0 font-mono text-xs tabular-nums text-slate-500">{formatDate(event.received_at)}</p>
    </li>
  );
}

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
    <PageContainer className="max-w-3xl space-y-8" wide={false}>
      {/* Control room header */}
      <section className="py-4">
        <p className="hud-tag hud-tag-accent flex items-center gap-3">
          <span aria-hidden className="h-px w-8 bg-indigo-400/60" />
          Developer settings · control room
        </p>
        <h1 className="hero-display mt-3 text-slate-50">SETTINGS</h1>
        <p className="mt-4 text-sm text-slate-400">
          Your account, connection, and session details.
        </p>
      </section>

      <SettingsSection title="GitHub account">
        <div className="flex items-center gap-4">
          {user?.avatar_url ? (
            <img
              src={user.avatar_url}
              alt={user.login ?? 'user'}
              className="h-16 w-16 rounded-full ring-2 ring-accent-indigo/40"
            />
          ) : (
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-brand-gradient text-lg font-bold text-white shadow-glow-sm">
              {initials(user?.login)}
            </div>
          )}
          <div className="text-sm">
            <p className="text-base font-semibold text-slate-100">
              {user?.name || user?.login || 'Unknown user'}
            </p>
            <p className="text-accent-indigo">@{user?.login ?? '\u2014'}</p>
            {user?.email && <p className="mt-0.5 text-slate-400">{user.email}</p>}
            {user?.github_id != null && (
              <p className="mt-0.5 text-xs text-slate-500">GitHub ID {user.github_id}</p>
            )}
          </div>
        </div>
      </SettingsSection>

      <SettingsSection title="Connection">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="text-sm text-slate-300">
            <p className="font-mono text-xs text-slate-500">{API_BASE_URL}</p>
            <p className="mt-1">
              Status:{' '}
              {health === 'ok' ? (
                <span className="inline-flex items-center gap-1.5 font-medium text-emerald-300">
                  <span
                    aria-hidden
                    className="inline-flex h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.7)]"
                  />
                  Backend reachable
                </span>
              ) : health === 'down' ? (
                <span className="inline-flex items-center gap-1.5 font-medium text-rose-300">
                  <span
                    aria-hidden
                    className="inline-flex h-1.5 w-1.5 rounded-full bg-rose-400 shadow-[0_0_6px_rgba(244,63,94,0.7)]"
                  />
                  Backend unreachable
                </span>
              ) : health === 'checking' ? (
                <span className="text-slate-400">Checking\u2026</span>
              ) : (
                <span className="text-slate-400">Not checked yet</span>
              )}
            </p>
          </div>
          <button
            type="button"
            onClick={checkHealth}
            disabled={health === 'checking'}
            className="relative inline-flex items-center gap-2 rounded-lg border border-white/[0.08] bg-white/[0.02] px-4 py-2 text-sm font-medium text-slate-300 transition-all duration-150 hover:border-accent-indigo/30 hover:text-slate-100 hover:shadow-[0_0_14px_-8px_rgba(99,102,241,0.5)] disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:border-white/[0.08] disabled:hover:text-slate-300 disabled:hover:shadow-none"
          >
            <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
              <path d="M20 12a8 8 0 0 1-11.6 7.1M4 12a8 8 0 0 1 11.6-7.1M12 3v6m0 6v6M3 12h6m6 0h6" strokeLinecap="round" />
            </svg>
            Check connection
          </button>
        </div>
      </SettingsSection>

      <SettingsSection title="Security">
        <p className="text-sm leading-relaxed text-slate-400">
          You are signed in with a SmartSDLC session token. Your GitHub OAuth access token and any
          AI provider keys stay on the backend and are never exposed to this app. Sign out from the
          header to clear your session from this browser.
        </p>
        <div className="mt-4 flex flex-wrap gap-x-6 gap-y-1.5 text-xs text-slate-500">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400/80" /> OAuth token stored server-side
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-sky-400/80" /> AI keys never leave backend
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-violet-400/80" /> Session scoped to browser
          </span>
        </div>
      </SettingsSection>

      <SettingsSection title="Webhook deliveries">
        <p className="mb-4 text-sm leading-relaxed text-slate-400">
          Recent signed pull-request deliveries processed by the review engine. Replay protection rejects
          repeated deliveries by delivery ID and payload hash, so replays are never re-processed.
        </p>
        <WebhookDeliveries />
      </SettingsSection>
    </PageContainer>
  );
}