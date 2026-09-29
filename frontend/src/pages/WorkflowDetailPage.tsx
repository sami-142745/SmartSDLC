import { Link, useParams } from 'react-router-dom';

import { getWorkflow } from '../api/workflows';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import { PageContainer } from '../components/PageContainer';
import { PageHeader } from '../components/PageHeader';
import { Card, CardBody, CardHeader } from '../components/ui/Card';
import { cn } from '../lib/cn';
import { useAsync } from '../hooks/useAsync';
import type { WorkflowHistoryEntry } from '../types';
import { formatDate } from '../utils/format';

const STAGE_ORDER = [
  'RECEIVED',
  'VALIDATED',
  'FETCHING',
  'ANALYZING',
  'GENERATING_REVIEW',
  'PERSISTING',
  'COMPLETED',
] as const;

const STATUS_STYLE: Record<string, string> = {
  queued: 'border-amber-300/25 bg-amber-300/[0.06] text-amber-200',
  running: 'border-sky-400/25 bg-sky-400/[0.06] text-sky-300',
  completed: 'border-emerald-500/20 bg-emerald-500/[0.06] text-emerald-300',
  failed: 'border-rose-500/25 bg-rose-500/[0.06] text-rose-300',
};

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

function Timestamp({ value }: { value: string | null }) {
  if (!value) return <span className="text-ink-faint">—</span>;
  return (
    <span className="font-mono text-xs tabular-nums text-ink-subtle">{formatDate(value)}</span>
  );
}

function StageRail({ current }: { current: string }) {
  const reached = STAGE_ORDER.indexOf(current as (typeof STAGE_ORDER)[number]);
  return (
    <ol className="flex flex-wrap items-center gap-1.5">
      {STAGE_ORDER.map((stage, index) => {
        const active = index <= reached && current !== 'FAILED';
        const isCurrent = stage === current;
        return (
          <li key={stage} className="flex items-center gap-1.5">
            <span
              className={cn(
                'rounded-full border px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.14em] transition-all duration-150',
                isCurrent
                  ? 'border-indigo-400/50 bg-indigo-400/[0.12] text-indigo-100'
                  : active
                    ? 'border-emerald-500/25 bg-emerald-500/[0.06] text-emerald-300'
                    : 'border-white/[0.05] bg-white/[0.01] text-ink-faint',
              )}
            >
              {stage.replace(/_/g, ' ')}
            </span>
            {index < STAGE_ORDER.length - 1 ? (
              <span aria-hidden className="h-px w-2.5 bg-white/[0.08]" />
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}

function HistoryTimeline({ history }: { history: WorkflowHistoryEntry[] }) {
  if (history.length === 0) {
    return <p className="text-sm text-ink-subtle">No stage transitions recorded for this run.</p>;
  }
  return (
    <ol className="relative space-y-1 border-l border-white/[0.07] pl-6">
      {history.map((entry, index) => (
        <li key={`${entry.stage}-${index}`} className="relative pb-4 last:pb-0">
          <span
            aria-hidden
            className={cn(
              'absolute -left-[29px] top-1.5 h-2 w-2 rounded-full',
              index === history.length - 1 ? 'bg-indigo-400' : 'bg-white/20',
            )}
          />
          <p className="font-mono text-xs uppercase tracking-[0.14em] text-ink-muted">
            {entry.stage.replace(/_/g, ' ')}
          </p>
          <div className="mt-1 flex flex-wrap items-center gap-3">
            <Timestamp value={entry.at} />
            {entry.detail ? <span className="text-xs text-ink">{entry.detail}</span> : null}
          </div>
        </li>
      ))}
    </ol>
  );
}

export function WorkflowDetailPage() {
  const { workflowId } = useParams<{ workflowId: string }>();

  const detail = useAsync(() => getWorkflow(workflowId ?? ''), [workflowId]);

  if (detail.loading) return <LoadingState label="Loading workflow…" />;
  if (detail.error || !detail.data) {
    return (
      <ErrorState
        title="Could not load this workflow"
        message={detail.error ?? undefined}
        retry={detail.refetch}
      />
    );
  }

  const workflow = detail.data;

  return (
    <PageContainer className="space-y-6">
      <Link
        to="/workflows"
        className="group inline-flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.16em] text-ink-faint transition-colors hover:text-ink"
      >
        <span aria-hidden className="transition-transform group-hover:-translate-x-0.5">
          &larr;
        </span>
        Back to workflow runs
      </Link>

      <PageHeader
        eyebrow={
          <>
            <span aria-hidden className="h-px w-8 bg-indigo-400/60" />
            <span className="font-mono">
              {workflow.owner}/{workflow.repository}{' '}
              <span className="text-ink">#{workflow.pull_request_number}</span>
            </span>
          </>
        }
        title="Review workflow"
        description={
          <span className="flex flex-wrap items-center gap-3">
            <StatusChip status={workflow.status} />
            <span className="font-mono text-xs text-ink-muted">
              {workflow.trigger} &middot; {workflow.provider}
            </span>
          </span>
        }
      />

      <Card>
        <CardHeader title="Stage pipeline" />
        <CardBody>
          <StageRail current={workflow.stage} />
          {workflow.error ? (
            <p className="mt-4 rounded-lg border border-rose-500/20 bg-rose-500/[0.05] px-3 py-2 text-xs text-rose-300">
              {workflow.error}
            </p>
          ) : null}
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Stage timeline" />
        <CardBody>
          <HistoryTimeline history={workflow.history} />
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Run metadata" />
        <CardBody>
          <dl className="grid grid-cols-1 gap-x-6 gap-y-3.5 text-sm md:grid-cols-3">
            <div>
              <dt className="eyebrow">Workflow ID</dt>
              <dd className="mt-1 font-mono text-xs text-ink-muted">{workflow.workflow_id}</dd>
            </div>
            <div>
              <dt className="eyebrow">Started</dt>
              <dd className="mt-1">
                <Timestamp value={workflow.created_at} />
              </dd>
            </div>
            <div>
              <dt className="eyebrow">Last updated</dt>
              <dd className="mt-1">
                <Timestamp value={workflow.updated_at} />
              </dd>
            </div>
            <div>
              <dt className="eyebrow">Elapsed</dt>
              <dd className="mt-1 font-mono text-xs text-ink-muted">
                {formatDuration(workflow.duration_ms)}
              </dd>
            </div>
            <div>
              <dt className="eyebrow">Trigger</dt>
              <dd className="mt-1 font-mono text-xs capitalize text-ink-muted">{workflow.trigger}</dd>
            </div>
            <div>
              <dt className="eyebrow">Provider</dt>
              <dd className="mt-1 font-mono text-xs text-ink-muted">{workflow.provider}</dd>
            </div>
            {workflow.review_id ? (
              <div className="md:col-span-3">
                <dt className="eyebrow">Produced review</dt>
                <dd className="mt-1">
                  <Link
                    to={`/reviews/${workflow.owner}/${workflow.repository}/${workflow.pull_request_number}`}
                    className="inline-flex items-center gap-1.5 font-mono text-xs text-indigo-300 transition-colors hover:text-indigo-200"
                  >
                    {workflow.review_id}
                    <span aria-hidden>&rarr;</span>
                  </Link>
                </dd>
              </div>
            ) : null}
          </dl>
        </CardBody>
      </Card>
    </PageContainer>
  );
}
