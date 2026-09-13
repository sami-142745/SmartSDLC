import { useState } from 'react';

import { getRepositories } from '../api/github';
import { generateInsight, getInsights } from '../api/insights';
import { CategoryBarChart } from '../components/Charts/CategoryBarChart';
import { SeverityPieChart } from '../components/Charts/SeverityPieChart';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import { PageContainer } from '../components/PageContainer';
import { StateBadge } from '../components/Badge';
import { CinematicButton } from '../components/ui/CinematicButton';
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
  insufficient: 'bg-slate-500',
};

const PRIORITY_STYLE: Record<string, string> = {
  high: 'border-rose-400/30 text-rose-300',
  medium: 'border-amber-300/30 text-amber-200',
  low: 'border-slate-400/30 text-slate-300',
};

function Stat({
  label,
  value,
  tone = 'text-slate-50',
}: {
  label: string;
  value: string | number;
  tone?: string;
}) {
  return (
    <div className="holo-panel holo-panel-press px-4 py-4">
      <p className="hud-tag">{label}</p>
      <p className={`mt-2 font-mono text-2xl font-semibold tabular-nums ${tone}`}>{value}</p>
    </div>
  );
}

function TrendRow({ trend }: { trend: InsightTrend }) {
  return (
    <div className="flex items-center justify-between gap-3 py-2.5">
      <div className="flex min-w-0 items-center gap-2.5">
        <span aria-hidden className={`h-1.5 w-1.5 shrink-0 rounded-full ${TREND_DOT[trend.status] ?? 'bg-slate-500'}`} />
        <span className="truncate text-sm capitalize text-slate-200">
          {trend.metric.replace(/_/g, ' ')}
        </span>
      </div>
      <div className="flex shrink-0 items-center gap-3 font-mono text-xs">
        <span className="tabular-nums text-slate-500">
          {trend.earlier} → {trend.later}
        </span>
        <span className="w-24 text-right text-slate-400">{trend.status}</span>
      </div>
    </div>
  );
}

function NarrativeBlock({ title, body }: { title: string; body: string | null }) {
  if (!body) return null;
  return (
    <section className="glass-edge block rounded-xl p-5">
      <p className="hud-tag hud-tag-accent mb-3">{title}</p>
      <p className="whitespace-pre-line text-sm leading-relaxed text-slate-300/90">{body}</p>
    </section>
  );
}

