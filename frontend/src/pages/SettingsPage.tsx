import { useState } from 'react';
import type { ReactNode } from 'react';

import { getWebhookEvents } from '../api/webhooks';
import { API_BASE_URL, http } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { LoadingState } from '../components/LoadingState';
import { PageContainer } from '../components/PageContainer';
import { PageHeader } from '../components/PageHeader';
import { Button } from '../components/ui/Button';
import { Card, CardBody, CardHeader } from '../components/ui/Card';
import { useAsync } from '../hooks/useAsync';
import type { WebhookEvent } from '../types';
import { formatDate, initials, truncate } from '../utils/format';

function SettingsCard({
  title,
  description,
  children,
}: {
  title: string;
  description?: ReactNode;
  children: ReactNode;
}) {
  return (
    <Card>
      <CardHeader title={title} description={description} />
      <CardBody>{children}</CardBody>
    </Card>
  );
}

function EventRow({ event }: { event: WebhookEvent }) {
  return (
    <li className="flex flex-wrap items-center justify-between gap-x-6 gap-y-1 border-b border-white/[0.04] py-2.5 last:border-b-0">
      <div className="min-w-0">
        <p className="text-sm text-ink-muted">
          <span className="font-mono text-[11px] uppercase tracking-[0.12em] text-accent-indigo">
            {event.event}
          </span>
          <span className="mx-1.5 text-ink-faint">/</span>
          {event.action}
          {event.repository ? (
            <span className="text-ink">
              {' '}
              &middot; {event.repository}
              {event.pull_number != null ? <span> #{event.pull_number}</span> : null}
            </span>
          ) : null}
        </p>
        <p className="mt-0.5 font-mono text-[11px] text-ink-faint">
          {event.delivery_id ? truncate(event.delivery_id, 24) : 'no delivery id'}
          {event.payload_hash_prefix ? ` \u00b7 ${event.payload_hash_prefix}` : ''}
        </p>
      </div>
      <p className="shrink-0 font-mono text-[11px] tabular-nums text-ink">{formatDate(event.received_at)}</p>
    </li>
  );
}

function WebhookDeliveries() {
  const events = useAsync(() => getWebhookEvents({ page: 1, per_page: 25 }), []);

  if (events.loading) return <LoadingState label="Loading deliveries…" />;
  if (events.error || !events.data) {
    return <p className="text-sm text-rose-300">Could not load webhook deliveries.</p>;
  }
  if (events.data.items.length === 0) {
    return <p className="text-sm text-ink-subtle">No webhook deliveries recorded yet.</p>;
  }

  return (
    <ul>
      {events.data.items.map((event) => (
        <EventRow key={event.id} event={event} />
      ))}
    </ul>
  );
}

type HealthState = 'idle' | 'checking' | 'ok' | 'down';

const HEALTH_COPY: Record<HealthState, { label: string; className: string; dot: string }> = {
  idle: { label: 'Not checked yet', className: 'text-ink-subtle', dot: '' },
  checking: { label: 'Checking…', className: 'text-ink-subtle', dot: '' },
  ok: {
    label: 'Backend reachable',
    className: 'text-emerald-300',
    dot: 'bg-emerald-400',
  },
  down: {
    label: 'Backend unreachable',
    className: 'text-rose-300',
    dot: 'bg-rose-400',
  },
};

export function SettingsPage() {
  const { user } = useAuth();
  const [health, setHealth] = useState<HealthState>('idle');

  const checkHealth = async () => {
    setHealth('checking');
    try {
      await http.get('/health');
      setHealth('ok');
    } catch {
      setHealth('down');
    }
  };

  const status = HEALTH_COPY[health];

  return (
    <PageContainer className="max-w-3xl space-y-6" wide={false}>
      <PageHeader
        eyebrow={
          <>
            <span aria-hidden className="h-px w-8 bg-indigo-400/60" />
            Developer settings &middot; control room
          </>
        }
        title="Settings"
        description="Your account, connection, and session details."
      />

      <SettingsCard title="GitHub account">
        <div className="flex items-center gap-4">
          {user?.avatar_url ? (
            <img
              src={user.avatar_url}
              alt={user.login ?? 'user'}
              className="h-14 w-14 rounded-full ring-2 ring-accent-indigo/40"
            />
          ) : (
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-brand-gradient text-base font-bold text-white">
              {initials(user?.login)}
            </div>
          )}
          <div className="min-w-0 text-sm">
            <p className="truncate text-[15px] font-semibold text-ink">
              {user?.name || user?.login || 'Unknown user'}
            </p>
            <p className="text-accent-indigo">@{user?.login ?? '\u2014'}</p>
            {user?.email ? <p className="mt-0.5 text-ink-subtle">{user.email}</p> : null}
            {user?.github_id != null ? (
              <p className="mt-0.5 font-mono text-[11px] text-ink-faint">
                GitHub ID {user.github_id}
              </p>
            ) : null}
          </div>
        </div>
      </SettingsCard>

      <SettingsCard title="Connection">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0 text-sm">
            <p className="truncate font-mono text-xs text-ink">{API_BASE_URL}</p>
            <p className="mt-1.5 text-ink-muted">
              Status:{' '}
              <span className={`inline-flex items-center gap-1.5 font-medium ${status.className}`}>
                {status.dot ? <span aria-hidden className={`h-1.5 w-1.5 rounded-full ${status.dot}`} /> : null}
                {status.label}
              </span>
            </p>
          </div>
          <Button variant="secondary" onClick={checkHealth} disabled={health === 'checking'}>
            <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
              <path d="M20 12a8 8 0 0 1-11.6 7.1M4 12a8 8 0 0 1 11.6-7.1M12 3v6m0 6v6M3 12h6m6 0h6" strokeLinecap="round" />
            </svg>
            Check connection
          </Button>
        </div>
      </SettingsCard>

      <SettingsCard title="Security">
        <p className="text-sm leading-relaxed text-ink-subtle">
          You are signed in with a SmartSDLC session token. Your GitHub OAuth access token and any
          AI provider keys stay on the backend and are never exposed to this app. Sign out from the
          header to clear your session from this browser.
        </p>
        <ul className="mt-4 flex flex-wrap gap-x-6 gap-y-1.5 text-[11.5px] text-ink-subtle">
          {[
            { tone: 'bg-emerald-400/80', label: 'OAuth token stored server-side' },
            { tone: 'bg-sky-400/80', label: 'AI keys never leave backend' },
            { tone: 'bg-violet-400/80', label: 'Session scoped to browser' },
          ].map((item) => (
            <li key={item.label} className="inline-flex items-center gap-1.5">
              <span aria-hidden className={`h-1.5 w-1.5 rounded-full ${item.tone}`} />
              {item.label}
            </li>
          ))}
        </ul>
      </SettingsCard>

      <SettingsCard
        title="Webhook deliveries"
        description="Recent signed pull-request deliveries processed by the review engine. Replay protection rejects repeated deliveries by delivery ID and payload hash, so replays are never re-processed."
      >
        <WebhookDeliveries />
      </SettingsCard>
    </PageContainer>
  );
}
