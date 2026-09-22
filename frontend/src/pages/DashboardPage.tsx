import type { CSSProperties, ReactNode } from 'react';
import { useLayoutEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import gsap from 'gsap';

import { getDashboard, getFeedbackSummary, getRepositoryMetrics } from '../api/dashboard';
import { getInsights } from '../api/insights';
import { CategoryBarChart } from '../components/Charts/CategoryBarChart';
import { SeverityPieChart } from '../components/Charts/SeverityPieChart';
import { DataTable } from '../components/DataTable';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import { PageContainer } from '../components/PageContainer';
import { SeverityBadge } from '../components/SeverityBadge';
import { StateBadge } from '../components/Badge';
import { useAsync } from '../hooks/useAsync';
import { useMotionPrefs } from '../hooks/useMotionPrefs';
import { isTestEnv } from '../lib/env';
import type { DashboardSummary, FeedbackSummary, InsightReport, RecentReview, RepositoryMetric } from '../types';
import { formatCount, formatDate, formatPercent } from '../utils/format';
import { SEVERITY_CHART_COLORS } from '../utils/severity';

const SEVERITY_ORDER = ['critical', 'high', 'medium', 'low', 'info'] as const;
const SEVERITY_LABEL: Record<string, string> = {
  critical: 'Critical',
  high: 'High',
  medium: 'Medium',
  low: 'Low',
  info: 'Info',
};

/* ------------------------------------------------------------------ */
/* Section 1 — CINEMATIC 3D HERO                                        */
/* ------------------------------------------------------------------ */

function HUDMeter({
  value,
  label,
  className,
  accent = 'text-slate-100',
  side = 'left',
  tiltX = 5,
  tiltY = -7,
}: {
  value: string | number;
  label: string;
  className: string;
  accent?: string;
  side?: 'left' | 'right';
  tiltX?: number;
  tiltY?: number;
}) {
  const mirrors = side === 'right';
  return (
    <div
      data-hero="hud"
      data-hud={side}
      className={`orbital-meter absolute z-20 hidden md:block ${className}`}
    >
      <div
        className="holo-panel hud-tilt px-4 py-2.5"
        style={
          {
            '--tilt-x': `${mirrors ? -tiltX : tiltX}deg`,
            '--tilt-y': `${mirrors ? -tiltY : tiltY}deg`,
          } as CSSProperties
        }
      >
        <p className={`font-mono text-xl font-semibold tabular-nums ${accent}`}>{value}</p>
        <p className="hud-tag mt-0.5">{label}</p>
      </div>
    </div>
  );
}

/**
 * Dashboard-only cinematic scroll choreography.
 * The HTML hero composition (title, score, HUD slabs) drifts up and recedes as
 * the page scrolls, letting the fixed 3D AI core "emerge" beneath it. The
 * telemetry / analytics / recent sections then reveal in sequence.
 *
 * The hero parallax is driven from the live scroll position (Lenis already
 * smooths the scroll into per-frame native events) and the section reveals are
 * triggered by an IntersectionObserver. GSAP performs all of the motion
 * itself. Deterministic — no ScrollTrigger position-refresh races. Skipped in
 * tests, for reduced-motion users, and on touch devices.
 */
function useDashboardChoreography(rootRef: React.RefObject<HTMLDivElement | null>) {
  const { reduced, coarse } = useMotionPrefs();

  useLayoutEffect(() => {
    if (isTestEnv() || reduced || coarse || typeof window === 'undefined') return;
    const root = rootRef.current;
    if (!root) return;

    // --- Hero parallax: recede the DOM composition over the fixed 3D core ---
    const hero = root.querySelector<HTMLElement>('[data-cinematic="hero"]');
    const title = root.querySelector<HTMLElement>('[data-hero="title"]');
    const score = root.querySelector<HTMLElement>('[data-hero="score"]');
    const hudL = Array.from(root.querySelectorAll<HTMLElement>('[data-hud="left"]'));
    const hudR = Array.from(root.querySelectorAll<HTMLElement>('[data-hud="right"]'));

    let progress = 0;
    const apply = () => {
      if (!title) return;
      gsap.set(title, { yPercent: -34 * progress, opacity: 1 - progress, scale: 1 - 0.04 * progress });
      if (score) gsap.set(score, { yPercent: -22 * progress, opacity: 1 - progress });
      hudL.forEach((el) =>
        gsap.set(el, { yPercent: -16 * progress, xPercent: -30 * progress, opacity: 0.1 + 0.9 * (1 - progress) }),
      );
      hudR.forEach((el) =>
        gsap.set(el, { yPercent: -16 * progress, xPercent: 30 * progress, opacity: 0.1 + 0.9 * (1 - progress) }),
      );
    };

    const measure = () => {
      if (!hero || !title) return;
      const startY = hero.getBoundingClientRect().top + window.scrollY;
      const span = Math.max(200, hero.offsetHeight - window.innerHeight * 0.45);
      const next = Math.min(1, Math.max(0, (window.scrollY - startY) / span));
      if (Math.abs(next - progress) > 0.001) {
        progress = next;
        apply();
      }
    };

    measure();
    window.addEventListener('scroll', measure, { passive: true });
    window.addEventListener('resize', measure, { passive: true });
    const syncId = window.setTimeout(measure, 1600);

    // --- Section reveals: GSAP play triggered by intersection ---
    const io =
      typeof IntersectionObserver === 'undefined'
        ? null
        : new IntersectionObserver(
            (entries) => {
              entries.forEach((entry) => {
                if (!entry.isIntersecting) return;
                const el = entry.target as HTMLElement;
                (el as HTMLElement).dataset.revealed = '1';
                gsap.to(el, { y: 0, opacity: 1, duration: 0.9, ease: 'power2.out', overwrite: 'auto' });
                io?.unobserve(el);
              });
            },
            { rootMargin: '0px 0px -6% 0px', threshold: 0.01 },
          );

    const reveals = Array.from(root.querySelectorAll<HTMLElement>('[data-reveal-section]'));
    reveals.forEach((el) => {
      gsap.set(el, { y: 48, opacity: 0 });
      if (io) io.observe(el);
    });
    if (!io) {
      reveals.forEach((el) => {
        gsap.to(el, { y: 0, opacity: 1, duration: 0.9, ease: 'power2.out', overwrite: 'auto' });
      });
    }

    return () => {
      window.removeEventListener('scroll', measure);
      window.removeEventListener('resize', measure);
      window.clearTimeout(syncId);
      io?.disconnect();
      reveals.forEach((el) => gsap.killTweensOf(el));
    };
  }, [reduced, coarse, rootRef]);
}

function CinematicHero({
  summary,
  feedbackSummary,
}: {
  summary: DashboardSummary;
  feedbackSummary?: FeedbackSummary;
}) {
  return (
    <section
      id="dashboard-hero"
      data-cinematic="hero"
      className="relative -mx-6 -mt-8 flex min-h-[100svh] flex-col overflow-hidden lg:-mx-10 lg:-mt-10"
    >
      {/* atmospheric gradient layers */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(62%_54%_at_66%_42%,rgba(99,102,241,0.22),transparent_70%)]"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(46%_42%_at_24%_64%,rgba(34,211,238,0.1),transparent_72%)]"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 bottom-0 h-[34vh] bg-gradient-to-t from-[#02030A] via-[#02030A]/50 to-transparent"
      />

      {/* fine perspective grid — spatial depth layer */}
      <div aria-hidden className="grid-floor" />

      {/* decorative command-center corner frame */}
      <div aria-hidden className="pointer-events-none absolute inset-0 z-10 hidden md:block">
        <span className="hud-corner hud-corner-tl" />
        <span className="hud-corner hud-corner-tr" />
        <span className="hud-corner hud-corner-bl" />
        <span className="hud-corner hud-corner-br" />
      </div>

      <h1 className="sr-only">Dashboard</h1>

      {/* LEFT — oversized editorial command center type */}
      <div
        data-hero="title"
        className="hero-enter stagger-1 absolute left-6 top-[14%] z-20 hidden max-w-xl md:block lg:left-[max(4vw,2.75rem)] lg:top-[15%]"
      >
        <p className="hud-tag hud-tag-accent mb-5 flex items-center gap-2">
          <span aria-hidden className="h-px w-10 bg-indigo-400/60" />
          SmartSDLC / AI security system
        </p>
        <div className="hero-display hero-display-xl text-slate-50">
          <span className="block">SECURITY</span>
          <span className="h-grad block">COMMAND</span>
          <span className="block text-slate-500">CENTER</span>
        </div>
        <p className="mt-8 max-w-sm text-sm leading-relaxed text-slate-400">
          One live intelligence core over your repositories, reviews and
          findings — every signal is real pipeline data.
        </p>
      </div>

      {/* floating spatial HUD panels — the real six metrics flanking the core */}
      <HUDMeter
        className="left-[7%] top-[41%]"
        accent="text-slate-100"
        value={formatCount(summary.total_reviews)}
        label="Total reviews"
        side="left"
        tiltX={6}
        tiltY={-9}
      />
      <HUDMeter
        className="left-[8%] top-[59%]"
        accent="text-rose-300"
        value={formatCount(summary.critical_findings)}
        label="Critical findings"
        side="left"
        tiltX={4}
        tiltY={-5}
      />
      <HUDMeter
        className="bottom-[12%] left-[7%]"
        accent="text-cyan-200"
        value={formatCount(summary.reviews_today)}
        label="Reviews today"
        side="left"
        tiltX={7}
        tiltY={-10}
      />
      <HUDMeter
        className="right-[7%] top-[41%]"
        accent="text-amber-200"
        value={formatCount(summary.high_findings)}
        label="High findings"
        side="right"
        tiltX={6}
        tiltY={-9}
      />
      <HUDMeter
        className="right-[8%] top-[59%]"
        accent="text-indigo-200"
        value={formatCount(summary.total_findings)}
        label="Total findings"
        side="right"
        tiltX={4}
        tiltY={-5}
      />
      <HUDMeter
        className="bottom-[12%] right-[7%]"
        accent="text-emerald-300"
        value={feedbackSummary ? formatPercent(feedbackSummary.acceptance_rate) : '\u2014'}
        label="Acceptance rate"
        side="right"
        tiltX={7}
        tiltY={-10}
      />

      {/* MOBILE — compact stack (title + score, panels hidden) */}
      <div className="relative z-20 mx-auto flex flex-col items-center px-4 pt-20 text-center md:hidden">
        <p className="hud-tag hud-tag-accent">SmartSDLC / AI security system</p>
        <div className="hero-display hero-display-xl mt-5 text-slate-50">
          <span className="block">SECURITY</span>
          <span className="h-grad block">COMMAND</span>
          <span className="block text-slate-500">CENTER</span>
        </div>
      </div>

      <p className="absolute bottom-4 left-1/2 z-20 hidden -translate-x-1/2 font-mono text-[9px] uppercase tracking-[0.25em] text-slate-600 md:block">
        Scroll — Live telemetry
      </p>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Helper blocks for sections 2-4                                      */
/* ------------------------------------------------------------------ */

function SectionKicker({ children }: { children: ReactNode }) {
  return <p className="hud-tag hud-tag-accent">{children}</p>;
}

function TelemetryCard({
  label,
  value,
  unit = '',
  tone = 'text-slate-50',
}: {
  label: string;
  value: string | number;
  unit?: string;
  tone?: string;
}) {
  return (
    <div className="holo-panel holo-panel-press px-4 py-4">
      <p className="hud-tag">{label}</p>
      <p className={`mt-2 font-mono text-2xl font-semibold tabular-nums ${tone}`}>
        {value}
        {unit && <span className="ml-0.5 text-sm font-normal text-slate-500">{unit}</span>}
      </p>
    </div>
  );
}

/* Section 2 — SECURITY TELEMETRY (real, derived) */
function TelemetryBand({
  summary,
  repoCount,
}: {
  summary: DashboardSummary;
  repoCount: number;
}) {
  const total = summary.total_findings;
  const criticalShare =
    total > 0 ? ((summary.critical_findings / total) * 100).toFixed(1) : '0.0';
  const highShare = total > 0 ? ((summary.high_findings / total) * 100).toFixed(1) : '0.0';

  return (
    <section id="telemetry" data-reveal-section className="relative">
      <div className="mb-4 flex items-center gap-3">
        <SectionKicker>Security Telemetry</SectionKicker>
        <span aria-hidden className="h-px flex-1 bg-gradient-to-r from-accent-indigo/25 to-transparent" />
        <span className="font-mono text-[9px] uppercase tracking-[0.18em] text-slate-600">
          live · {formatCount(repoCount)} repositories connected
        </span>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <TelemetryCard label="Critical share" value={`${criticalShare}%`} tone="text-rose-300" />
        <TelemetryCard label="High share" value={`${highShare}%`} tone="text-amber-200" />
        <TelemetryCard
          label="Findings / review"
          value={summary.average_findings_per_review.toFixed(1)}
          tone="text-indigo-200"
        />
        <TelemetryCard
          label="Reviews this week"
          value={formatCount(summary.reviews_this_week)}
          tone="text-cyan-200"
        />
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <span className="hud-tag mr-1">Severity mix</span>
        {SEVERITY_ORDER.filter((s) => (summary.severity_distribution[s] ?? 0) > 0).map((s) => (
          <span
            key={s}
            className="flex items-center gap-1.5 rounded-full border border-white/[0.06] bg-white/[0.02] px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.14em] text-slate-400"
          >
            <span aria-hidden className="h-1.5 w-1.5 rounded-full" style={{ background: SEVERITY_CHART_COLORS[s] }} />
            {SEVERITY_LABEL[s]} {summary.severity_distribution[s]}
          </span>
        ))}
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Section 3 — SECURITY ANALYTICS (real charts + repository ledger)     */
/* ------------------------------------------------------------------ */

function AnalyticsSection({
  summary,
  repoRows,
  repoColumns,
  onOpenRepo,
}: {
  summary: DashboardSummary;
  repoRows: RepositoryMetric[];
  repoColumns: Array<{
    key: string;
    header: string;
    render: (row: RepositoryMetric) => ReactNode;
  }>;
  onOpenRepo: (row: RepositoryMetric) => void;
}) {
  return (
    <section id="analytics" data-reveal-section className="relative">
      <div className="mb-4 flex items-center gap-3">
        <SectionKicker>Security Analytics</SectionKicker>
        <span aria-hidden className="h-px flex-1 bg-gradient-to-r from-accent-indigo/25 to-transparent" />
        <span className="font-mono text-[9px] uppercase tracking-[0.18em] text-slate-600">real data</span>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[0.95fr_1.05fr] lg:gap-6">
        <div className="holo-panel p-5 sm:p-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold tracking-tight text-slate-50">
                Finding severity mix
              </h2>
              <p className="hud-tag mt-1">By severity · real findings</p>
            </div>
          </div>
          <div className="mt-4 flex items-center justify-center">
            <SeverityPieChart data={summary.severity_distribution} height={240} />
          </div>
          <div className="mt-4 flex flex-wrap justify-center gap-2">
            {SEVERITY_ORDER.filter((s) => (summary.severity_distribution[s] ?? 0) > 0).map((s) => (
              <span
                key={s}
                className="flex items-center gap-1.5 rounded-full border border-white/[0.06] bg-white/[0.02] px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.14em] text-slate-400"
              >
                <span aria-hidden className="h-1.5 w-1.5 rounded-full" style={{ background: SEVERITY_CHART_COLORS[s] }} />
                {SEVERITY_LABEL[s]} {summary.severity_distribution[s]}
              </span>
            ))}
          </div>
        </div>

        <div className="holo-panel p-5 sm:p-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold tracking-tight text-slate-50">
                Finding categories
              </h2>
              <p className="hud-tag mt-1">Where issues cluster</p>
            </div>
          </div>
          <div className="mt-4">
            <CategoryBarChart data={summary.category_distribution} height={240} />
          </div>
          <div className="mt-4 border-t border-white/[0.06] pt-4">
            <div className="flex items-center justify-between">
              <p className="hud-tag">Verdict signal</p>
              <span className="font-mono text-xs text-slate-500">
                {formatCount(summary.reviews_this_week)} this week
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* repository ledger */}
      <div className="holo-panel mt-5 p-5 sm:p-6">
        <div className="flex items-end justify-between gap-3 border-b border-white/[0.06] pb-3">
          <div>
            <p className="hud-tag hud-tag-accent">Repository Intelligence</p>
            <h2 className="mt-1 text-lg font-semibold tracking-tight text-slate-50">
              Repository telemetry
            </h2>
          </div>
          {repoRows.length > 0 && (
            <span className="font-mono text-xs tabular-nums text-slate-600">
              {repoRows.length} repos
            </span>
          )}
        </div>
        <div className="mt-4">
          {repoRows.length > 0 ? (
            <DataTable
              columns={repoColumns}
              rows={repoRows}
              rowKey={(row) => `${row.owner}/${row.repository}`}
              onRowClick={onOpenRepo}
            />
          ) : (
            <EmptyState
              title="No repository metrics yet"
              description="Metrics appear after the first review."
            />
          )}
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Section 4 — RECENT REVIEWS (real review data)                        */
/* ------------------------------------------------------------------ */

function RecentReviewsFeed({
  recent,
  onOpen,
}: {
  recent: RecentReview[];
  onOpen: (row: RecentReview) => void;
}) {
  if (recent.length === 0) {
    return (
      <EmptyState
        title="No reviews yet"
        description="Run your first AI review from a pull request page."
      />
    );
  }

  return (
    <div className="relative space-y-1">
      <span
        aria-hidden
        className="absolute bottom-3 left-[5px] top-3 w-px bg-gradient-to-b from-accent-indigo/25 via-white/[0.07] to-transparent"
      />
      <div className="space-y-1">
        {recent.map((item) => {
          const severityColor = item.review_severity
            ? (SEVERITY_CHART_COLORS[item.review_severity as keyof typeof SEVERITY_CHART_COLORS] ??
              '#94a3b8')
            : '#94a3b8';
          return (
            <button
              key={`${item.owner}/${item.repository}/${item.pull_request_number}`}
              type="button"
              onClick={() => onOpen(item)}
              className="group card-lift relative w-full rounded-lg border border-white/[0.05] bg-surface-1/80 py-3.5 pl-10 pr-4 text-left hover:bg-surface-2"
            >
              <span
                aria-hidden
                className="timeline-pulse absolute left-0 top-1/2 h-2.5 w-2.5 -translate-y-1/2 rounded-full border border-surface-0"
                style={
                  {
                    '--dot-glow': severityColor,
                    '--dot-dur': '3.4s',
                    background: severityColor,
                    boxShadow: `0 0 8px ${severityColor}80`,
                  } as React.CSSProperties
                }
              />

              <span className="flex flex-wrap items-center gap-x-4 gap-y-1">
                <span className="flex min-w-0 flex-1 items-center gap-2.5">
                  <span className="flex items-center gap-1.5">
                    <StateBadge state={item.status} />
                    {item.review_severity ? <SeverityBadge severity={item.review_severity} /> : null}
                  </span>
                  <span className="truncate font-mono text-sm text-slate-100">
                    {item.owner}/{item.repository}{' '}
                    <span className="text-slate-500">#{item.pull_request_number}</span>
                  </span>
                </span>

                <span className="flex shrink-0 items-center gap-3">
                  {item.pull_request_title && (
                    <span className="hidden max-w-52 truncate text-sm text-slate-400 lg:inline">
                      {item.pull_request_title}
                    </span>
                  )}
                  <span className="font-mono text-xs text-slate-500">
                    <span className="tabular-nums text-slate-200">{formatCount(item.total_finding_count)}</span>{' '}
                    findings
                  </span>
                  {item.review_score_100 != null ? (
                    <span
                      className={`font-mono text-xs tabular-nums ${
                        item.review_score_100 >= 80
                          ? 'text-emerald-300'
                          : item.review_score_100 < 60
                            ? 'text-rose-300'
                            : 'text-amber-200'
                      }`}
                    >
                      {item.review_score_100}%
                    </span>
                  ) : null}
                  <span className="w-28 shrink-0 text-right font-mono text-xs text-slate-600">
                    {formatDate(item.created_at)}
                  </span>
                </span>
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function RecentSection({
  recent,
  onOpen,
}: {
  recent: RecentReview[];
  onOpen: (row: RecentReview) => void;
}) {
  return (
    <section id="recent" data-reveal-section className="relative">
      <div className="mb-4 flex items-center gap-3">
        <SectionKicker>AI Review Activity</SectionKicker>
        <span aria-hidden className="h-px flex-1 bg-gradient-to-r from-accent-indigo/25 to-transparent" />
        <span className="font-mono text-[9px] uppercase tracking-[0.18em] text-slate-600">latest first</span>
      </div>

      <div className="holo-panel p-5 sm:p-6">
        <div className="flex items-center justify-between gap-3 border-b border-white/[0.06] pb-3">
          <h2 className="text-lg font-semibold tracking-tight text-slate-50">Recent reviews</h2>
          <span className="font-mono text-xs text-slate-600">{formatCount(recent.length)} latest</span>
        </div>
        <div className="mt-4">
          <RecentReviewsFeed recent={recent} onOpen={onOpen} />
        </div>
      </div>
    </section>
  );
}

/* Section — LATEST INSIGHT (real report, placed right below the hero) */
function InsightStrip({ insight, onOpen }: { insight: InsightReport; onOpen: () => void }) {
  const { metrics, feedback } = insight;
  return (
    <section id="latest-insight" data-reveal-section className="relative">
      <div className="mb-4 flex items-center gap-3">
        <SectionKicker>Latest Intelligence</SectionKicker>
        <span aria-hidden className="h-px flex-1 bg-gradient-to-r from-accent-indigo/25 to-transparent" />
        <span className="font-mono text-[9px] uppercase tracking-[0.18em] text-slate-600">
          generated report · real data
        </span>
      </div>

      <div className="holo-panel holo-panel-press p-5 sm:p-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <p className="hud-tag hud-tag-accent">
                {insight.owner}/{insight.repository}
              </p>
              <span className="rounded-full border border-white/[0.06] bg-white/[0.02] px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.14em] text-slate-500">
                {insight.report_type}
              </span>
            </div>
            <p className="mt-2 text-sm leading-relaxed text-slate-300">
              {insight.metrics.total_findings} findings across {insight.activity.review_count} reviews
              {insight.recommendations.length > 0
                ? ` · ${insight.recommendations.length} recommended actions`
                : ''}
            </p>
          </div>

          <div className="flex items-center gap-6">
            <div className="text-right">
              <p className="font-mono text-xl font-semibold tabular-nums text-rose-300">
                {formatCount(metrics.critical_findings)}
              </p>
              <p className="hud-tag mt-0.5">Critical</p>
            </div>
            <div className="text-right">
              <p className="font-mono text-xl font-semibold tabular-nums text-indigo-200">
                {formatCount(metrics.total_findings)}
              </p>
              <p className="hud-tag mt-0.5">Findings</p>
            </div>
            <div className="text-right">
              <p className="font-mono text-xl font-semibold tabular-nums text-emerald-300">
                {feedback.total_feedback > 0 ? formatPercent(feedback.acceptance_rate) : '\u2014'}
              </p>
              <p className="hud-tag mt-0.5">Acceptance</p>
            </div>
            <button
              type="button"
              onClick={onOpen}
              className="shrink-0 rounded-lg border border-accent-indigo/25 bg-accent-indigo/10 px-4 py-2.5 text-sm font-medium text-accent-lavender transition-all hover:border-accent-indigo/40 hover:bg-accent-indigo/20"
            >
              Open report
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Page                                                                 */
/* ------------------------------------------------------------------ */

export function DashboardPage() {
  const dashboard = useAsync(() => getDashboard(), []);
  const feedback = useAsync(() => getFeedbackSummary(), []);
  const repos = useAsync(() => getRepositoryMetrics(1, 10), []);
  const latestInsight = useAsync(async () => {
    const res = await getInsights({ perPage: 1 });
    return res.items[0] ?? null;
  }, []);

  if (dashboard.loading) return <LoadingState label="Loading dashboard\u2026" />;

  if (dashboard.error || !dashboard.data) {
    return (
      <PageContainer className="space-y-6">
        <ErrorState
          title="Could not load the dashboard"
          message={dashboard.error ?? 'No dashboard data available.'}
          retry={dashboard.refetch}
        />
      </PageContainer>
    );
  }

  return (
    <CinematicDashboard
      summary={dashboard.data}
      feedbackSummary={feedback.data ?? undefined}
      repoRows={repos.data?.repositories ?? []}
      latestInsight={latestInsight.data ?? undefined}
    />
  );
}

/**
 * Rendered only after dashboard data is available, so the cinematic scroll
 * choreography can bind to a fully-populated DOM subtree.
 */
function CinematicDashboard({
  summary,
  feedbackSummary,
  repoRows,
  latestInsight,
}: {
  summary: DashboardSummary;
  feedbackSummary?: FeedbackSummary;
  repoRows: RepositoryMetric[];
  latestInsight?: InsightReport;
}) {
  const navigate = useNavigate();
  const rootRef = useRef<HTMLDivElement>(null);
  useDashboardChoreography(rootRef);

  const repoColumns = [
    {
      key: 'repo',
      header: 'Repository',
      render: (row: RepositoryMetric) => (
        <span className="font-mono text-sm text-slate-200">
          {row.owner}/{row.repository}
        </span>
      ),
    },
    {
      key: 'reviews',
      header: 'Reviews',
      render: (row: RepositoryMetric) => (
        <span className="tabular-nums text-slate-200">{formatCount(row.review_count)}</span>
      ),
    },
    {
      key: 'findings',
      header: 'Findings',
      render: (row: RepositoryMetric) => (
        <span className="tabular-nums text-slate-300">{formatCount(row.finding_count)}</span>
      ),
    },
    {
      key: 'critical',
      header: 'Critical',
      render: (row: RepositoryMetric) => (
        <span className="tabular-nums font-medium text-rose-300">{formatCount(row.critical_count)}</span>
      ),
    },
    {
      key: 'avg',
      header: 'Avg / review',
      render: (row: RepositoryMetric) => (
        <span className="tabular-nums text-slate-300">
          {row.average_findings_per_review.toFixed(1)}
        </span>
      ),
    },
    {
      key: 'last',
      header: 'Last review',
      render: (row: RepositoryMetric) => (
        <span className="whitespace-nowrap font-mono text-xs text-slate-500">
          {formatDate(row.last_review_at)}
        </span>
      ),
    },
  ];

  return (
    <div ref={rootRef}>
      {/* SECTION 1 — CINEMATIC 3D COMMAND CENTER (full first viewport) */}
      <CinematicHero summary={summary} feedbackSummary={feedbackSummary ?? undefined} />

      {/* SECTIONS 2-4 — telemetry, analytics, recent reviews */}
      <div className="space-y-16 pt-16">
        {latestInsight && (
          <InsightStrip insight={latestInsight} onOpen={() => navigate('/insights')} />
        )}

        <TelemetryBand summary={summary} repoCount={repoRows.length} />

        <AnalyticsSection
          summary={summary}
          repoRows={repoRows}
          repoColumns={repoColumns}
          onOpenRepo={(row) => navigate(`/repositories/${row.owner}/${row.repository}`)}
        />

        <RecentSection
          recent={summary.recent_reviews}
          onOpen={(row) => navigate(`/reviews/${row.owner}/${row.repository}/${row.pull_request_number}`)}
        />
      </div>
    </div>
  );
}