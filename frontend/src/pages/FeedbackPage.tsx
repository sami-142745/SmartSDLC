import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { getFeedbackHistory } from '../api/reviews';
import { getFeedbackLearning } from '../api/feedback_learning';
import { DataTable } from '../components/DataTable';
import type { Column } from '../components/DataTable';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import { MetricCard, MetricGrid } from '../components/MetricCard';
import { PageContainer } from '../components/PageContainer';
import { PageHeader } from '../components/PageHeader';
import { Pagination } from '../components/Pagination';
import { SeverityBadge } from '../components/SeverityBadge';
import { Card, CardBody, CardHeader } from '../components/ui/Card';
import type {
  FeedbackHistoryResponse,
  FeedbackItem,
  FeedbackLearningResponse,
  LearningProfile,
} from '../types';
import { categoryLabel } from '../utils/severity';
import { formatDate, formatPercent } from '../utils/format';

const PER_PAGE = 20;

function FeedbackAnalytics({ items }: { items: FeedbackItem[] }) {
  const accepted = items.filter((item) => item.action === 'accepted').length;
  const dismissed = items.filter((item) => item.action === 'dismissed').length;
  const total = items.length;
  const rate = total > 0 ? accepted / total : 0;

  return (
    <MetricGrid className="sm:grid-cols-3">
      <MetricCard
        label="Accepted"
        value={String(accepted)}
        tone="success"
        hint={`of ${total} feedback signal${total === 1 ? '' : 's'}`}
        icon={
          <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
            <path d="M20 6 9 17l-5-5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        }
      />
      <MetricCard
        label="Dismissed"
        value={String(dismissed)}
        tone="critical"
        hint="findings judged as false positives"
        icon={
          <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
            <path d="M6 6l12 12M18 6 6 18" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        }
      />
      <MetricCard
        label="Acceptance rate"
        value={formatPercent(rate)}
        tone="default"
        hint="share of findings you kept"
        icon={
          <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
            <path d="M3 17a9 9 0 1 1 18 0M9 17a3 3 0 0 1 6 0" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        }
      />
    </MetricGrid>
  );
}

function LearningSignals({ learning }: { learning: FeedbackLearningResponse | null }) {
  const profiles = learning?.profiles ?? [];

  const columns: Column<LearningProfile>[] = [
    {
      key: 'repository',
      header: 'Repository',
      render: (row) => (
        <span className="font-mono text-sm text-ink-muted">
          {row.owner}/{row.repository}
        </span>
      ),
    },
    {
      key: 'category',
      header: 'Category',
      render: (row) => <span className="text-ink-subtle">{categoryLabel(row.category)}</span>,
    },
    {
      key: 'accepted',
      header: 'Accepted',
      render: (row) => <span className="font-mono text-emerald-300">{row.accepted_count}</span>,
    },
    {
      key: 'dismissed',
      header: 'Dismissed',
      render: (row) => <span className="font-mono text-rose-300">{row.dismissed_count}</span>,
    },
    {
      key: 'acceptance',
      header: 'Acceptance',
      render: (row) => (
        <span className="font-mono tabular-nums text-ink-muted">{formatPercent(row.acceptance_rate)}</span>
      ),
    },
    {
      key: 'weight',
      header: 'Learned weight',
      render: (row) => (
        <span
          className={`chip ${
            row.learned_weight > 1
              ? 'border-emerald-400/30 bg-emerald-400/10 text-emerald-300'
              : row.learned_weight < 1
                ? 'border-amber-400/30 bg-amber-400/10 text-amber-300'
                : 'border-white/10 bg-white/5 text-ink-subtle'
          }`}
        >
          {row.learned_weight.toFixed(2)}x
        </span>
      ),
    },
    {
      key: 'confidence',
      header: 'Confidence',
      render: (row) => (
        <span className="font-mono tabular-nums text-ink-subtle">{formatPercent(row.confidence)}</span>
      ),
    },
    {
      key: 'updated',
      header: 'Last updated',
      render: (row) => (
        <span className="whitespace-nowrap font-mono text-xs text-ink">{formatDate(row.updated_at)}</span>
      ),
    },
  ];

  return (
    <Card>
      <CardHeader
        title="Adaptive review prioritization"
        description="Category-level signals calibrated from accepted and dismissed findings. No stored severity changes — only passive priority weighting."
      />
      <CardBody>
        {learning?.data_available ? (
          <DataTable
            caption="Learned prioritization weights by repository and category"
            columns={columns}
            rows={profiles}
            rowKey={(row) => `${row.owner}:${row.repository}:${row.category}`}
          />
        ) : (
          <EmptyState
            title="No learning signals available yet"
            description="Accept or dismiss findings to calibrate prioritization."
          />
        )}
      </CardBody>
    </Card>
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
    getFeedbackLearning()
      .then(setLearning)
      .catch(() => setLearning(null));
  }, [page]);

  useEffect(() => {
    load();
  }, [load]);

  const columns: Column<FeedbackItem>[] = [
    {
      key: 'pr',
      header: 'Pull request',
      render: (row) => (
        <span className="font-mono text-sm text-ink-muted">
          {row.owner}/{row.repository} #{row.pull_request_number}
        </span>
      ),
    },
    {
      key: 'action',
      header: 'Action',
      render: (row) => (
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
      render: (row) => <SeverityBadge severity={row.severity} />,
    },
    {
      key: 'category',
      header: 'Category',
      render: (row) => <span className="text-ink-subtle">{categoryLabel(row.category)}</span>,
    },
    {
      key: 'finding',
      header: 'Finding',
      render: (row) => <span className="font-mono text-xs text-ink">{row.finding_id}</span>,
    },
    {
      key: 'date',
      header: 'Date',
      render: (row) => (
        <span className="whitespace-nowrap font-mono text-xs text-ink">
          {formatDate(row.updated_at ?? row.created_at)}
        </span>
      ),
    },
  ];

  return (
    <PageContainer className="space-y-6">
      <PageHeader
        eyebrow={
          <>
            <span aria-hidden className="h-px w-8 bg-indigo-400/60" />
            Feedback loop \u00b7 learning layer
          </>
        }
        title="AI learning"
        description="Automated quality signals — which findings you accept or dismiss feed back into the network so every review gets sharper."
      />

      {loading ? (
        <LoadingState label="Loading feedback…" />
      ) : error ? (
        <ErrorState title="Could not load feedback" message={error} retry={load} />
      ) : data && data.items.length === 0 ? (
        <>
          <EmptyState
            title="No feedback yet"
            description="Accept or dismiss findings on a review to see them here."
          />
          <LearningSignals learning={learning} />
        </>
      ) : data ? (
        <>
          <FeedbackAnalytics items={data.items} />

          <Card>
            <CardHeader
              title="Feedback ledger"
              description="Review signals and human corrections, in sequence."
              actions={
                <span className="font-mono text-[11.5px] tabular-nums text-ink-faint">
                  {data.total} total
                </span>
              }
            />
            <CardBody>
              <DataTable
                caption="Accepted and dismissed findings across recent reviews"
                columns={columns}
                rows={data.items}
                rowKey={(row) => `${row.review_id}:${row.finding_id}`}
                onRowClick={(row) =>
                  navigate(`/reviews/${row.owner}/${row.repository}/${row.pull_request_number}`)
                }
              />
            </CardBody>
          </Card>

          <Pagination
            page={page}
            perPage={PER_PAGE}
            total={data.total}
            totalPages={data.total_pages}
            onPageChange={setPage}
          />

          <LearningSignals learning={learning} />
        </>
      ) : null}
    </PageContainer>
  );
}
