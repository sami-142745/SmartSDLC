import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { getWorkflows } from '../api/workflows';
import { DataTable } from '../components/DataTable';
import type { Column } from '../components/DataTable';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import { MetricCard, MetricGrid } from '../components/MetricCard';
import { PageContainer } from '../components/PageContainer';
import { PageHeader } from '../components/PageHeader';
import { Card, CardBody, CardHeader } from '../components/ui/Card';
import { cn } from '../lib/cn';
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
      className={cn(
        'chip font-mono uppercase tracking-[0.14em]',
        STATUS_STYLE[status] ?? 'border-white/10 bg-ink-faint/[0.06] text-ink-subtle',
      )}
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

export function WorkflowsPage() {
  const navigate = useNavigate();
  const [statusFilter, setStatusFilter] = useState<string>('all');

  const workflows = useAsync(
    () =>
      getWorkflows({
        page: 1,
        per_page: 100,
        status: statusFilter === 'all' ? undefined : statusFilter,
      }),
    [statusFilter],
  );

  const stats = useMemo(() => {
    const total = workflows.data?.total ?? 0;
    const items = workflows.data?.items ?? [];
    return {
      total,
      running: items.filter((w) => w.status === 'running').length,
      completed: items.filter((w) => w.status === 'completed').length,
      failed: items.filter((w) => w.status === 'failed').length,
    };
  }, [workflows.data]);

  const columns: Column<Workflow>[] = [
    {
      key: 'pr',
      header: 'Pull request',
      render: (w) => (
        <div className="min-w-0">
          <p className="truncate font-medium text-ink">
            {w.owner}/{w.repository}
            <span className="text-ink"> #{w.pull_request_number}</span>
          </p>
          <p className="mt-0.5 font-mono text-[11px] text-ink-faint">
            {w.trigger} &middot; {w.provider}
          </p>
        </div>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (w) => <StatusChip status={w.status} />,
    },
    {
      key: 'stage',
      header: 'Stage',
      hideBelow: 'sm',
      render: (w) => (
        <span className="font-mono text-xs text-ink-muted">{w.stage.replace(/_/g, ' ')}</span>
      ),
    },
    {
      key: 'duration',
      header: 'Duration',
      render: (w) => (
        <span className="font-mono text-xs tabular-nums text-ink-subtle">
          {formatDuration(w.duration_ms)}
        </span>
      ),
    },
    {
      key: 'updated',
      header: 'Updated',
      hideBelow: 'lg',
      render: (w) => (
        <span className="whitespace-nowrap font-mono text-xs tabular-nums text-ink-subtle">
          {formatDate(w.updated_at)}
        </span>
      ),
    },
  ];

  if (workflows.loading) return <LoadingState label="Loading workflows…" />;
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
    <PageContainer className="space-y-6">
      <PageHeader
        eyebrow={
          <>
            <span aria-hidden className="h-px w-8 bg-indigo-400/60" />
            <span className="font-mono">Review pipeline telemetry</span>
          </>
        }
        title="Workflow orchestration"
        description="End-to-end lifecycle of every review run — from receiving the trigger through fetch, analysis, generation, and persistence."
      />

      <MetricGrid>
        <MetricCard label="Total runs" value={stats.total} />
        <MetricCard label="Running" value={stats.running} tone="high" />
        <MetricCard label="Completed" value={stats.completed} tone="success" />
        <MetricCard label="Failed" value={stats.failed} tone="critical" />
      </MetricGrid>

      <Card>
        <CardHeader
          title="Execution history"
          actions={
            <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Filter by status">
              {STATUS_FILTERS.map((filter) => (
                <button
                  key={filter}
                  type="button"
                  aria-pressed={statusFilter === filter}
                  onClick={() => setStatusFilter(filter)}
                  className={cn(
                    'rounded-full border px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.14em] transition-all duration-150',
                    statusFilter === filter
                      ? 'border-indigo-400/40 bg-indigo-400/[0.08] text-indigo-200'
                      : 'border-white/[0.06] bg-white/[0.02] text-ink-faint hover:text-ink-muted',
                  )}
                >
                  {filter}
                </button>
              ))}
            </div>
          }
        />
        <CardBody>
          {items.length === 0 ? (
            <EmptyState
              title="No workflows recorded yet"
              description="Trigger a pull request review to see its pipeline stages here."
            />
          ) : (
            <DataTable
              caption="Review workflow runs"
              columns={columns}
              rows={items}
              rowKey={(w) => w.workflow_id}
              onRowClick={(w) => navigate(`/workflows/${w.workflow_id}`)}
            />
          )}
        </CardBody>
      </Card>
    </PageContainer>
  );
}