function InsightView({ report }: { report: InsightReport }) {
  const { metrics, activity, feedback, trends, risks, recommendations, narrative } = report;

  return (
    <section className="space-y-5">
      {/* report header */}
      <div className="glass-edge block rounded-xl p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="text-lg font-semibold text-slate-50">
              {report.owner}/{report.repository}
            </h2>
            <p className="mt-1 font-mono text-xs text-slate-500">
              {report.report_type === 'pull_request'
                ? `Pull request #${report.pull_request}`
                : 'Repository-wide'}
              {report.model ? ` · ${report.model}` : ' · rule-based'}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="rounded-full border border-white/[0.06] bg-white/[0.02] px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.14em] text-slate-400">
              {report.report_type}
            </span>
            <StateBadge state={report.status} />
          </div>
        </div>

        <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-2 border-t border-white/[0.05] pt-4 text-sm md:grid-cols-4">
          <div>
            <dt className="hud-tag block">Generated</dt>
            <dd className="mt-1 font-mono text-xs text-slate-400">{formatDate(report.generated_at)}</dd>
          </div>
          <div>
            <dt className="hud-tag block">Reviews analyzed</dt>
            <dd className="mt-1 font-mono text-xs text-slate-400">{report.source_review_ids.length}</dd>
          </div>
          <div>
            <dt className="hud-tag block">Duration</dt>
            <dd className="mt-1 font-mono text-xs text-slate-400">
              {report.duration_ms != null ? `${report.duration_ms} ms` : '—'}
            </dd>
          </div>
          <div>
            <dt className="hud-tag block">Feedback acceptance</dt>
            <dd className="mt-1 font-mono text-xs text-slate-400">
              {feedback.total_feedback > 0 ? formatPercent(feedback.acceptance_rate) : '—'}
            </dd>
          </div>
        </dl>
      </div>

      {report.status === 'failed' ? (
        <ErrorState title="Insight generation failed" message={report.error ?? undefined} />
      ) : (
        <>
          {/* narrative (Gemini, when available — otherwise rule-based report only) */}
          {narrative && (
            <div className="space-y-4">
              <NarrativeBlock title="Executive summary" body={narrative.executive_summary} />
              <NarrativeBlock title="Trend interpretation" body={narrative.trend_interpretation} />
              <NarrativeBlock title="Risk explanation" body={narrative.risk_explanation} />
              {narrative.recommendations.length > 0 && (
                <section className="glass-edge block rounded-xl p-5">
                  <p className="hud-tag hud-tag-accent mb-3">Narrative recommendations</p>
                  <ul className="space-y-2">
                    {narrative.recommendations.map((item) => (
                      <li
                        key={item}
                        className="flex items-start gap-2.5 text-sm leading-relaxed text-slate-300/90"
                      >
                        <span
                          aria-hidden
                          className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-indigo-400 shadow-[0_0_8px_rgba(129,140,248,0.8)]"
                        />
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                </section>
              )}
            </div>
          )}

          {/* key metrics */}
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <Stat label="Total findings" value={metrics.total_findings} tone="text-indigo-200" />
            <Stat label="Critical" value={metrics.critical_findings} tone="text-rose-300" />
            <Stat label="Security" value={metrics.security_findings} tone="text-amber-200" />
            <Stat
              label="Findings / review"
              value={metrics.average_findings_per_review.toFixed(2)}
              tone="text-cyan-200"
            />
          </div>

          {/* distributions */}
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            <div className="holo-panel p-5">
              <h3 className="text-sm font-semibold text-slate-50">Severity mix</h3>
              <div className="mt-4 flex items-center justify-center">
                <SeverityPieChart data={metrics.severity_distribution} height={220} />
              </div>
              <div className="mt-4 flex flex-wrap justify-center gap-2">
                {SEVERITY_ORDER.filter((s) => (metrics.severity_distribution[s] ?? 0) > 0).map((s) => (
                  <span
                    key={s}
                    className="flex items-center gap-1.5 rounded-full border border-white/[0.06] bg-white/[0.02] px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.14em] text-slate-400"
                  >
                    <span
                      aria-hidden
                      className="h-1.5 w-1.5 rounded-full"
                      style={{ background: SEVERITY_CHART_COLORS[s] }}
                    />
                    {SEVERITY_LABEL[s]} {metrics.severity_distribution[s]}
                  </span>
                ))}
              </div>
            </div>
            <div className="holo-panel p-5">
              <h3 className="text-sm font-semibold text-slate-50">Category clustering</h3>
              <div className="mt-4">
                <CategoryBarChart data={metrics.category_distribution} height={220} />
              </div>
              {metrics.recurring_categories.length > 0 && (
                <div className="mt-4 flex flex-wrap items-center gap-1.5">
                  <span className="hud-tag mr-1">Recurring</span>
                  {metrics.recurring_categories.map((cat) => (
                    <span
                      key={cat}
                      className="rounded-full border border-white/[0.06] bg-white/[0.02] px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.14em] text-slate-400"
                    >
                      {cat}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* activity + feedback */}
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            <div className="glass-edge block rounded-xl p-5">
              <p className="hud-tag hud-tag-accent mb-3">Activity</p>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <p className="font-mono text-xl font-semibold tabular-nums text-slate-100">
                    {activity.review_count}
                  </p>
                  <p className="hud-tag mt-0.5">Reviews</p>
                </div>
                <div>
                  <p className="font-mono text-xl font-semibold tabular-nums text-slate-100">
                    {activity.pull_request_count}
                  </p>
                  <p className="hud-tag mt-0.5">Pull requests</p>
                </div>
                <div>
                  <p className="font-mono text-xl font-semibold tabular-nums text-slate-100">
                    {activity.reviews_this_week}
                  </p>
                  <p className="hud-tag mt-0.5">This week</p>
                </div>
              </div>
              {activity.reviews_over_time.length > 0 && (
                <div className="mt-4 border-t border-white/[0.06] pt-3">
                  {activity.reviews_over_time.map((point) => (
                    <div
                      key={point.period}
                      className="flex items-center justify-between py-1.5 font-mono text-xs"
                    >
                      <span className="text-slate-500">{point.period}</span>
                      <span className="tabular-nums text-slate-300">
                        {point.reviews} reviews · {point.findings} findings
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="glass-edge block rounded-xl p-5">
              <p className="hud-tag hud-tag-accent mb-3">Human feedback loop</p>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <p className="font-mono text-xl font-semibold tabular-nums text-slate-100">
                    {feedback.total_accepted}
                  </p>
                  <p className="hud-tag mt-0.5">Accepted</p>
                </div>
                <div>
                  <p className="font-mono text-xl font-semibold tabular-nums text-slate-100">
                    {feedback.total_dismissed}
                  </p>
                  <p className="hud-tag mt-0.5">Dismissed</p>
                </div>
                <div>
                  <p className="font-mono text-xl font-semibold tabular-nums text-slate-100">
                    {feedback.total_feedback > 0 ? formatPercent(feedback.acceptance_rate) : '—'}
                  </p>
                  <p className="hud-tag mt-0.5">Acceptance</p>
                </div>
              </div>
              {feedback.total_feedback === 0 && (
                <p className="mt-3 text-xs text-slate-500">
                  No accepted/dismissed decisions recorded yet — decisions appear as you triage findings.
                </p>
              )}
            </div>
          </div>

          {/* trends */}
          <section className="glass-edge block rounded-xl p-5">
            <p className="hud-tag hud-tag-accent mb-1">Trajectory</p>
            <p className="mb-2 text-xs text-slate-500">
              Later window vs early window across the review timeline.
            </p>
            <div className="divide-y divide-white/[0.04]">
              {trends.length > 0 ? (
                trends.map((trend) => <TrendRow key={trend.metric} trend={trend} />)
              ) : (
                <p className="py-3 text-sm text-slate-500">Not enough history to compare.</p>
              )}
            </div>
          </section>

          {/* risks + recommendations */}
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            <section className="glass-edge block rounded-xl p-5">
              <p className="hud-tag hud-tag-accent mb-3">Risk signals</p>
              {risks.filter((r) => r.triggered).length > 0 ? (
                <div className="space-y-2.5">
                  {risks
                    .filter((r) => r.triggered)
                    .map((risk) => (
                      <div
                        key={risk.key}
                        className="flex items-start gap-2.5 rounded-lg border border-white/[0.05] bg-surface-1/60 px-3.5 py-3"
                      >
                        <span
                          aria-hidden
                          className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full"
                          style={{
                            background:
                              SEVERITY_CHART_COLORS[risk.severity as keyof typeof SEVERITY_CHART_COLORS] ??
                              '#94a3b8',
                            boxShadow: `0 0 8px ${
                              SEVERITY_CHART_COLORS[risk.severity as keyof typeof SEVERITY_CHART_COLORS] ??
                              '#94a3b8'
                            }80`,
                          }}
                        />
                        <div className="min-w-0">
                          <p className="text-sm font-medium text-slate-100">{risk.label}</p>
                          <p className="mt-0.5 text-xs leading-relaxed text-slate-400">{risk.detail}</p>
                        </div>
                      </div>
                    ))}
                </div>
              ) : (
                <p className="text-sm text-slate-500">No active risk signals across this scope.</p>
              )}
            </section>

            <section className="glass-edge block rounded-xl p-5">
              <p className="hud-tag hud-tag-accent mb-3">Recommended actions</p>
              {recommendations.length > 0 ? (
                <ul className="space-y-2.5">
                  {recommendations.map((rec) => (
                    <li
                      key={rec.message}
                      className="rounded-lg border border-white/[0.05] bg-surface-1/60 px-3.5 py-3"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <p className="text-sm text-slate-200">{rec.message}</p>
                        <span
                          className={`shrink-0 rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.14em] ${
                            PRIORITY_STYLE[rec.priority] ?? PRIORITY_STYLE.low
                          }`}
                        >
                          {rec.priority}
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-slate-500">{rec.basis}</p>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-slate-500">No recommendations for this scope yet.</p>
              )}
            </section>
          </div>
        </>
      )}
    </section>
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

  if (repositories.loading) return <LoadingState label="Loading repositories\u2026" />;
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
    <PageContainer className="space-y-10">
      {/* Intelligence hero */}
      <section className="py-6 lg:py-9">
        <p className="hud-tag hud-tag-accent flex items-center gap-3">
          <span aria-hidden className="h-px w-10 bg-indigo-400/60" />
          Trajectory analysis
        </p>
        <h1 className="hero-display mt-4 text-slate-50">
          <span className="block">AI INTELLIGENCE</span>
          <span className="h-grad block">REPORTS</span>
        </h1>
        <p className="mt-5 max-w-md text-sm leading-relaxed text-slate-400">
          Compute deterministic integrity reports from your real review and
          feedback history — trends, risk signals and recommended actions for
          any repository scope.
        </p>
      </section>

      {/* Generator console */}
      <div className="holo-panel flex flex-wrap items-end gap-4 p-5">
        <label className="flex flex-col gap-1.5">
          <span className="section-title">Repository</span>
          <select
            value={selected}
            onChange={(event) => setSelected(event.target.value)}
            aria-label="Repository"
            className="field min-w-[16rem]"
          >
            <option value="" disabled className="bg-surface-1 text-slate-100">
              Select a repository…
            </option>
            {repos.map((repo) => (
              <option key={repo.full_name} value={repo.full_name} className="bg-surface-1 text-slate-100">
                {repo.full_name}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1.5">
          <span className="section-title">Pull request (optional)</span>
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

        <CinematicButton onClick={handleGenerate} disabled={generating || !selected}>
          {generating ? (
            <span className="flex items-center gap-2">
              <span
                aria-hidden
                className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-transparent border-t-current"
              />
              Analyzing…
            </span>
          ) : (
            <>Generate report</>
          )}
        </CinematicButton>

        {generateError && <p className="w-full text-sm text-rose-300">{generateError}</p>}
      </div>

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div>
          <div className="mb-4 flex items-center justify-between border-b border-white/[0.06] pb-3">
            <span className="eyebrow">Live report</span>
          </div>
          {active ? (
            <InsightView report={active} />
          ) : (
            <EmptyState
              title="No report displayed"
              description="Select a repository and analyze, or open a generated report from the archive."
            />
          )}
        </div>

        <aside>
          <div className="mb-4 flex items-center justify-between border-b border-white/[0.06] pb-3">
            <span className="eyebrow">Archive</span>
            {history.data && (
              <span className="font-mono text-xs tabular-nums text-slate-500">
                {history.data.total} reports
              </span>
            )}
          </div>

          {history.loading ? (
            <LoadingState label="Loading archive\u2026" />
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
                <button
                  key={report.id}
                  type="button"
                  onClick={() => setActive(report)}
                  className={`group/hrow relative w-full overflow-hidden rounded-xl border bg-surface-1/70 py-3 pl-5 pr-4 text-left backdrop-blur-sm transition-all duration-200 hover:-translate-y-0.5 hover:border-accent-indigo/20 hover:bg-surface-2/80 ${
                    active?.id === report.id
                      ? 'border-accent-indigo/25 bg-surface-2/80 shadow-[0_0_22px_-10px_rgba(99,102,241,0.5)]'
                      : 'border-white/[0.06]'
                  }`}
                >
                  <span
                    aria-hidden
                    className="pointer-events-none absolute inset-y-0 left-0 w-[3px] rounded-r-full bg-gradient-to-b from-accent-indigo/0 via-accent-indigo/50 to-accent-indigo/0 opacity-0 transition-opacity duration-200 group-hover/hrow:opacity-100"
                  />
                  <span className="block truncate text-sm text-slate-200">
                    {report.owner}/{report.repository}
                  </span>
                  <span className="mt-0.5 block font-mono text-[11px] text-slate-600">
                    {report.report_type === 'pull_request' ? `PR #${report.pull_request} · ` : ''}
                    {report.metrics.total_findings} findings · {formatDate(report.generated_at)}
                  </span>
                </button>
              ))}
            </div>
          )}
        </aside>
      </div>
    </PageContainer>
  );
}