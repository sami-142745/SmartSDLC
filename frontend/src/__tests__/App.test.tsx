import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

const dashboardMocks = vi.hoisted(() => ({
  getDashboard: vi.fn(),
  getFeedbackSummary: vi.fn(),
  getRepositoryMetrics: vi.fn(),
}));

const authMocks = vi.hoisted(() => ({
  exchangeCode: vi.fn(),
  getLoginUrl: vi.fn(() => 'http://localhost:8000/auth/github/login'),
  validateToken: vi.fn(async () => true),
  userFromToken: vi.fn(() => null),
}));

vi.mock('../api/dashboard', () => dashboardMocks);

vi.mock('../api/reviews', () => ({
  getReviews: vi.fn(async () => []),
  getReviewFindings: vi.fn(async () => ({ review_id: 'r1', findings: [] })),
  getFeedbackHistory: vi.fn(async () => ({ items: [], page: 1, per_page: 20, total: 0, total_pages: 1 })),
  runReview: vi.fn(),
  submitFeedback: vi.fn(),
}));

vi.mock('../api/github', () => ({
  getRepositories: vi.fn(async () => ({ repositories: [], page: 1, per_page: 30, has_more: false })),
  getPullRequests: vi.fn(),
  getPullRequest: vi.fn(),
  getPullRequestFiles: vi.fn(),
  getPullRequestDiff: vi.fn(),
}));

vi.mock('../api/insights', () => ({
  generateInsight: vi.fn(),
  getInsights: vi.fn(async () => ({ items: [], page: 1, per_page: 20, total: 0, total_pages: 0 })),
  getLatestRepositoryInsight: vi.fn(),
  getInsight: vi.fn(),
}));

vi.mock('../api/auth', () => authMocks);

import App from '../App';
import { dashboardSummary, feedbackSummary, repoMetrics, TEST_TOKEN } from '../test/fixtures';

beforeEach(() => {
  window.localStorage.clear();
  dashboardMocks.getDashboard.mockResolvedValue(dashboardSummary);
  dashboardMocks.getFeedbackSummary.mockResolvedValue(feedbackSummary);
  dashboardMocks.getRepositoryMetrics.mockResolvedValue(repoMetrics);
});

const RENDER_TIMEOUT = { timeout: 10_000 };

describe('App routing', () => {
  it('redirects an unauthenticated user to the login page', async () => {
    render(<App />);

    expect(await screen.findByRole('link', { name: /continue with github/i })).toHaveAttribute(
      'href',
      'http://localhost:8000/auth/github/login',
    );
  });

  it('renders the dashboard for an authenticated user', async () => {
    window.localStorage.setItem('smartsdlc_token', TEST_TOKEN);

    render(<App />);

    expect(await screen.findByRole('heading', { name: /dashboard/i }, RENDER_TIMEOUT)).toBeInTheDocument();
    expect(await screen.findByText('Total reviews', undefined, RENDER_TIMEOUT)).toBeInTheDocument();
    expect(screen.getByText('5')).toBeInTheDocument();
    expect(authMocks.validateToken).toHaveBeenCalled();
  });
});