import { useCallback, useEffect, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';

import { createAiReview, getAiReview, runAiReview } from '../api/aiReviews';
import { AiReviewWorkspace } from '../components/ai-review/AiReviewWorkspace';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import { PageContainer } from '../components/PageContainer';
import { PageHeader } from '../components/PageHeader';
import { Button } from '../components/ui/Button';
import type { AiReview, ScmProvider } from '../types';

/**
 * Sprint 3 review surface.
 *
 * Two ways in:
 *  - `/ai-reviews/:reviewId` loads a stored review, which is what the PR page
 *    links to after starting a run.
 *  - `?owner=&repository=&number=` has no stored review yet, so the page offers
 *    to start one instead of erroring.
 */
export function AiReviewPage() {
  const { reviewId } = useParams<{ reviewId: string }>();
  const [searchParams] = useSearchParams();
  const provider: ScmProvider = searchParams.get('provider') === 'gitlab' ? 'gitlab' : 'github';

  const owner = searchParams.get('owner') ?? '';
  const repository = searchParams.get('repository') ?? '';
  const number = Number(searchParams.get('number') ?? NaN);
  const hasRunParams = Boolean(owner && repository && Number.isFinite(number) && number > 0);

  // `new` is the placeholder the PR page links to when no review exists yet, so
  // it must not be treated as a review id.
  const storedId = reviewId && reviewId !== 'new' ? reviewId : null;

  const [review, setReview] = useState<AiReview | null>(null);
  const [loading, setLoading] = useState(Boolean(storedId));
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);

  useEffect(() => {
    if (!storedId) {
      setReview(null);
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);
    getAiReview(storedId)
      .then((data) => {
        if (!cancelled) setReview(data);
      })
      .catch((cause: unknown) => {
        if (cancelled) return;
        setReview(null);
        setError(cause instanceof Error ? cause.message : 'Could not load this review.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [storedId]);

  const start = useCallback(async () => {
    setRunning(true);
    setRunError(null);
    try {
      const created = await runAiReview(owner, repository, number, provider);
      setReview(created);
    } catch (cause: unknown) {
      setRunError(cause instanceof Error ? cause.message : 'The review could not be started.');
    } finally {
      setRunning(false);
    }
  }, [owner, repository, number, provider]);

  // Re-running reuses the stored owner/repo/number, which the loaded review
  // already carries, so the query string is not required to be present.
  const rerun = useCallback(async () => {
    if (!review) return;
    setRunning(true);
    setRunError(null);
    try {
      const created = await createAiReview({
        owner: review.owner,
        repository: review.repository,
        pull_request_number: review.pull_request_number,
        provider: review.provider,
      });
      setReview(created);
    } catch (cause: unknown) {
      setRunError(cause instanceof Error ? cause.message : 'The review could not be re-run.');
    } finally {
      setRunning(false);
    }
  }, [review]);

  if (loading) {
    return (
      <PageContainer>
        <PageHeader title="AI review" description="Loading the stored review…" />
        <LoadingState label="Loading AI review" />
      </PageContainer>
    );
  }

  if (error) {
    return (
      <PageContainer>
        <PageHeader title="AI review" description="This review could not be loaded." />
        <ErrorState
          message={error}
          retry={() => window.location.reload()}
          title="This review could not be loaded"
        >
          {hasRunParams ? (
            <Button variant="secondary" onClick={start} disabled={running}>
              Start a new review
            </Button>
          ) : null}
        </ErrorState>
      </PageContainer>
    );
  }

  if (!review) {
    if (!hasRunParams) {
      return (
        <PageContainer>
          <PageHeader title="AI review" description="No pull request selected." />
          <EmptyState
            title="No pull request to review"
            description="Open a pull request and start an AI review from there, or pass owner, repository and number in the URL."
          />
        </PageContainer>
      );
    }

    return (
      <PageContainer>
        <PageHeader
          title="AI review"
          description={`${owner}/${repository} #${number}`}
        />
        {runError ? <ErrorState message={runError} retry={start} /> : null}
        <EmptyState
          title="No review has been run yet"
          description="Run the AI review to analyse the changes in this pull request. The diff and any findings will appear here."
          action={
            <Button onClick={start} disabled={running}>
              {running ? 'Running review…' : 'Run AI review'}
            </Button>
          }
        />
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <PageHeader
        title={review.pull_request_title ?? `Pull request #${review.pull_request_number}`}
        description={`${review.owner}/${review.repository} #${review.pull_request_number}`}
        actions={
          <Button variant="secondary" onClick={rerun} disabled={running}>
            {running ? 'Running review…' : 'Re-run AI review'}
          </Button>
        }
      />
      {runError ? <ErrorState message={runError} retry={rerun} /> : null}
      {/* The re-run action lives in the page header, so the workspace's own
          copy is left off here to avoid rendering the same button twice. */}
      <AiReviewWorkspace review={review} />
    </PageContainer>
  );
}
