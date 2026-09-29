import { useState } from 'react';

import { getRepositories } from '../api/github';
import { generateInsight, getInsights } from '../api/insights';
import { CategoryBarChart } from '../components/Charts/CategoryBarChart';
import { SeverityPieChart } from '../components/Charts/SeverityPieChart';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import { MetricCard, MetricGrid } from '../components/MetricCard';
import { PageContainer } from '../components/PageContainer';
import { PageHeader } from '../components/PageHeader';
import { StateBadge } from '../components/Badge';
import { Button } from '../components/ui/Button';
import { Card, CardBody, CardHeader } from '../components/ui/Card';
import { cn } from '../lib/cn';
import { useAsync } from '../hooks/useAsync';
import type { InsightReport, InsightTrend } from '../types';
import { formatDate, formatPercent } from '../utils/format';
import { SEVERITY_CHART_COLORS } from '../utils/severity';

const SEVERITY_ORDER = ['critical', 'high', 'medium', 'low', 'info'] as const;
const SEVERITY_LABEL: Record<string, string> = {
  critical: 'Critical',
  high: 'High',
  medium: 'Medium',
  low: 'Low',
  info: 'Info',
};

const TREND_DOT: Record<string, string> = {
  increasing: 'bg-rose-400',
  decreasing: 'bg-emerald-400',
  stable: 'bg-cyan-300',
  insufficient: 'bg-ink-faint',
};

const PRIORITY_STYLE: Record<string, string> = {
  high: 'border-rose-400/30 bg-rose-400/[0.06] text-rose-300',
  medium: 'border-amber-300/30 bg-amber-300/[0.06] text-amber-200',
  low: 'border-white/10 bg-white/[0.02] text-ink-muted',
};

function TrendRow({ trend }: { trend: InsightTrend }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-white/[0.04] py-2.5 last:border-b-0">
      <div className="flex min-w-0 items-center gap-2.5">
        <span
          aria-hidden
          className={cn('h-1.5 w-1.5 shrink-0 rounded-full', TREND_DOT[trend.status] ?? 'bg-ink-faint')}
        />
        <span className="truncate text-sm capitalize text-ink-muted">
          {trend.metric.replace(/_/g, ' ')}
        </span>
      </div>
      <div className="flex shrink-0 items-center gap-3 font-mono text-xs">
        <span className="tabular-nums text-ink">
          {trend.earlier} &rarr; {trend.later}
        </span>
        <span className="w-24 text-right capitalize text-ink-subtle">{trend.status}</span>
      </div>
    </div>
  );
}

function MiniStat({ value, label }: { value: string | number; label: string }) {
  return (
    <div>
      <p className="font-mono text-xl font-semibold tabular-nums text-ink">{value}</p>
      <p className="eyebrow mt-0.5">{label}</p>
    </div>
  );
}

