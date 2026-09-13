import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { getWorkflows } from '../api/workflows';
import { DataTable } from '../components/DataTable';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import { PageContainer } from '../components/PageContainer';
import { Reveal } from '../components/motion/Reveal';
import { useAsync } from '../hooks/useAsync';
import type { Workflow } from '../types';
import { formatDate } from '../utils/format';

const STATUS_STYLE: Record<string, string> = {
  queued: 'border-amber-300/25 bg-amber-300/[0.06] text-amber-200',
  running: 'border-sky-400/25 bg-sky-400/[0.06] text-sky-300',
  completed: 'border-emerald-500/20 bg-emerald-500/[0.06] text-emerald-300',
  failed: 'border-rose-500/25 bg-rose-500/[0.06] text-rose-300',
};

const STATUS_FILTERS = ['all', 'queued', 'running', 'completed', 'failed'] as const;

function StatusChip({ status }: { status: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.14em] ${
        STATUS_STYLE[status] ?? 'border-slate-500/30 bg-slate-500/[0.06] text-slate-400'
      }`}
    >
      {status}
    </span>
  );
}

function formatDuration(ms: number | null): string {
  if (ms == null) return '—';
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

function Stat({ label, value, tone = 'text-slate-50' }: { label: string; value: number; tone?: string }) {
  return (
    <div className="holo-panel holo-panel-press px-4 py-4">
      <p className="hud-tag">{label}</p>
      <p className={`mt-2 font-mono text-2xl font-semibold tabular-nums ${tone}`}>{value}</p>
    </div>
  );
}

export function WorkflowsPage() {
  const navigate = useNavigate();
  const [statusFilter, setStatusFilter] = useState<string>('all');

  const workflows = useAsync(
    () => getWorkflows({ page: 1, per_page: 100, status: statusFilter === 'all' ? undefined : statusFilter }),
    [statusFilter],
  );

  const stats = useMemo(() => {
    const total = workflows.data?.total ?? 0;
    const items = workflows.data?.items ?? [];
    const running = items.filter((w) => w.status === 'running').length;
    const completed = items.filter((w) => w.status === 'completed').length;
    const failed = items.filter((w) => w.status === 'failed').length;
    return { total, running, completed, failed };
  }, [workflows.data]);

  const columns = [
    {
      key: 'pr',
      header: 'Pull request',
      render: (w: Workflow) => (
        <div className="min-w-0">
          <p className="truncate font-medium text-slate-100">
            {w.owner}/{w.repository}
            <span className="text-slate-500"> #{w.pull_request_number}</span>
          </p>
          <p className="mt-0.5 font-mono text-[11px] text-slate-500">
            {w.trigger} · {w.provider}
          </p>
        </div>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (w: Workflow) => <StatusChip status={w.status} />,
    },
    {
      key: 'stage',
      header: 'Stage',
      render: (w: Workflow) => (
        <span className="font-mono text-xs text-slate-300">{w.stage.replace(/_/g, ' ')}</span>
      ),
    },
    {
      key: 'duration',
      header: 'Duration',
      render: (w: Workflow) => (
        <span className="font-mono text-xs tabular-nums text-slate-400">{formatDuration(w.duration_ms)}</span>
      ),
    },
    {
      key: 'updated',
      header: 'Updated',
      render: (w: Workflow) => (
        <span className="font-mono text-xs tabular-nums text-slate-400">{formatDate(w.updated_at)}</span>
      ),
    },
  ];

  if (workflows.loading) return <LoadingState label="Loading workflows\u2026" />;
  if (workflows.error || !workflows.data) {
    return (
      <ErrorState
        title="Could not load workflows"
        message={workflows.error ?? undefined}
        retry={workflows.refetch}
      />
    );
  }

  const items = workflows.data.items;

  return (
    <PageContainer className="space-y-10">
      <Reveal>
        <section className="py-6 lg:py-9">
          <p className="hud-tag hud-tag-accent flex items-center gap-3">
            <span aria-hidden className="h-px w-10 bg-indigo-400/60" />
            <span className="font-mono">Review pipeline telemetry</span>
          </p>
          <div className="mt-6 flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <h1 className="text-[clamp(2.1rem,5.5vw,4.6rem)] font-semibold leading-[1] tracking-[-0.035em] text-slate-50">
                Workflow Orchestration
              </h1>
              <p className="mt-5 text-sm leading-relaxed text-slate-400">
                End-to-end lifecycle of every review run — from receiving the trigger through fetch, analysis,
                generation, and persistence.
              </p>
            </div>
          </div>
        </section>
      </Reveal>

      <Reveal delay={0.05}>
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <Stat label="Total runs" value={stats.total} />
          <Stat label="Running" value={stats.running} tone="text-sky-300" />
          <Stat label="Completed" value={stats.completed} tone="text-emerald-300" />
          <Stat label="Failed" value={stats.failed} tone="text-rose-300" />
        </div>
      </Reveal>

      <Reveal delay={0.1}>
        <section className="glass-edge block rounded-xl p-5">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <p className="hud-tag hud-tag-accent">Execution history</p>
            <div className="flex flex-wrap gap-2">
              {STATUS_FILTERS.map((filter) => (
                <button
                  key={filter}
                  type="button"
                  onClick={() => setStatusFilter(filter)}
                  className={`rounded-full border px-3 py-1 font-mono text-[10px] uppercase tracking-[0.14em] transition-all ${
                    statusFilter === filter
                      ? 'border-indigo-400/40 bg-indigo-400/[0.08] text-indigo-200 shadow-[0_0_14px_-6px_rgba(99,102,241,0.7)]'
                      : 'border-white/[0.06] bg-white/[0.02] text-slate-500 hover:text-slate-300'
                  }`}
                >
                  {filter}
                </button>
              ))}
            </div>
          </div>

          {items.length === 0 ? (
            <div className="rounded-xl border border-dashed border-white/[0.08] bg-surface-1/40 px-4 py-12 text-center">
              <p className="text-sm text-slate-400">No workflows recorded yet.</p>
              <p className="mt-1 text-xs text-slate-500">
                Trigger a pull request review to see its pipeline stages here.
              </p>
            </div>
          ) : (
            <DataTable
              columns={columns}
              rows={items}
              rowKey={(w) => w.workflow_id}
              onRowClick={(w) => navigate(`/workflows/${w.workflow_id}`)}
            />
          )}
        </section>
      </Reveal>
    </PageContainer>
  );
}