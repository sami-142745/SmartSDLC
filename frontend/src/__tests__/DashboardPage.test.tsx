import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';

const mocks = vi.hoisted(() => ({
  getDashboard: vi.fn(),
  getFeedbackSummary: vi.fn(),
  getRepositoryMetrics: vi.fn(),
}));

vi.mock('../api/dashboard', () => mocks);

vi.mock('../api/insights', () => {
  return {
    generateInsight: vi.fn(),
    getInsights: vi.fn(async () => ({
      items: [],
      page: 1,
      per_page: 20,
      total: 0,
      total_pages: 0,
    })),
    getLatestRepositoryInsight: vi.fn(),
    getInsight: vi.fn(),
  };
});

vi.mock('../api/auth', () => ({
  exchangeCode: vi.fn(),
  getLoginUrl: vi.fn(),
  validateToken: vi.fn(),
  userFromToken: vi.fn(() => null),
}));

import { DashboardPage } from '../pages/DashboardPage';
import { dashboardSummary, feedbackSummary, repoMetrics } from '../test/fixtures';
import { renderWithProviders } from '../test/utils';
import { TEST_TOKEN } from '../test/fixtures';

beforeEach(() => {
  mocks.getDashboard.mockReset();
  mocks.getFeedbackSummary.mockReset();
  mocks.getRepositoryMetrics.mockReset();
  mocks.getDashboard.mockResolvedValue(dashboardSummary);
  mocks.getFeedbackSummary.mockResolvedValue(feedbackSummary);
  mocks.getRepositoryMetrics.mockResolvedValue(repoMetrics);
});

describe('DashboardPage', () => {
  it('renders metrics, charts, and tables from the API', async () => {
    renderWithProviders(<DashboardPage />, { route: '/dashboard', authToken: TEST_TOKEN });

    expect(await screen.findByText('Total reviews')).toBeInTheDocument();
    expect(await screen.findByText('Total findings')).toBeInTheDocument();
    expect(screen.getByText('23')).toBeInTheDocument();
    expect(screen.getByText('Critical findings')).toBeInTheDocument();
    expect(screen.getByText('Acceptance rate')).toBeInTheDocument();
    expect(screen.getByText('60%')).toBeInTheDocument();

    expect(await screen.findByText('Recent reviews')).toBeInTheDocument();
    expect(screen.getAllByText(/acme\/webapp/).length).toBeGreaterThan(0);
    expect(screen.getByText('Add auth flow')).toBeInTheDocument();
  });

  it('shows an error state when the API call fails', async () => {
    mocks.getDashboard.mockRejectedValue(new Error('Backend unreachable'));

    renderWithProviders(<DashboardPage />, { route: '/dashboard', authToken: TEST_TOKEN });

    expect(await screen.findByRole('alert')).toHaveTextContent(/could not load the dashboard/i);
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
  });

  it('supports retry after a failure', async () => {
    mocks.getDashboard
      .mockRejectedValueOnce(new Error('Backend unreachable'))
      .mockResolvedValueOnce(dashboardSummary);

    renderWithProviders(<DashboardPage />, { route: '/dashboard', authToken: TEST_TOKEN });

    expect(await screen.findByRole('alert')).toBeInTheDocument();
    await waitFor(() => expect(mocks.getFeedbackSummary).toHaveBeenCalledTimes(1));
    const retry = screen.getByRole('button', { name: /try again/i });
    retry.click();

    await waitFor(() => expect(mocks.getDashboard).toHaveBeenCalledTimes(2));
    expect(await screen.findByText('Total reviews')).toBeInTheDocument();
  });
});