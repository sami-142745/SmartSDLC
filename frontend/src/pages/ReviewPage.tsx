import { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';

import { getFeedbackHistory, getReviewFindings, getReviews, runReview } from '../api/reviews';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { FindingCard } from '../components/FindingCard';
import { LoadingState } from '../components/LoadingState';
import { ReviewSummary } from '../components/ReviewSummary';
import type { FeedbackAction, ReviewResponse } from '../types';

interface LatestFindings {
  review_id: string;
  findings: ReviewResponse['findings'];
}

const FEEDBACK_PRELOAD_LIMIT = 500;
const FEEDBACK_PAGE_SIZE = 100;

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

export function ReviewPage() {
  const { owner, repo, number } = useParams<{ owner: string; repo: string; number: string }>();
  const prNumber = Number(number);

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
      const [list, feedbackMap] = await Promise.all([
        getReviews(owner ?? '', repo ?? '', prNumber),
        loadFeedbackMap(),
      ]);
      setReviews(list);
      setFeedbackMap(feedbackMap);

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
      await runReview(owner ?? '', repo ?? '', prNumber);
      await load();
    } catch (err) {
      setRunError((err as { message?: string }).message ?? 'The review could not be completed.');
    } finally {
      setRunning(false);
    }
  };

  if (loading) return <LoadingState label="Loading review…" />;
  if (error) {
    return <ErrorState title="Could not load this review" message={error} retry={load} />;
  }

  const hasReview = reviews && reviews.length > 0 && latest;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-sm text-slate-500">
            {owner}/{repo} #{number}
          </p>
          <h1 className="mt-1 text-2xl font-semibold text-slate-900">AI Review</h1>
        </div>
        <button
          type="button"
          onClick={handleRunReview}
          disabled={running}
          className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {running ? 'Running AI review…' : hasReview ? 'Run review again' : 'Run AI review'}
        </button>
      </div>

      {runError && (
        <ErrorState title="Review failed" message={runError} />
      )}

      {!hasReview ? (
        <EmptyState
          title="No review yet"
          description="Run an AI review to analyze this pull request for security, bugs, performance, and maintainability issues."
        />
      ) : (
        <>
          <ReviewSummary review={reviews[0]} />

          <section>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
              Findings ({latest.findings.length})
            </h2>
            {latest.findings.length === 0 ? (
              <EmptyState title="No findings" description="This pull request looks clean." />
            ) : (
              <div className="space-y-4">
                {latest.findings.map((finding) => (
                  <FindingCard
                    key={finding.id}
                    finding={finding}
                    owner={owner ?? ''}
                    repo={repo ?? ''}
                    number={prNumber}
                    initialFeedback={{
                      [finding.id]: feedbackMap[`${latest.review_id}:${finding.id}`],
                    }}
                    onFeedbackChange={(findingId, action) =>
                      setFeedbackMap((prev) => ({
                        ...prev,
                        [`${latest.review_id}:${findingId}`]: action,
                      }))
                    }
                  />
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}