import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';

const aiReviewMocks = vi.hoisted(() => ({
  getAiReview: vi.fn(),
  createAiReview: vi.fn(),
  runAiReview: vi.fn(),
  getAiReviewFindings: vi.fn(),
}));

vi.mock('../api/aiReviews', () => aiReviewMocks);

vi.mock('../api/auth', () => ({
  exchangeCode: vi.fn(),
  getLoginUrl: vi.fn(),
  validateToken: vi.fn(),
  userFromToken: vi.fn(() => null),
}));

import { AiReviewPage } from '../pages/AiReviewPage';
import { makeAiReview } from '../test/fixtures';
import { renderRoute } from '../test/utils';
import { TEST_TOKEN } from '../test/fixtures';

function renderStored(route = '/ai-reviews/r-1') {
  return renderRoute('/ai-reviews/:reviewId', <AiReviewPage />, {
    route,
    authToken: TEST_TOKEN,
  });
}

function renderNewReview(query = 'owner=acme&repository=webapp&number=101') {
  return renderRoute('/ai-reviews/:reviewId', <AiReviewPage />, {
    route: `/ai-reviews/new?${query}`,
    authToken: TEST_TOKEN,
  });
}

beforeEach(() => {
  aiReviewMocks.getAiReview.mockReset();
  aiReviewMocks.createAiReview.mockReset();
  aiReviewMocks.runAiReview.mockReset();
  aiReviewMocks.getAiReviewFindings.mockReset();
});

describe('AiReviewPage', () => {
  it('loads a stored review by id', async () => {
    aiReviewMocks.getAiReview.mockResolvedValue(makeAiReview());
    renderStored();

    expect(await screen.findByText('Harden the login redirect')).toBeInTheDocument();
    expect(aiReviewMocks.getAiReview).toHaveBeenCalledWith('r-1');
    expect(aiReviewMocks.getAiReviewFindings).not.toHaveBeenCalled();
  });

  it('shows an error state when the review cannot be loaded', async () => {
    aiReviewMocks.getAiReview.mockRejectedValue(new Error('Review not found'));
    renderStored();

    expect(await screen.findByRole('alert')).toHaveTextContent('Review not found');
  });

  it('offers to start a review when the pull request has none yet', async () => {
    renderNewReview();

    expect(await screen.findByText('No review has been run yet')).toBeInTheDocument();
    expect(aiReviewMocks.getAiReview).not.toHaveBeenCalled();
  });

  it('runs a review on demand and renders the result', async () => {
    aiReviewMocks.runAiReview.mockResolvedValue(makeAiReview());
    renderNewReview();

    fireEvent.click(await screen.findByRole('button', { name: 'Run AI review' }));

    expect(await screen.findByText('Harden the login redirect')).toBeInTheDocument();
    expect(aiReviewMocks.runAiReview).toHaveBeenCalledWith('acme', 'webapp', 101, 'github');
  });

  it('reports a failed run without discarding the page', async () => {
    aiReviewMocks.runAiReview.mockRejectedValue(new Error('GitHub rate limit reached'));
    renderNewReview();

    fireEvent.click(await screen.findByRole('button', { name: 'Run AI review' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('GitHub rate limit reached');
    expect(screen.getByText('No review has been run yet')).toBeInTheDocument();
  });

  it('asks for a pull request when no id and no query are present', async () => {
    renderStored('/ai-reviews/new');

    expect(await screen.findByText('No pull request to review')).toBeInTheDocument();
  });

  it('re-runs a loaded review using the repository it was stored against', async () => {
    aiReviewMocks.getAiReview.mockResolvedValue(makeAiReview());
    aiReviewMocks.createAiReview.mockResolvedValue(makeAiReview({ review_id: 'r-2' }));
    renderStored();

    const rerun = await screen.findByRole('button', { name: 'Re-run AI review' });
    fireEvent.click(rerun);

    await waitFor(() =>
      expect(aiReviewMocks.createAiReview).toHaveBeenCalledWith({
        owner: 'acme',
        repository: 'webapp',
        pull_request_number: 101,
        provider: 'github',
      }),
    );
  });

  it('passes the GitLab provider through to the new review call', async () => {
    aiReviewMocks.runAiReview.mockResolvedValue(makeAiReview({ provider: 'gitlab' }));
    renderNewReview('owner=acme&repository=webapp&number=101&provider=gitlab');

    fireEvent.click(await screen.findByRole('button', { name: 'Run AI review' }));

    await waitFor(() =>
      expect(aiReviewMocks.runAiReview).toHaveBeenCalledWith('acme', 'webapp', 101, 'gitlab'),
    );
  });
});
