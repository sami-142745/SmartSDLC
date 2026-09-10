import { useNavigate } from 'react-router-dom';

import { getDashboard, getFeedbackSummary, getRepositoryMetrics } from '../api/dashboard';
import { SeverityPieChart } from '../components/Charts/SeverityPieChart';
import { CategoryBarChart as CategoryChart } from '../components/Charts/CategoryBarChart';
import { DataTable } from '../components/DataTable';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import { MetricCard, MetricGrid } from '../components/MetricCard';
import { SeverityBadge } from '../components/SeverityBadge';
import { StateBadge } from '../components/Badge';
import { useAsync } from '../hooks/useAsync';
import type { RecentReview, RepositoryMetric } from '../types';
import { formatCount, formatDate, formatPercent } from '../utils/format';

export function DashboardPage() {
  const navigate = useNavigate();

  const dashboard = useAsync(() => getDashboard(), []);
  const feedback = useAsync(() => getFeedbackSummary(), []);
  const repos = useAsync(() => getRepositoryMetrics(1, 10), []);

  if (dashboard.loading) return <LoadingState label="Loading dashboard…" />;
  if (dashboard.error || !dashboard.data) {
    return <ErrorState title="Could not load the dashboard" message={dashboard.error ?? undefined} retry={dashboard.refetch} />;
  }

  const summary = dashboard.data;
  const feedbackSummary = feedback.data;

  const recentColumns = [
    {
      key: 'pr',
      header: 'Pull request',
      render: (row: RecentReview) => (
        <div>
          <span className="font-medium text-slate-900">
            {row.owner}/{row.repository} #{row.pull_request_number}
          </span>
          {row.pull_request_title && (
            <span className="block text-xs text-slate-500">{row.pull_request_title}</span>
          )}
        </div>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (row: RecentReview) => <StateBadge state={row.status} />,
    },
    {
      key: 'findings',
      header: 'Findings',
      render: (row: RecentReview) => (
        <span className="tabular-nums font-medium text-slate-700">{row.total_finding_count}</span>
      ),
    },
    {
      key: 'score',
      header: 'Score',
      render: (row: RecentReview) => (
        <span className="tabular-nums">{row.review_score != null ? row.review_score : '—'}</span>
      ),
    },
    {
      key: 'severity',
      header: 'Severity',
      render: (row: RecentReview) => <SeverityBadge severity={row.review_severity} />,
    },
    {
      key: 'date',
      header: 'Reviewed',
      render: (row: RecentReview) => <span className="whitespace-nowrap">{formatDate(row.created_at)}</span>,
    },
  ];

  const repoColumns = [
    {
      key: 'repo',
      header: 'Repository',
      render: (row: RepositoryMetric) => (
        <span className="font-medium text-slate-900">
          {row.owner}/{row.repository}
        </span>
      ),
    },
    {
      key: 'reviews',
      header: 'Reviews',
      render: (row: RepositoryMetric) => <span className="tabular-nums">{row.review_count}</span>,
    },
    {
      key: 'findings',
      header: 'Findings',
      render: (row: RepositoryMetric) => <span className="tabular-nums">{row.finding_count}</span>,
    },
    {
      key: 'critical',
      header: 'Critical',
      render: (row: RepositoryMetric) => (
        <span className="tabular-nums font-medium text-red-700">{row.critical_count}</span>
      ),
    },
    {
      key: 'avg',
      header: 'Avg / review',
      render: (row: RepositoryMetric) => (
        <span className="tabular-nums">{row.average_findings_per_review.toFixed(1)}</span>
      ),
    },
    {
      key: 'last',
      header: 'Last review',
      render: (row: RepositoryMetric) => (
        <span className="whitespace-nowrap text-slate-500">{formatDate(row.last_review_at)}</span>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Dashboard</h1>
        <p className="mt-1 text-sm text-slate-500">
          An overview of your reviewed pull requests and findings.
        </p>
      </div>

      <MetricGrid>
        <MetricCard label="Total reviews" value={formatCount(summary.total_reviews)} />
        <MetricCard label="Total findings" value={formatCount(summary.total_findings)} />
        <MetricCard label="Critical findings" value={formatCount(summary.critical_findings)} tone="critical" />
        <MetricCard label="High findings" value={formatCount(summary.high_findings)} tone="high" />
        <MetricCard label="Reviews today" value={formatCount(summary.reviews_today)} />
        <MetricCard
          label="Acceptance rate"
          value={feedbackSummary ? formatPercent(feedbackSummary.acceptance_rate) : '—'}
          tone="success"
          hint={feedbackSummary ? `${feedbackSummary.total_accepted} of ${feedbackSummary.total_feedback}` : undefined}
        />
      </MetricGrid>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
            Findings by severity
          </h2>
          <SeverityPieChart data={summary.severity_distribution} />
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
            Findings by category
          </h2>
          <CategoryChart data={summary.category_distribution} />
        </div>
      </div>

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-500">
          Recent reviews
        </h2>
        {summary.recent_reviews.length === 0 ? (
          <EmptyState
            title="No reviews yet"
            description="Run your first AI review from a pull request page."
          />
        ) : (
          <DataTable
            columns={recentColumns}
            rows={summary.recent_reviews}
            rowKey={(row) => `${row.owner}/${row.repository}/${row.pull_request_number}`}
            onRowClick={(row) =>
              navigate(`/reviews/${row.owner}/${row.repository}/${row.pull_request_number}`)
            }
          />
        )}
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-500">
          Repositories
        </h2>
        {repos.data && repos.data.repositories.length > 0 ? (
          <DataTable
            columns={repoColumns}
            rows={repos.data.repositories}
            rowKey={(row) => `${row.owner}/${row.repository}`}
            onRowClick={(row) => navigate(`/repositories/${row.owner}/${row.repository}`)}
          />
        ) : (
          <EmptyState
            title="No repository metrics yet"
            description="Metrics appear after the first review."
          />
        )}
      </section>
    </div>
  );
}