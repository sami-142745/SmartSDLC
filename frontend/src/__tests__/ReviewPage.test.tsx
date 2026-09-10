import { beforeEach, describe, expect, it, vi } from 'vitest';
import { Route, Routes } from 'react-router-dom';
import { fireEvent, screen, waitFor } from '@testing-library/react';

const reviewsMocks = vi.hoisted(() => ({
  getReviews: vi.fn(),
  getReviewFindings: vi.fn(),
  getFeedbackHistory: vi.fn(),
  runReview: vi.fn(),
  submitFeedback: vi.fn(),
}));

vi.mock('../api/reviews', () => reviewsMocks);

vi.mock('../api/auth', () => ({
  exchangeCode: vi.fn(),
  getLoginUrl: vi.fn(),
  validateToken: vi.fn(),
  userFromToken: vi.fn(() => null),
}));

import { ReviewPage } from '../pages/ReviewPage';
import { emptyFeedbackHistory, findings, makeFinding, makeReview } from '../test/fixtures';
import { renderWithProviders } from '../test/utils';
import { TEST_TOKEN } from '../test/fixtures';

function renderReview(props?: { authToken?: string }) {
  return renderWithProviders(
    <Routes>
      <Route path="/reviews/:owner/:repo/:number" element={<ReviewPage />} />
    </Routes>,
    { route: '/reviews/acme/webapp/101', authToken: props?.authToken ?? TEST_TOKEN },
  );
}

beforeEach(() => {
  reviewsMocks.getReviews.mockReset();
  reviewsMocks.getReviewFindings.mockReset();
  reviewsMocks.getFeedbackHistory.mockReset();
  reviewsMocks.runReview.mockReset();
  reviewsMocks.submitFeedback.mockReset();

  reviewsMocks.getFeedbackHistory.mockResolvedValue(emptyFeedbackHistory);
});

describe('ReviewPage', () => {
  it('shows the review summary and findings from the latest review', async () => {
    reviewsMocks.getReviews.mockResolvedValue([makeReview()]);
    reviewsMocks.getReviewFindings.mockResolvedValue({ review_id: 'review-1', findings });

    renderReview();

    expect(await screen.findByRole('heading', { name: /AI Review/i })).toBeInTheDocument();
    expect(await screen.findByText(/Review #101/i)).toBeInTheDocument();
    expect(await screen.findByText('Finding f1')).toBeInTheDocument();
    expect(screen.getByText('Finding f2')).toBeInTheDocument();
    expect(screen.getAllByText('Critical').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Info').length).toBeGreaterThan(0);
  });

  it('shows an empty state when no review exists yet', async () => {
    reviewsMocks.getReviews.mockResolvedValue([]);

    renderReview();

    expect(await screen.findByText('No review yet')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /run ai review/i })).toBeInTheDocument();
  });

  it('runs a new review and refreshes the findings', async () => {
    reviewsMocks.getReviews.mockResolvedValueOnce([]);
    reviewsMocks.runReview.mockResolvedValueOnce(makeReview());
    reviewsMocks.getReviews.mockResolvedValueOnce([makeReview()]);
    reviewsMocks.getReviewFindings.mockResolvedValue({ review_id: 'review-1', findings });

    renderReview();

    expect(await screen.findByText('No review yet')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /run ai review/i }));

    expect(await screen.findByText(/Review #101/i)).toBeInTheDocument();
    expect(reviewsMocks.runReview).toHaveBeenCalledWith('acme', 'webapp', 101);
  });

  it('lets the user accept a finding and stores the feedback', async () => {
    const finding = makeFinding('f1', { severity: 'high' });
    reviewsMocks.getReviews.mockResolvedValue([makeReview({ findings: [finding] })]);
    reviewsMocks.getReviewFindings.mockResolvedValue({ review_id: 'review-1', findings: [finding] });
    reviewsMocks.submitFeedback.mockResolvedValue({
      review_id: 'review-1',
      finding_id: 'f1',
      owner: 'acme',
      repository: 'webapp',
      pull_request_number: 101,
      action: 'accepted',
      category: 'security',
      severity: 'high',
      created_at: null,
      updated_at: null,
    });

    renderReview();

    expect(await screen.findByText('Finding f1')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /^accept$/i }));

    await waitFor(() =>
      expect(reviewsMocks.submitFeedback).toHaveBeenCalledWith('acme', 'webapp', 101, 'f1', 'accepted'),
    );
    expect(await screen.findByRole('button', { name: /accepted/i })).toBeInTheDocument();
  });

  it('preloads previously stored feedback states', async () => {
    const finding = makeFinding('f1', { severity: 'high' });
    reviewsMocks.getReviews.mockResolvedValue([makeReview({ findings: [finding] })]);
    reviewsMocks.getReviewFindings.mockResolvedValue({ review_id: 'review-1', findings: [finding] });
    reviewsMocks.getFeedbackHistory.mockResolvedValue({
      items: [
        {
          review_id: 'review-1',
          finding_id: 'f1',
          owner: 'acme',
          repository: 'webapp',
          pull_request_number: 101,
          action: 'dismissed',
          category: 'security',
          severity: 'high',
          created_at: '2026-09-08T10:00:00Z',
          updated_at: '2026-09-08T10:00:00Z',
        },
      ],
      page: 1,
      per_page: 100,
      total: 1,
      total_pages: 1,
    });

    renderReview();

    expect(await screen.findByRole('button', { name: /^Dismissed ✓$/i })).toBeInTheDocument();
    expect(reviewsMocks.getFeedbackHistory).toHaveBeenCalledWith(1, 100);
  });
});