function InsightView({ report }: { report: InsightReport }) {
  const { metrics, activity, feedback, trends, risks, recommendations, narrative } = report;
  const triggeredRisks = risks.filter((risk) => risk.triggered);

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader
          title={
            <span className="text-[15px] font-semibold normal-case tracking-normal">
              {report.owner}/{report.repository}
            </span>
          }
          description={
            <span className="font-mono">
              {report.report_type === 'pull_request'
                ? `Pull request #${report.pull_request}`
                : 'Repository-wide'}
              {report.model ? ` \u00b7 ${report.model}` : ' \u00b7 rule-based'}
            </span>
          }
          actions={
            <div className="flex items-center gap-2">
              <span className="chip font-mono uppercase tracking-[0.14em]">{report.report_type}</span>
              <StateBadge state={report.status} />
            </div>
          }
        />
        <CardBody>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-3 md:grid-cols-4">
            <div>
              <dt className="eyebrow">Generated</dt>
              <dd className="mt-1 font-mono text-xs text-ink-subtle">{formatDate(report.generated_at)}</dd>
            </div>
            <div>
              <dt className="eyebrow">Reviews analyzed</dt>
              <dd className="mt-1 font-mono text-xs text-ink-subtle">{report.source_review_ids.length}</dd>
            </div>
            <div>
              <dt className="eyebrow">Duration</dt>
              <dd className="mt-1 font-mono text-xs text-ink-subtle">
                {report.duration_ms != null ? `${report.duration_ms} ms` : '—'}
              </dd>
            </div>
            <div>
              <dt className="eyebrow">Feedback acceptance</dt>
              <dd className="mt-1 font-mono text-xs text-ink-subtle">
                {feedback.total_feedback > 0 ? formatPercent(feedback.acceptance_rate) : '—'}
              </dd>
            </div>
          </dl>
        </CardBody>
      </Card>

      {report.status === 'failed' ? (
        <ErrorState title="Insight generation failed" message={report.error ?? undefined} />
      ) : (
        <>
          {narrative ? (
            <div className="space-y-4">
              <NarrativeBlock title="Executive summary" body={narrative.executive_summary} />
              <NarrativeBlock title="Trend interpretation" body={narrative.trend_interpretation} />
              <NarrativeBlock title="Risk explanation" body={narrative.risk_explanation} />
              {narrative.recommendations.length > 0 ? (
                <Card>
                  <CardHeader title="Narrative recommendations" />
                  <CardBody>
                    <ul className="space-y-2">
                      {narrative.recommendations.map((item) => (
                        <li key={item} className="flex items-start gap-2.5 text-sm leading-relaxed text-ink-subtle">
                          <span aria-hidden className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-accent-indigo" />
                          <span>{item}</span>
                        </li>
                      ))}
                    </ul>
                  </CardBody>
                </Card>
              ) : null}
            </div>
          ) : null}

          <MetricGrid>
            <MetricCard label="Total findings" value={metrics.total_findings} />
            <MetricCard label="Critical" value={metrics.critical_findings} tone="critical" />
            <MetricCard label="Security" value={metrics.security_findings} tone="high" />
            <MetricCard
              label="Findings / review"
              value={metrics.average_findings_per_review.toFixed(2)}
              tone="default"
            />
          </MetricGrid>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader title="Severity mix" />
              <CardBody>
                <div className="flex items-center justify-center">
                  <SeverityPieChart data={metrics.severity_distribution} height={220} />
                </div>
                <div className="mt-4 flex flex-wrap justify-center gap-2">
                  {SEVERITY_ORDER.filter((s) => (metrics.severity_distribution[s] ?? 0) > 0).map((s) => (
                    <span key={s} className="chip font-mono uppercase tracking-[0.14em]">
                      <span
                        aria-hidden
                        className="h-1.5 w-1.5 rounded-full"
                        style={{ background: SEVERITY_CHART_COLORS[s] }}
                      />
                      {SEVERITY_LABEL[s]} {metrics.severity_distribution[s]}
                    </span>
                  ))}
                </div>
              </CardBody>
            </Card>

            <Card>
              <CardHeader title="Category clustering" />
              <CardBody>
                <CategoryBarChart data={metrics.category_distribution} height={220} />
                {metrics.recurring_categories.length > 0 ? (
                  <div className="mt-4 flex flex-wrap items-center gap-1.5">
                    <span className="eyebrow mr-1">Recurring</span>
                    {metrics.recurring_categories.map((cat) => (
                      <span key={cat} className="chip font-mono uppercase tracking-[0.14em]">
                        {cat}
                      </span>
                    ))}
                  </div>
                ) : null}
              </CardBody>
            </Card>
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader title="Activity" />
              <CardBody>
                <div className="grid grid-cols-3 gap-3">
                  <MiniStat value={activity.review_count} label="Reviews" />
                  <MiniStat value={activity.pull_request_count} label="Pull requests" />
                  <MiniStat value={activity.reviews_this_week} label="This week" />
                </div>
                {activity.reviews_over_time.length > 0 ? (
                  <div className="mt-4 border-t border-white/[0.06] pt-3">
                    {activity.reviews_over_time.map((point) => (
                      <div
                        key={point.period}
                        className="flex items-center justify-between gap-3 py-1.5 font-mono text-xs"
                      >
                        <span className="text-ink">{point.period}</span>
                        <span className="tabular-nums text-ink-muted">
                          {point.reviews} reviews &middot; {point.findings} findings
                        </span>
                      </div>
                    ))}
                  </div>
                ) : null}
              </CardBody>
            </Card>

            <Card>
              <CardHeader title="Human feedback loop" />
              <CardBody>
                <div className="grid grid-cols-3 gap-3">
                  <MiniStat value={feedback.total_accepted} label="Accepted" />
                  <MiniStat value={feedback.total_dismissed} label="Dismissed" />
                  <MiniStat
                    value={feedback.total_feedback > 0 ? formatPercent(feedback.acceptance_rate) : '—'}
                    label="Acceptance"
                  />
                </div>
                {feedback.total_feedback === 0 ? (
                  <p className="mt-3 text-xs text-ink-subtle">
                    No accepted/dismissed decisions recorded yet — decisions appear as you triage findings.
                  </p>
                ) : null}
              </CardBody>
            </Card>
          </div>

          <Card>
            <CardHeader
              title="Trajectory"
              description="Later window vs early window across the review timeline."
            />
            <CardBody>
              {trends.length > 0 ? (
                trends.map((trend) => <TrendRow key={trend.metric} trend={trend} />)
              ) : (
                <p className="text-sm text-ink-subtle">Not enough history to compare.</p>
              )}
            </CardBody>
          </Card>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader title="Risk signals" />
              <CardBody>
                {triggeredRisks.length > 0 ? (
                  <div className="space-y-2.5">
                    {triggeredRisks.map((risk) => {
                      const color =
                        SEVERITY_CHART_COLORS[risk.severity as keyof typeof SEVERITY_CHART_COLORS] ??
                        '#94a3b8';
                      return (
                        <div
                          key={risk.key}
                          className="flex items-start gap-2.5 rounded-lg border border-white/[0.05] bg-surface-1/60 px-3.5 py-3"
                        >
                          <span
                            aria-hidden
                            className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full"
                            style={{ background: color }}
                          />
                          <div className="min-w-0">
                            <p className="text-sm font-medium text-ink">{risk.label}</p>
                            <p className="mt-0.5 text-xs leading-relaxed text-ink-subtle">{risk.detail}</p>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p className="text-sm text-ink-subtle">No active risk signals across this scope.</p>
                )}
              </CardBody>
            </Card>

            <Card>
              <CardHeader title="Recommended actions" />
              <CardBody>
                {recommendations.length > 0 ? (
                  <ul className="space-y-2.5">
                    {recommendations.map((rec) => (
                      <li
                        key={rec.message}
                        className="rounded-lg border border-white/[0.05] bg-surface-1/60 px-3.5 py-3"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <p className="text-sm text-ink">{rec.message}</p>
                          <span
                            className={cn(
                              'chip shrink-0 font-mono uppercase tracking-[0.14em]',
                              PRIORITY_STYLE[rec.priority] ?? PRIORITY_STYLE.low,
                            )}
                          >
                            {rec.priority}
                          </span>
                        </div>
                        <p className="mt-1 text-xs text-ink-subtle">{rec.basis}</p>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-ink-subtle">No recommendations for this scope yet.</p>
                )}
              </CardBody>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}

function NarrativeBlock({ title, body }: { title: string; body: string | null }) {
  if (!body) return null;
  return (
    <Card>
      <CardHeader title={title} />
      <CardBody>
        <p className="whitespace-pre-line text-sm leading-relaxed text-ink-subtle">{body}</p>
      </CardBody>
    </Card>
  );
}

function ArchiveRow({
  report,
  selected,
  onSelect,
}: {
  report: InsightReport;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-current={selected ? 'true' : undefined}
      className={cn(
        'w-full rounded-xl border py-2.5 pl-3.5 pr-3 text-left transition-colors duration-150',
        selected
          ? 'border-accent-indigo/30 bg-surface-2/80'
          : 'border-white/[0.06] bg-surface-1/70 hover:border-accent-indigo/20 hover:bg-surface-2/70',
      )}
    >
      <span className="block truncate font-mono text-[13px] text-ink">
        {report.owner}/{report.repository}
      </span>
      <span className="mt-0.5 block truncate font-mono text-[11px] text-ink-faint">
        {report.report_type === 'pull_request' ? `PR #${report.pull_request} \u00b7 ` : ''}
        {report.metrics.total_findings} findings &middot; {formatDate(report.generated_at)}
      </span>
    </button>
  );
}

export function InsightsPage() {
  const [selected, setSelected] = useState('');
  const [prNumber, setPrNumber] = useState('');
  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState<string | null>(null);
  const [active, setActive] = useState<InsightReport | null>(null);

  const repositories = useAsync(() => getRepositories(1, 100), []);
  const history = useAsync(() => getInsights({ perPage: 50 }), []);

  const handleGenerate = async () => {
    const repo = repositories.data?.repositories.find((r) => r.full_name === selected);
    if (!repo) return;
    setGenerating(true);
    setGenerateError(null);
    try {
      const report = await generateInsight({
        owner: repo.owner ?? repo.full_name.split('/')[0],
        repository: repo.name,
        pull_request: prNumber ? Number(prNumber) : undefined,
      });
      setActive(report);
      setPrNumber('');
      history.refetch();
    } catch (err) {
      setGenerateError((err as { message?: string }).message ?? 'Could not generate insight.');
    } finally {
      setGenerating(false);
    }
  };

  if (repositories.loading) return <LoadingState label="Loading repositories…" />;
  if (repositories.error || !repositories.data) {
    return (
      <ErrorState
        title="Could not load repositories"
        message={repositories.error ?? undefined}
        retry={repositories.refetch}
      />
    );
  }

  const repos = repositories.data.repositories;

  return (
    <PageContainer className="space-y-6">
      <PageHeader
        eyebrow={
          <>
            <span aria-hidden className="h-px w-8 bg-indigo-400/60" />
            Trajectory analysis
          </>
        }
        title={
          <>
            <span className="block">AI INTELLIGENCE</span>
            <span className="text-brand-gradient block">Reports</span>
          </>
        }
        description="Compute deterministic integrity reports from your real review and feedback history — trends, risk signals and recommended actions for any repository scope."
      />

      <Card tone="flat">
        <CardHeader title="Generator" />
        <CardBody>
          <div className="flex flex-wrap items-end gap-4">
            <label className="flex flex-col gap-1.5">
              <span className="eyebrow">Repository</span>
              <select
                value={selected}
                onChange={(event) => setSelected(event.target.value)}
                aria-label="Repository"
                className="field min-w-[16rem]"
              >
                <option value="" disabled className="bg-surface-1 text-ink">
                  Select a repository…
                </option>
                {repos.map((repo) => (
                  <option key={repo.full_name} value={repo.full_name} className="bg-surface-1 text-ink">
                    {repo.full_name}
                  </option>
                ))}
              </select>
            </label>

            <label className="flex flex-col gap-1.5">
              <span className="eyebrow">Pull request (optional)</span>
              <input
                type="number"
                min={1}
                placeholder="e.g. 12"
                value={prNumber}
                onChange={(event) => setPrNumber(event.target.value)}
                aria-label="Pull request number (optional)"
                className="field w-32"
              />
            </label>

            <Button
              variant="primary"
              onClick={handleGenerate}
              disabled={generating || !selected}
              loading={generating}
            >
              Generate report
            </Button>
          </div>

          {generateError ? (
            <p role="alert" className="mt-4 text-sm text-rose-300">
              {generateError}
            </p>
          ) : null}
        </CardBody>
      </Card>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div>
          {active ? (
            <InsightView report={active} />
          ) : (
            <EmptyState
              title="No report displayed"
              description="Select a repository and analyze, or open a generated report from the archive."
            />
          )}
        </div>

        <Card tone="flat" className="self-start">
          <CardHeader
            title="Archive"
            actions={
              history.data ? (
                <span className="font-mono text-[11.5px] tabular-nums text-ink-faint">
                  {history.data.total} reports
                </span>
              ) : null
            }
          />
          <CardBody>
            {history.loading ? (
              <LoadingState label="Loading archive…" />
            ) : history.error ? (
              <ErrorState title="Could not load insights" message={history.error} retry={history.refetch} />
            ) : history.data && history.data.items.length === 0 ? (
              <EmptyState
                title="No reports yet"
                description="Generated reports are archived here for later reference."
              />
            ) : (
              <div className="space-y-1.5">
                {history.data?.items.map((report) => (
                  <ArchiveRow
                    key={report.id}
                    report={report}
                    selected={active?.id === report.id}
                    onSelect={() => setActive(report)}
                  />
                ))}
              </div>
            )}
          </CardBody>
        </Card>
      </div>
    </PageContainer>
  );
}
