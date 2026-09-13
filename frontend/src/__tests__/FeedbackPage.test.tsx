import { describe, expect, it, vi } from 'vitest';
import { fireEvent, screen } from '@testing-library/react';
import { Route, Routes } from 'react-router-dom';

const reviewsMocks = vi.hoisted(() => ({
  getFeedbackHistory: vi.fn(),
}));

const learningMocks = vi.hoisted(() => ({
  getFeedbackLearning: vi.fn(),
}));

vi.mock('../api/reviews', () => ({
  ...reviewsMocks,
  getReviews: vi.fn(),
  getReviewFindings: vi.fn(),
  runReview: vi.fn(),
  submitFeedback: vi.fn(),
}));

vi.mock('../api/feedback_learning', () => ({
  ...learningMocks,
}));

vi.mock('../api/auth', () => ({
  exchangeCode: vi.fn(),
  getLoginUrl: vi.fn(),
  validateToken: vi.fn(),
  userFromToken: vi.fn(() => null),
}));

import { FeedbackPage } from '../pages/FeedbackPage';
import { renderWithProviders } from '../test/utils';
import { TEST_TOKEN, emptyLearningResponse, learningResponse } from '../test/fixtures';
import type { FeedbackHistoryResponse } from '../types';

const feedback: FeedbackHistoryResponse = {
  items: [
    {
      review_id: 'review-1',
      finding_id: 'f1',
      owner: 'acme',
      repository: 'webapp',
      pull_request_number: 101,
      action: 'accepted',
      category: 'security',
      severity: 'high',
      created_at: '2026-09-08T10:00:00Z',
      updated_at: '2026-09-08T10:00:00Z',
    },
  ],
  page: 1,
  per_page: 20,
  total: 1,
  total_pages: 1,
};

describe('FeedbackPage', () => {
  it('lists feedback actions and links to the review', async () => {
    reviewsMocks.getFeedbackHistory.mockResolvedValue(feedback);
    learningMocks.getFeedbackLearning.mockResolvedValue(emptyLearningResponse);

    renderWithProviders(
      <Routes>
        <Route path="/feedback" element={<FeedbackPage />} />
        <Route path="/reviews/:owner/:repo/:number" element={<div>Review page placeholder</div>} />
      </Routes>,
      { route: '/feedback', authToken: TEST_TOKEN },
    );

    expect(await screen.findByText(/acme\/webapp #101/i)).toBeInTheDocument();
    expect(screen.getByText('accepted')).toBeInTheDocument();
    expect(screen.getByText('High')).toBeInTheDocument();
    expect(screen.getByText('Security')).toBeInTheDocument();

    fireEvent.click(screen.getByText(/acme\/webapp #101/i));
    expect(await screen.findByText('Review page placeholder')).toBeInTheDocument();
  });

  it('shows an empty state when there is no feedback', async () => {
    reviewsMocks.getFeedbackHistory.mockResolvedValue({
      items: [],
      page: 1,
      per_page: 20,
      total: 0,
      total_pages: 1,
    });
    learningMocks.getFeedbackLearning.mockResolvedValue(emptyLearningResponse);

    renderWithProviders(<FeedbackPage />, { route: '/feedback', authToken: TEST_TOKEN });

    expect(await screen.findByText('No feedback yet')).toBeInTheDocument();
    expect(
      await screen.findByText(/no learning signals available yet/i),
    ).toBeInTheDocument();
  });

  it('renders adaptive review prioritization signals', async () => {
    reviewsMocks.getFeedbackHistory.mockResolvedValue(feedback);
    learningMocks.getFeedbackLearning.mockResolvedValue(learningResponse);

    renderWithProviders(<FeedbackPage />, { route: '/feedback', authToken: TEST_TOKEN });

    expect(await screen.findByText(/adaptive review prioritization/i)).toBeInTheDocument();
    expect(await screen.findByText('1.09x')).toBeInTheDocument();
    expect(screen.getByText('0.89x')).toBeInTheDocument();
    expect(screen.getByText('Bug')).toBeInTheDocument();
  });
});