import { Link, useNavigate, useParams } from 'react-router-dom';

import { getWorkflow } from '../api/workflows';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import { PageContainer } from '../components/PageContainer';
import { Reveal } from '../components/motion/Reveal';
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

function Timestamp({ value }: { value: string | null }) {
  if (!value) return <span className="text-slate-600">—</span>;
  return <span className="font-mono text-xs tabular-nums text-slate-400">{formatDate(value)}</span>;
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
              className={`rounded-full border px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.14em] transition-all ${
                isCurrent
                  ? 'border-indigo-400/50 bg-indigo-400/[0.12] text-indigo-100 shadow-[0_0_16px_-6px_rgba(99,102,241,0.9)]'
                  : active
                    ? 'border-emerald-500/25 bg-emerald-500/[0.06] text-emerald-300'
                    : 'border-white/[0.05] bg-white/[0.01] text-slate-600'
              }`}
            >
              {stage.replace(/_/g, ' ')}
            </span>
            {index < STAGE_ORDER.length - 1 && (
              <span aria-hidden className="h-px w-2.5 bg-white/[0.08]" />
            )}
          </li>
        );
      })}
    </ol>
  );
}

function HistoryTimeline({ history }: { history: WorkflowHistoryEntry[] }) {
  if (history.length === 0) {
    return <p className="text-sm text-slate-500">No stage transitions recorded for this run.</p>;
  }
  return (
    <ol className="relative space-y-1 border-l border-white/[0.07] pl-6">
      {history.map((entry, index) => (
        <li key={`${entry.stage}-${index}`} className="relative pb-4">
          <span
            aria-hidden
            className={`absolute -left-[29px] top-1.5 h-2 w-2 rounded-full ${
              index === history.length - 1 ? 'bg-indigo-400 shadow-[0_0_10px_rgba(99,102,241,0.9)]' : 'bg-slate-600'
            }`}
          />
          <p className="font-mono text-xs uppercase tracking-[0.14em] text-slate-200">
            {entry.stage.replace(/_/g, ' ')}
          </p>
          <div className="mt-1 flex flex-wrap items-center gap-3">
            <Timestamp value={entry.at} />
            {entry.detail && <span className="text-xs text-slate-500">{entry.detail}</span>}
          </div>
        </li>
      ))}
    </ol>
  );
}

export function WorkflowDetailPage() {
  const { workflowId } = useParams<{ workflowId: string }>();
  const navigate = useNavigate();

  const detail = useAsync(() => getWorkflow(workflowId ?? ''), [workflowId]);

  if (detail.loading) return <LoadingState label="Loading workflow\u2026" />;
  if (detail.error || !detail.data) {
    return (
      <ErrorState title="Could not load this workflow" message={detail.error ?? undefined} retry={detail.refetch} />
    );
  }

  const workflow = detail.data;

  return (
    <PageContainer className="space-y-10">
      <Reveal>
        <section className="py-6 lg:py-9">
          <button
            type="button"
            onClick={() => navigate('/workflows')}
            className="group mb-6 inline-flex items-center gap-2 font-mono text-xs uppercase tracking-[0.16em] text-slate-500 transition-colors hover:text-slate-200"
          >
            <span aria-hidden className="transition-transform group-hover:-translate-x-0.5">←</span>
            Back to workflow runs
          </button>

          <p className="hud-tag hud-tag-accent flex items-center gap-3">
            <span aria-hidden className="h-px w-10 bg-indigo-400/60" />
            <span className="font-mono">
              {workflow.owner}/{workflow.repository} <span className="text-slate-500">#{workflow.pull_request_number}</span>
            </span>
          </p>

          <div className="mt-6 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <h1 className="text-[clamp(2.1rem,5.5vw,4.6rem)] font-semibold leading-[1] tracking-[-0.035em] text-slate-50">
                Review workflow
              </h1>
              <p className="mt-5 flex flex-wrap items-center gap-3 text-sm text-slate-400">
                <StatusChip status={workflow.status} />
                <span className="font-mono text-xs text-slate-500">
                  {workflow.trigger} · {workflow.provider}
                </span>
              </p>
            </div>
          </div>
        </section>
      </Reveal>

      <Reveal delay={0.05}>
        <section className="glass-edge block rounded-xl p-5">
          <p className="hud-tag hud-tag-accent mb-4">Stage pipeline</p>
          <StageRail current={workflow.stage} />
          {workflow.error && (
            <p className="mt-4 rounded-lg border border-rose-500/20 bg-rose-500/[0.05] px-3 py-2 text-xs text-rose-300">
              {workflow.error}
            </p>
          )}
        </section>
      </Reveal>

      <Reveal delay={0.1}>
        <section className="glass-edge block rounded-xl p-5">
          <p className="hud-tag hud-tag-accent mb-4">Stage timeline</p>
          <HistoryTimeline history={workflow.history} />
        </section>
      </Reveal>

      <Reveal delay={0.15}>
        <section className="glass-edge block rounded-xl p-5">
          <p className="hud-tag hud-tag-accent mb-4">Run metadata</p>
          <dl className="grid grid-cols-1 gap-x-6 gap-y-3 text-sm md:grid-cols-3">
            <div>
              <dt className="hud-tag block">Workflow ID</dt>
              <dd className="mt-1 font-mono text-xs text-slate-300">{workflow.workflow_id}</dd>
            </div>
            <div>
              <dt className="hud-tag block">Started</dt>
              <dd className="mt-1">
                <Timestamp value={workflow.created_at} />
              </dd>
            </div>
            <div>
              <dt className="hud-tag block">Last updated</dt>
              <dd className="mt-1">
                <Timestamp value={workflow.updated_at} />
              </dd>
            </div>
            <div>
              <dt className="hud-tag block">Elapsed</dt>
              <dd className="mt-1 font-mono text-xs text-slate-300">{formatDuration(workflow.duration_ms)}</dd>
            </div>
            <div>
              <dt className="hud-tag block">Trigger</dt>
              <dd className="mt-1 font-mono text-xs capitalize text-slate-300">{workflow.trigger}</dd>
            </div>
            <div>
              <dt className="hud-tag block">Provider</dt>
              <dd className="mt-1 font-mono text-xs text-slate-300">{workflow.provider}</dd>
            </div>
            {workflow.review_id && (
              <div className="md:col-span-3">
                <dt className="hud-tag block">Produced review</dt>
                <dd className="mt-1">
                  <Link
                    to={`/reviews/${workflow.owner}/${workflow.repository}/${workflow.pull_request_number}`}
                    className="inline-flex items-center gap-2 font-mono text-xs text-indigo-300 transition-colors hover:text-indigo-200"
                  >
                    {workflow.review_id}
                    <span aria-hidden>→</span>
                  </Link>
                </dd>
              </div>
            )}
          </dl>
        </section>
      </Reveal>
    </PageContainer>
  );
}