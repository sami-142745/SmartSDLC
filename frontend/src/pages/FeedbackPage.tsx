import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { getFeedbackHistory } from '../api/reviews';
import { getFeedbackLearning } from '../api/feedback_learning';
import { DataTable } from '../components/DataTable';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import { PageContainer } from '../components/PageContainer';
import { Pagination } from '../components/Pagination';
import { SeverityBadge } from '../components/SeverityBadge';
import { Reveal } from '../components/motion/Reveal';
import type { FeedbackHistoryResponse, FeedbackItem, FeedbackLearningResponse, LearningProfile } from '../types';
import { categoryLabel } from '../utils/severity';
import { formatDate, formatPercent } from '../utils/format';

const PER_PAGE = 20;

function FeedbackAnalytics({ items }: { items: FeedbackItem[] }) {
  const accepted = items.filter((item) => item.action === 'accepted').length;
  const dismissed = items.filter((item) => item.action === 'dismissed').length;
  const total = items.length;
  const rate = total > 0 ? accepted / total : 0;

  const stats = [
    {
      label: 'Accepted',
      value: String(accepted),
      tone: 'text-emerald-300',
      code: 'ACC',
      icon: (
        <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
          <path d="M20 6 9 17l-5-5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      ),
      chip: 'border-emerald-400/25 bg-emerald-400/10 text-emerald-300',
    },
    {
      label: 'Dismissed',
      value: String(dismissed),
      tone: 'text-rose-300',
      code: 'DIS',
      icon: (
        <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
          <path d="M6 6l12 12M18 6 6 18" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      ),
      chip: 'border-rose-400/25 bg-rose-400/10 text-rose-300',
    },
    {
      label: 'Acceptance rate',
      value: formatPercent(rate),
      tone: 'text-accent-indigo',
      code: 'RATE',
      icon: (
        <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
          <path d="M3 17a9 9 0 1 1 18 0M9 17a3 3 0 0 1 6 0" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      ),
      chip: 'border-accent-indigo/25 bg-accent-indigo/10 text-accent-indigo',
    },
  ];

  return (
    <div className="relative grid grid-cols-1 gap-4 sm:grid-cols-3">
      {stats.map((stat) => (
        <div
          key={stat.label}
          className="group holo-panel holo-panel-press flex items-center gap-4 p-5"
        >
          <span className={`relative flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border transition-transform duration-150 group-hover:-translate-y-0.5 ${stat.chip}`}>
            {stat.icon}
          </span>
          <div className="min-w-0">
            <p className="font-mono text-[9px] font-semibold uppercase tracking-[0.22em] text-slate-500">
              {stat.code} · {stat.label}
            </p>
            <p className={`mt-1 font-mono text-3xl font-semibold tabular-nums leading-none tracking-tight ${stat.tone}`}>
              {stat.value}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}

function LearningSignals({ learning }: { learning: FeedbackLearningResponse | null }) {
  const profiles = learning?.profiles ?? [];

  const columns = [
    {
      key: 'repository',
      header: 'Repository',
      render: (row: LearningProfile) => (
        <span className="font-mono text-sm text-slate-200">
          {row.owner}/{row.repository}
        </span>
      ),
    },
    {
      key: 'category',
      header: 'Category',
      render: (row: LearningProfile) => (
        <span className="text-slate-400">{categoryLabel(row.category)}</span>
      ),
    },
    {
      key: 'accepted',
      header: 'Accepted',
      render: (row: LearningProfile) => (
        <span className="font-mono text-emerald-300">{row.accepted_count}</span>
      ),
    },
    {
      key: 'dismissed',
      header: 'Dismissed',
      render: (row: LearningProfile) => (
        <span className="font-mono text-rose-300">{row.dismissed_count}</span>
      ),
    },
    {
      key: 'acceptance',
      header: 'Acceptance',
      render: (row: LearningProfile) => (
        <span className="font-mono tabular-nums text-slate-300">
          {formatPercent(row.acceptance_rate)}
        </span>
      ),
    },
    {
      key: 'weight',
      header: 'Learned weight',
      render: (row: LearningProfile) => (
        <span
          className={`chip ${
            row.learned_weight > 1
              ? 'border-emerald-400/30 bg-emerald-400/10 text-emerald-300'
              : row.learned_weight < 1
                ? 'border-amber-400/30 bg-amber-400/10 text-amber-300'
                : 'border-white/10 bg-white/5 text-slate-400'
          }`}
        >
          {row.learned_weight.toFixed(2)}x
        </span>
      ),
    },
    {
      key: 'confidence',
      header: 'Confidence',
      render: (row: LearningProfile) => (
        <span className="font-mono tabular-nums text-slate-400">
          {formatPercent(row.confidence)}
        </span>
      ),
    },
    {
      key: 'updated',
      header: 'Last updated',
      render: (row: LearningProfile) => (
        <span className="whitespace-nowrap font-mono text-xs text-slate-500">
          {formatDate(row.updated_at)}
        </span>
      ),
    },
  ];

  return (
    <div className="holo-panel">
      <div className="border-b border-white/[0.06] px-5 py-4">
        <p className="hud-tag hud-tag-accent">Adaptive review prioritization</p>
        <p className="mt-1 text-sm text-slate-400">
          Category-level signals calibrated from accepted and dismissed findings.
          No stored severity changes — only passive priority weighting.
        </p>
      </div>
      <div className="p-5">
        {!learning?.data_available ? (
          <p className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-4 py-8 text-center font-mono text-xs uppercase tracking-[0.2em] text-slate-500">
            No learning signals available yet — accept or dismiss findings to calibrate prioritization.
          </p>
        ) : (
          <DataTable columns={columns} rows={profiles} rowKey={(row) => `${row.owner}:${row.repository}:${row.category}`} />
        )}
      </div>
    </div>
  );
}

export function FeedbackPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [data, setData] = useState<FeedbackHistoryResponse | null>(null);
  const [learning, setLearning] = useState<FeedbackLearningResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    getFeedbackHistory(page, PER_PAGE)
      .then(setData)
      .catch((err) => setError((err as { message?: string }).message ?? 'Could not load feedback.'))
      .finally(() => setLoading(false));
    getFeedbackLearning().then(setLearning).catch(() => setLearning(null));
  }, [page]);

  useEffect(() => {
    load();
  }, [load]);

  const columns = [
    {
      key: 'pr',
      header: 'Pull request',
      render: (row: FeedbackItem) => (
        <span className="font-mono text-sm text-slate-200">
          {row.owner}/{row.repository} #{row.pull_request_number}
        </span>
      ),
    },
    {
      key: 'action',
      header: 'Action',
      render: (row: FeedbackItem) => (
        <span
          className={`chip ${
            row.action === 'accepted'
              ? 'border-emerald-400/30 bg-emerald-400/10 text-emerald-300'
              : 'border-rose-400/30 bg-rose-400/10 text-rose-300'
          }`}
        >
          {row.action}
        </span>
      ),
    },
    {
      key: 'severity',
      header: 'Severity',
      render: (row: FeedbackItem) => <SeverityBadge severity={row.severity} />,
    },
    {
      key: 'category',
      header: 'Category',
      render: (row: FeedbackItem) => (
        <span className="text-slate-400">{categoryLabel(row.category)}</span>
      ),
    },
    {
      key: 'finding',
      header: 'Finding',
      render: (row: FeedbackItem) => (
        <span className="font-mono text-xs text-slate-500">{row.finding_id}</span>
      ),
    },
    {
      key: 'date',
      header: 'Date',
      render: (row: FeedbackItem) => (
        <span className="whitespace-nowrap font-mono text-xs text-slate-500">
          {formatDate(row.updated_at ?? row.created_at)}
        </span>
      ),
    },
  ];

  return (
    <PageContainer className="space-y-10">
      {/* Neural learning sweep header */}
      <section className="py-6 lg:py-9">
        <p className="hud-tag hud-tag-accent flex items-center gap-3">
          <span aria-hidden className="h-px w-10 bg-indigo-400/60" />
          Feedback loop · learning layer
        </p>
        <h1 className="hero-display mt-4 text-slate-50">
          <span className="block">AI</span>
          <span className="h-grad block">LEARNING</span>
        </h1>
        <p className="mt-5 max-w-md text-sm leading-relaxed text-slate-400">
          Automated quality signals — which findings you accept or dismiss
          feed back into the network so every review gets sharper.
        </p>
      </section>

      {loading ? (
        <LoadingState label="Loading feedback\u2026" />
      ) : error ? (
        <ErrorState title="Could not load feedback" message={error} retry={load} />
      ) : data && data.items.length === 0 ? (
        <>
          <EmptyState
            title="No feedback yet"
            description="Accept or dismiss findings on a review to see them here."
          />
          <Reveal>
            <LearningSignals learning={learning} />
          </Reveal>
        </>
      ) : data ? (
        <>
          <Reveal>
            <FeedbackAnalytics items={data.items} />
          </Reveal>
          <Reveal delay={90}>
            <div className="holo-panel">
              <div className="border-b border-white/[0.06] px-5 py-4">
                <p className="hud-tag hud-tag-accent">Neural ledger</p>
                <p className="mt-1 text-sm text-slate-400">
                  Review signals and human corrections, in sequence.
                </p>
              </div>
              <div className="p-5">
                <DataTable
                  columns={columns}
                  rows={data.items}
                  rowKey={(row) => `${row.review_id}:${row.finding_id}`}
                  onRowClick={(row) =>
                    navigate(`/reviews/${row.owner}/${row.repository}/${row.pull_request_number}`)
                  }
                />
              </div>
            </div>
          </Reveal>
          <Pagination
            page={page}
            perPage={PER_PAGE}
            total={data.total}
            totalPages={data.total_pages}
            onPageChange={setPage}
          />
          <Reveal>
            <LearningSignals learning={learning} />
          </Reveal>
        </>
      ) : null}
    </PageContainer>
  );
}