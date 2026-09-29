import { Link } from 'react-router-dom';

import { getDashboard, getFeedbackSummary, getRepositoryMetrics } from '../api/dashboard';
import { getInsights } from '../api/insights';
import { Card, CardBody, CardHeader } from '../components/ui/Card';
import { MetricCard, MetricGrid } from '../components/MetricCard';
import { ErrorState } from '../components/ErrorState';
import { EmptyState } from '../components/EmptyState';
import { LoadingState } from '../components/LoadingState';
import { PageContainer } from '../components/PageContainer';
import { PageHeader } from '../components/PageHeader';
import { SeverityPieChart } from '../components/Charts/SeverityPieChart';
import { CategoryBarChart } from '../components/Charts/CategoryBarChart';
import { BarList } from '../components/ui/Charts';
import { ScoreGauge, scoreTone } from '../components/ui/ScoreGauge';
import { SeverityBadge } from '../components/SeverityBadge';
import { useAsync } from '../hooks/useAsync';
import { categoryLabel, severityLabel, SEVERITY_ORDER } from '../utils/severity';
import { formatPercent, formatShortDate } from '../utils/format';
import type { InsightListResponse } from '../types';

export function DashboardPage() {
  const dashboard = useAsync(() => getDashboard(), []);
  const feedback = useAsync(() => getFeedbackSummary(), []);
  const metrics = useAsync(() => getRepositoryMetrics(1, 8), []);
  const insights = useAsync<InsightListResponse>(() => getInsights({ page: 1, perPage: 5 }), []);

  if (dashboard.loading) return <LoadingState label="Loading the dashboard" />;

  if (dashboard.error) {
    return (
      <ErrorState
        title="Could not load the dashboard"
        message={dashboard.error}
        retry={dashboard.refetch}
      />
    );
  }

  const summary = dashboard.data;
  if (!summary) return null;

  const recent = summary.recent_reviews ?? [];
  const topRepos = [...(metrics.data?.repositories ?? [])]
    .sort((a, b) => b.finding_count - a.finding_count)
    .slice(0, 6)
    .map((repo) => ({
      key: `${repo.owner}/${repo.repository}`,
      label: `${repo.owner}/${repo.repository}`,
      value: repo.finding_count,
      color: repo.critical_count > 0 ? '#FB7185' : '#22D3EE',
    }));

  const latestInsight = insights.data?.items?.[0] ?? null;
  const score = summary.total_reviews > 0
    ? Math.max(0, Math.min(100, 100 - summary.critical_findings * 4 - summary.high_findings * 2))
    : 100;

  return (
    <PageContainer className="space-y-6">
      <PageHeader
        eyebrow="Overview"
        title="Dashboard"
        description="Everything SmartSDLC has observed across your connected repositories, updated on every completed review."
        actions={
          <Link to="/pull-requests" className="btn btn-secondary">
            Open pull requests
          </Link>
        }

      />

      <MetricGrid>
        <MetricCard
          label="Total reviews"
          value={summary.total_reviews}
          hint={`${summary.reviews_today} today`}
          icon={<IconChart />}
        />
        <MetricCard
          label="Total findings"
          value={summary.total_findings}
          hint={`${summary.average_findings_per_review.toFixed(1)} per review`}
          icon={<IconList />}
        />
        <MetricCard
          label="Critical findings"
          value={summary.critical_findings}
          tone="critical"
          hint={`${summary.high_findings} high`}
          icon={<IconShield />}
        />
        <MetricCard
          label="Acceptance rate"
          value={formatPercent(feedback.data?.acceptance_rate ?? 0)}
          tone="success"
          hint={`${feedback.data?.total_feedback ?? 0} decisions`}
          icon={<IconCheck />}
        />
      </MetricGrid>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader title="Health score" description="Weighted across all reviews" />
          <CardBody className="flex flex-col items-center gap-4">
            <ScoreGauge score={score} size={168} thickness={13} label="Health score" caption="of 100" />
            <div className="flex flex-wrap justify-center gap-1.5">
              {SEVERITY_ORDER.map((severity) => {
                const count = summary.severity_distribution[severity] ?? 0;
                if (count === 0) return null;
                return (
                  <span
                    key={severity}
                    className="chip border-white/[0.08] bg-white/[0.04] text-ink-subtle"
                  >
                    {severityLabel(severity)} {count}
                  </span>
                );
              })}
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Severity mix" description="Findings by severity band" />
          <CardBody>
            <SeverityPieChart data={summary.severity_distribution} />
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Category breakdown" description="Where findings concentrate" />
          <CardBody>
            {Object.keys(summary.category_distribution).length > 0 ? (
              <CategoryBarChart data={summary.category_distribution} />
            ) : (
              <EmptyState title="No categories yet" description="Run a review to populate this chart." />
            )}
          </CardBody>
        </Card>
      </div>

      <Card>
        <CardHeader
          title="Recent reviews"
          description="The last completed reviews across your repositories"
          actions={
            <Link to="/history" className="btn btn-ghost">
              View all
            </Link>
          }
        />
        <CardBody>
          {recent.length === 0 ? (
            <EmptyState
              title="No reviews yet"
              description="Open a pull request and run an AI review to see it here."
              action={
                <Link to="/pull-requests" className="btn btn-primary">
                  Browse pull requests
                </Link>
              }
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="t-table">
                <thead>
                  <tr>
                    <th>Repository</th>
                    <th className="hidden sm:table-cell">Pull request</th>
                    <th>Findings</th>
                    <th className="hidden md:table-cell">Severity</th>
                    <th className="text-right">Score</th>
                    <th className="hidden lg:table-cell text-right">Reviewed</th>
                  </tr>
                </thead>
                <tbody>
                  {recent.map((review) => {
                    const href = `/reviews/${review.owner}/${review.repository}/${review.pull_request_number}`;
                    const scoreValue = review.review_score ?? 0;
                    return (
                      <tr key={`${review.owner}/${review.repository}#${review.pull_request_number}`}>
                        <td>
                          <Link
                            to={href}
                            className="font-mono text-[12.5px] text-ink-muted hover:text-ink"
                          >
                            {review.owner}/{review.repository}
                          </Link>
                        </td>
                        <td className="hidden sm:table-cell">
                          <Link to={href} className="truncate text-[13px] text-ink hover:text-accent-lavender">
                            {review.pull_request_title ?? `Pull request #${review.pull_request_number}`}
                          </Link>
                        </td>
                        <td className="tabular-nums text-[13px] text-ink-muted">
                          {review.total_finding_count}
                        </td>
                        <td className="hidden md:table-cell">
                          <SeverityBadge severity={review.review_severity} />
                        </td>
                        <td className="text-right">
                          <span
                            className="font-mono text-[13px] tabular-nums"
                            style={{ color: TONE_COLOR[scoreTone(scoreValue)] }}
                          >
                            {scoreValue}
                          </span>
                        </td>
                        <td className="hidden lg:table-cell text-right font-mono text-[11.5px] text-ink-faint">
                          {formatShortDate(review.created_at)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardBody>
      </Card>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="Repositories by findings" description="Highest finding volume first" />
          <CardBody>
            {topRepos.length > 0 ? (
              <BarList data={topRepos} />
            ) : (
              <EmptyState title="No repository metrics yet" />
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Latest insight"
            description="Repository-level trend and risk narrative"
            actions={
              <Link to="/insights" className="btn btn-ghost">
                Open
              </Link>
            }
          />
          <CardBody>
            {latestInsight ? (
              <div className="space-y-3">
                <div>
                  <p className="font-mono text-[12px] text-ink-muted">
                    {latestInsight.owner}/{latestInsight.repository}
                  </p>
                  <p className="mt-1.5 text-[13px] leading-relaxed text-ink-subtle">
                    {latestInsight.narrative?.executive_summary ?? 'No executive summary available.'}
                  </p>
                </div>
                {latestInsight.recommendations.length > 0 ? (
                  <ul className="space-y-1.5">
                    {latestInsight.recommendations.slice(0, 3).map((rec, index) => (
                      <li key={index} className="flex items-start gap-2 text-[12.5px] text-ink-subtle">
                        <span aria-hidden className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-accent-violet" />
                        {rec.message}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
            ) : (
              <EmptyState
                title="No insight reports yet"
                description="Generate an insight report to see trend and risk analysis here."
                action={
                  <Link to="/insights" className="btn btn-secondary">
                    Generate insight
                  </Link>
                }
              />
            )}
          </CardBody>
        </Card>
      </div>
    </PageContainer>
  );
}

const TONE_COLOR: Record<string, string> = {
  good: '#34D399',
  warn: '#FBBF24',
  bad: '#FB7185',
  neutral: '#A1A1AA',
};

function IconChart() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-full w-full" aria-hidden="true">
      <path d="M4 19V5m0 14h16M8 15l3.5-4 3 2.5L20 7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function IconList() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-full w-full" aria-hidden="true">
      <path d="M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01" strokeLinecap="round" />
    </svg>
  );
}

function IconShield() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-full w-full" aria-hidden="true">
      <path d="M12 3l7 3v5.5c0 4.2-2.9 7.9-7 9.5-4.1-1.6-7-5.3-7-9.5V6l7-3Z" strokeLinejoin="round" />
    </svg>
  );
}

function IconCheck() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-full w-full" aria-hidden="true">
      <path d="m5 13 4 4 10-10" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
