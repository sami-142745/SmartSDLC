import { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';

import { getFeedbackHistory, getReviewFindings, getReviews, runReview } from '../api/reviews';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { FindingCard } from '../components/FindingCard';
import { HeuristicSummary } from '../components/HeuristicSummary';
import { LoadingState } from '../components/LoadingState';
import { PageContainer } from '../components/PageContainer';
import { PageHeader } from '../components/PageHeader';
import { ReviewSummary } from '../components/ReviewSummary';
import { Button } from '../components/ui/Button';
import { Card, CardBody } from '../components/ui/Card';
import { SkeletonRows } from '../components/ui/Skeleton';
import { Tabs } from '../components/ui/Tabs';
import { severityLabel } from '../utils/severity';
import { cn } from '../lib/cn';
import type { FeedbackAction, Finding, FindingSource, ReviewResponse, ScmProvider } from '../types';

interface LatestFindings {
  review_id: string;
  findings: ReviewResponse['findings'];
}

const FEEDBACK_PRELOAD_LIMIT = 500;
const FEEDBACK_PAGE_SIZE = 100;

const AI_SOURCES: FindingSource[] = ['gemini', 'combined'];

type Filter = 'all' | 'ai' | 'heuristic' | 'critical';

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

function FindingList({
  findings,
  owner,
  repo,
  number,
  feedbackMap,
  reviewId,
  onFeedbackChange,
  emptyLabel,
}: {
  findings: Finding[];
  owner: string;
  repo: string;
  number: number;
  feedbackMap: Record<string, FeedbackAction>;
  reviewId: string;
  onFeedbackChange: (findingId: string, action: FeedbackAction) => void;
  emptyLabel: string;
}) {
  if (findings.length === 0) {
    return <EmptyState title={emptyLabel} description="Nothing reported from this source." />;
  }
  return (
    <ul className="space-y-2">
      {findings.map((finding) => (
        <li key={finding.id}>
          <FindingCard
            finding={finding}
            owner={owner}
            repo={repo}
            number={number}
            initialFeedback={{ [finding.id]: feedbackMap[`${reviewId}:${finding.id}`] }}
            onFeedbackChange={onFeedbackChange}
          />
        </li>
      ))}
    </ul>
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
  const [filter, setFilter] = useState<Filter>('all');

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

  const findings = latest?.findings ?? [];
  const hasReview = Boolean(reviews && reviews.length > 0 && latest);

  const partitions = useMemo(() => {
    const ai = findings.filter((finding) => AI_SOURCES.includes(finding.source));
    const heuristic = findings.filter((finding) => finding.source === 'heuristic');
    return { ai, heuristic };
  }, [findings]);

  const visible = useMemo(() => {
    switch (filter) {
      case 'ai':
        return partitions.ai;
      case 'heuristic':
        return partitions.heuristic;
      case 'critical':
        return findings.filter((finding) => finding.severity === 'critical');
      default:
        return findings;
    }
  }, [filter, findings, partitions]);

  const criticalCount = findings.filter((finding) => finding.severity === 'critical').length;

  const handleFeedbackChange = (findingId: string, action: FeedbackAction) => {
    if (!latest) return;
    setFeedbackMap((previous) => ({ ...previous, [`${latest.review_id}:${findingId}`]: action }));
  };

  if (loading) {
    return (
      <PageContainer className="space-y-6">
        <LoadingState label="Loading review…" />
        <SkeletonRows rows={4} />
      </PageContainer>
    );
  }

  if (error) {
    return <ErrorState title="Could not load this review" message={error} retry={load} />;
  }

  return (
    <PageContainer className="space-y-6">
      <PageHeader
        eyebrow={
          <>
            <span className="font-mono">{owner}</span>
            <span className="text-ink-faint">/</span>
            <span className="font-mono">{repo}</span>
            <span className="text-ink-faint">#{number}</span>
          </>
        }
        title={
          <>
            AI Review
            {hasReview ? (
              <span className="ml-2.5 align-middle font-mono text-[13px] font-normal text-ink-faint">
                {findings.length} finding{findings.length === 1 ? '' : 's'}
              </span>
            ) : null}
          </>
        }
        description="Gemini model analysis combined with deterministic pattern matching. Accept or dismiss findings to train the adaptive ranking."
        actions={
          <Button variant="primary" onClick={handleRunReview} loading={running}>
            {!running ? (
              <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <path d="M13 2 3 14h7l-1 8 10-12h-7l1-8Z" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            ) : null}
            {running ? 'Running AI review\u2026' : hasReview ? 'Run review again' : 'Run AI review'}
          </Button>
        }
      />

      {runError ? <ErrorState title="Review failed" message={runError} /> : null}

      {!hasReview ? (
        <EmptyState
          title="No review yet"
          description="Run an AI review to analyze this pull request for security, bugs, performance, and maintainability issues."
        />
      ) : (
        <>
          <ReviewSummary review={reviews![0]} />

          <Card>
            <CardBody className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="section-title">Findings</h2>
                  <p className="mt-0.5 text-[12px] text-ink-subtle">
                    {visible.length} of {findings.length} shown
                  </p>
                </div>
                <Tabs
                  aria-label="Filter findings"
                  value={filter}
                  onChange={setFilter}
                  items={[
                    { value: 'all', label: 'All', count: findings.length },
                    { value: 'ai', label: 'AI', count: partitions.ai.length },
                    { value: 'heuristic', label: 'Heuristic', count: partitions.heuristic.length },
                    {
                      value: 'critical',
                      label: 'Critical',
                      count: criticalCount,
                      disabled: criticalCount === 0,
                    },
                  ]}
                  size="sm"
                />
              </div>

              <HeuristicSummary findings={partitions.heuristic} />

              <FindingList
                findings={visible}
                owner={owner ?? ''}
                repo={repo ?? ''}
                number={prNumber}
                feedbackMap={feedbackMap}
                reviewId={latest!.review_id}
                onFeedbackChange={handleFeedbackChange}
                emptyLabel={
                  filter === 'critical'
                    ? `No ${severityLabel('critical').toLowerCase()} findings`
                    : 'No findings match this filter'
                }
              />
            </CardBody>
          </Card>

          {/* Severity legend keeps the palette discoverable without a key. */}
          <Card tone="flat">
            <CardBody className="flex flex-wrap items-center gap-x-5 gap-y-2 text-[11.5px] text-ink-faint">
              <span className="flex items-center gap-1.5">
                <span className="h-1.5 w-1.5 rounded-full bg-accent-violet" />
                Gemini AI analysis
              </span>
              <span className="flex items-center gap-1.5">
                <span className="h-1.5 w-1.5 rounded-full bg-accent-cyan" />
                Heuristic rules
              </span>
              <span className={cn('flex items-center gap-1.5')}>
                <span className="h-1.5 w-1.5 rounded-full bg-rose-400" />
                Severity classified
              </span>
            </CardBody>
          </Card>
        </>
      )}
    </PageContainer>
  );
}
