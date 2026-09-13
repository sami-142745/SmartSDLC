import { useCallback, useEffect, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';

import { getFeedbackHistory, getReviewFindings, getReviews, runReview } from '../api/reviews';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { FindingCard } from '../components/FindingCard';
import { HeuristicSummary } from '../components/HeuristicSummary';
import { LoadingState } from '../components/LoadingState';
import { PageContainer } from '../components/PageContainer';
import { ReviewSummary } from '../components/ReviewSummary';
import { ReviewPipeline } from '../components/motion/ReviewPipeline';
import { Reveal } from '../components/motion/Reveal';
import { CinematicButton } from '../components/ui/CinematicButton';
import type { FeedbackAction, Finding, FindingSource, ReviewResponse, ScmProvider } from '../types';

interface LatestFindings {
  review_id: string;
  findings: ReviewResponse['findings'];
}

const FEEDBACK_PRELOAD_LIMIT = 500;
const FEEDBACK_PAGE_SIZE = 100;

const AI_SOURCES: FindingSource[] = ['gemini', 'combined'];

const CHANNELS = [
  { label: 'Gemini', tone: 'bg-violet-400 shadow-[0_0_10px_rgba(167,139,250,0.9)]' },
  { label: 'Heuristics', tone: 'bg-cyan-400 shadow-[0_0_10px_rgba(34,211,238,0.9)]' },
  { label: 'Security', tone: 'bg-indigo-400 shadow-[0_0_10px_rgba(129,140,248,0.9)]' },
  { label: 'Complexity', tone: 'bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.9)]' },
  { label: 'History', tone: 'bg-fuchsia-400 shadow-[0_0_10px_rgba(232,121,249,0.9)]' },
  { label: 'Feedback', tone: 'bg-amber-400 shadow-[0_0_10px_rgba(251,191,36,0.9)]' },
];

async function loadFeedbackMap(): Promise<Record<string, FeedbackAction>> {
  const map: Record<string, FeedbackAction> = {};
  let fetched = 0;
  let page = 1;
  while (fetched < FEEDBACK_PRELOAD_LIMIT) {
    const res = await getFeedbackHistory(page, FEEDBACK_PAGE_SIZE);
    for (const item of res.items) {
      if (item.action === 'accepted' || item.action === 'dismissed') {
        map[`${item.review_id}:${item.finding_id}`] = item.action;
      }
    }
    fetched += res.items.length;
    if (res.items.length < FEEDBACK_PAGE_SIZE) break;
    page += 1;
  }
  return map;
}

function FindingGroup({
  title,
  count,
  findings,
  owner,
  repo,
  number,
  feedbackMap,
  reviewId,
  onFeedbackChange,
  emptyLabel,
  accent,
}: {
  title: string;
  count: number;
  findings: Finding[];
  owner: string;
  repo: string;
  number: number;
  feedbackMap: Record<string, FeedbackAction>;
  reviewId: string;
  onFeedbackChange: (findingId: string, action: FeedbackAction) => void;
  emptyLabel: string;
  accent: string;
}) {
  return (
    <section className="relative">
      <div className="research-head relative flex flex-wrap items-center justify-between gap-3 rounded-xl border border-white/[0.06] bg-surface-1/60 px-4 py-3 backdrop-blur-sm">
        <span
          aria-hidden
          className={`absolute left-0 top-1/2 h-6 w-[3px] -translate-y-1/2 rounded-r-full ${accent}`}
        />
        <span
          aria-hidden
          className="pointer-events-none absolute inset-x-3 top-0 h-px bg-gradient-to-r from-transparent via-white/[0.07] to-transparent"
        />
        <div className="flex items-center gap-2.5">
          <span aria-hidden className={`h-2 w-2 rounded-full ${accent}`} />
          <h2 className="section-title">{title}</h2>
        </div>
        <span className="rounded-full border border-white/[0.08] bg-white/[0.03] px-2.5 py-0.5 text-xs font-semibold tabular-nums text-slate-400">
          {count}
        </span>
      </div>
      <div className="mt-3">
        {findings.length === 0 ? (
          <EmptyState title={emptyLabel} description="Nothing reported from this source." />
        ) : (
          <div className="space-y-2">
            {findings.map((finding) => (
              <FindingCard
                key={finding.id}
                finding={finding}
                owner={owner}
                repo={repo}
                number={number}
                initialFeedback={{
                  [finding.id]: feedbackMap[`${reviewId}:${finding.id}`],
                }}
                onFeedbackChange={onFeedbackChange}
              />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

export function ReviewPage() {
  const { owner, repo, number } = useParams<{ owner: string; repo: string; number: string }>();
  const [searchParams] = useSearchParams();
  const prNumber = Number(number);

  const provider: ScmProvider = searchParams.get('provider') === 'gitlab' ? 'gitlab' : 'github';

  const [reviews, setReviews] = useState<ReviewResponse[] | null>(null);
  const [latest, setLatest] = useState<LatestFindings | null>(null);
  const [feedbackMap, setFeedbackMap] = useState<Record<string, FeedbackAction>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [list, feedback] = await Promise.all([
        getReviews(owner ?? '', repo ?? '', prNumber),
        loadFeedbackMap(),
      ]);
      setReviews(list);
      setFeedbackMap(feedback);

      if (list.length > 0) {
        const findings = await getReviewFindings(owner ?? '', repo ?? '', prNumber);
        setLatest(findings);
      } else {
        setLatest(null);
      }
    } catch (err) {
      setError((err as { message?: string }).message ?? 'Could not load this review.');
    } finally {
      setLoading(false);
    }
  }, [owner, repo, prNumber]);

  useEffect(() => {
    load();
  }, [load]);

  const handleRunReview = async () => {
    setRunning(true);
    setRunError(null);
    try {
      await runReview(owner ?? '', repo ?? '', prNumber, provider);
      await load();
    } catch (err) {
      setRunError((err as { message?: string }).message ?? 'The review could not be completed.');
    } finally {
      setRunning(false);
    }
  };

  if (loading) return <LoadingState label="Loading review\u2026" />;
  if (error) {
    return <ErrorState title="Could not load this review" message={error} retry={load} />;
  }

  const hasReview = reviews && reviews.length > 0 && latest;

  return (
    <PageContainer className="space-y-8">
      {/* Analysis instrument — the report composes from the center, out */}
      <section className="py-8 lg:py-12">
        <p className="hud-tag hud-tag-accent flex items-center gap-3">
          <span aria-hidden className="h-px w-10 bg-indigo-400/60" />
          AI security intelligence · analysis core
        </p>

        <div className="mt-6 flex flex-col gap-8 lg:flex-row lg:items-end lg:justify-between">
          <h1 className="hero-display text-slate-50">
            <span className="block">AI</span>
            <span className="h-grad block">REVIEW</span>
          </h1>

          <div className="flex shrink-0 flex-col items-start gap-3 sm:flex-row sm:items-center lg:flex-col lg:items-end">
            <CinematicButton
              type="button"
              onClick={handleRunReview}
              disabled={running}
              className="group relative overflow-hidden rounded-xl border border-white/[0.12] bg-gradient-to-r from-indigo-500/90 via-violet-500/80 to-indigo-500/90 px-6 py-3 text-sm font-semibold text-white shadow-[0_18px_50px_-20px_rgba(99,102,241,0.9),inset_0_1px_0_rgba(255,255,255,0.15)] transition-all duration-200 hover:shadow-[0_22px_60px_-18px_rgba(99,102,241,1)] disabled:cursor-not-allowed disabled:opacity-60"
              strength={0.3}
            >
              <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <path d="M13 2 3 14h7l-1 8 10-12h-7l1-8Z" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              {running ? 'Running AI review\u2026' : hasReview ? 'Run review again' : 'Run AI review'}
            </CinematicButton>
            <span className="hud-tag">Gemini + heuristic engines</span>
          </div>
        </div>

        <p className="mt-8 inline-flex flex-wrap items-center gap-2 rounded-lg border border-white/[0.07] bg-surface-1/60 px-4 py-2 text-sm text-slate-400 backdrop-blur-sm">
          <svg viewBox="0 0 24 24" className="h-4 w-4 text-slate-500" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">
            <path d="M4 7h4l2.2-2.4a1 1 0 0 1 .76-.35H17a2 2 0 0 1 2 2V10M4 7v10a2 2 0 0 0 2 2h9M4 7h16a0 0 0 0 1 0 0v3M22 12.8V19a2 2 0 0 1-2 2h-8l2.5-3.5 4.5-4.7Z" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span className="font-mono text-accent-indigo">{owner}/{repo}</span>
          <span className="text-slate-600">/</span>
          <span className="tabular-nums text-slate-300">#{number}</span>
          <span aria-hidden className="mx-0.5 h-3 w-px bg-white/[0.08]" />
          <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-slate-600">
            pipeline &#x00B7; gemini + heuristic
          </span>
        </p>

        {/* Channel satellites — live sources feeding the core */}
        <div className="mt-6 flex flex-wrap items-center gap-2.5" aria-hidden="true">
          {CHANNELS.map((channel) => (
            <span key={channel.label} className="flex items-center gap-2 rounded-full border border-white/[0.07] bg-white/[0.02] px-3 py-1.5">
              <span className={`relative flex h-1.5 w-1.5`}>
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-50" style={{ backgroundColor: 'inherit' }} />
                <span className={`relative inline-flex h-1.5 w-1.5 rounded-full ${channel.tone}`} />
              </span>
              <span className="font-mono text-[9px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                {channel.label}
              </span>
            </span>
          ))}
        </div>
      </section>

      {runError && <ErrorState title="Review failed" message={runError} />}

      {!hasReview ? (
        <EmptyState
          title="No review yet"
          description="Run an AI review to analyze this pull request for security, bugs, performance, and maintainability issues."
        />
      ) : (
        <>
          <Reveal>
            <ReviewSummary review={reviews[0]} />
          </Reveal>

          <Reveal delay={60}>
            <ReviewPipeline
              geminiFindings={latest.findings.filter((f) => AI_SOURCES.includes(f.source)).length}
              heuristicFindings={latest.findings.filter((f) => f.source === 'heuristic').length}
            />
          </Reveal>

          <div className="flex items-end justify-between gap-3 border-b border-white/[0.06] pb-3">
            <div>
              <p className="hud-tag hud-tag-accent">Verbatim findings</p>
              <h2 className="mt-1 text-lg font-semibold tracking-tight text-slate-50">
                Findings ({latest.findings.length})
              </h2>
            </div>
          </div>

          <Reveal>
            <FindingGroup
              title="Gemini AI Findings"
              count={latest.findings.filter((f) => AI_SOURCES.includes(f.source)).length}
              findings={latest.findings.filter((f) => AI_SOURCES.includes(f.source))}
              owner={owner ?? ''}
              repo={repo ?? ''}
              number={prNumber}
              feedbackMap={feedbackMap}
              reviewId={latest.review_id}
              onFeedbackChange={(findingId, action) =>
                setFeedbackMap((prev) => ({
                  ...prev,
                  [`${latest.review_id}:${findingId}`]: action,
                }))
              }
              emptyLabel="No AI findings"
              accent="bg-violet-400 shadow-[0_0_10px_rgba(167,139,250,0.9)]"
            />
          </Reveal>

          <Reveal delay={80}>
            <HeuristicSummary findings={latest.findings.filter((f) => f.source === 'heuristic')} />
          </Reveal>

          <Reveal delay={120}>
            <FindingGroup
              title="Heuristic Findings"
              count={latest.findings.filter((f) => f.source === 'heuristic').length}
              findings={latest.findings.filter((f) => f.source === 'heuristic')}
              owner={owner ?? ''}
              repo={repo ?? ''}
              number={prNumber}
              feedbackMap={feedbackMap}
              reviewId={latest.review_id}
              onFeedbackChange={(findingId, action) =>
                setFeedbackMap((prev) => ({
                  ...prev,
                  [`${latest.review_id}:${findingId}`]: action,
                }))
              }
              emptyLabel="No heuristic findings"
              accent="bg-sky-400 shadow-[0_0_10px_rgba(56,189,248,0.9)]"
            />
          </Reveal>
        </>
      )}
    </PageContainer>
  );
}