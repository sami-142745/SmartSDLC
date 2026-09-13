import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen } from '@testing-library/react';

const reposMocks = vi.hoisted(() => ({
  getRepositories: vi.fn(),
}));

const insightsMocks = vi.hoisted(() => ({
  generateInsight: vi.fn(),
  getInsights: vi.fn(),
  getLatestRepositoryInsight: vi.fn(),
  getInsight: vi.fn(),
}));

vi.mock('../api/github', () => ({
  ...reposMocks,
  getPullRequests: vi.fn(),
  getPullRequest: vi.fn(),
  getPullRequestFiles: vi.fn(),
  getPullRequestDiff: vi.fn(),
}));

vi.mock('../api/insights', () => insightsMocks);

vi.mock('../api/auth', () => ({
  exchangeCode: vi.fn(),
  getLoginUrl: vi.fn(),
  validateToken: vi.fn(),
  userFromToken: vi.fn(() => null),
}));

import { InsightsPage } from '../pages/InsightsPage';
import {
  repositories,
  insightHistory,
  insightResponse,
  TEST_TOKEN,
} from '../test/fixtures';
import { renderWithProviders } from '../test/utils';

function renderPage() {
  return renderWithProviders(<InsightsPage />, {
    route: '/insights',
    authToken: TEST_TOKEN,
  });
}

describe('InsightsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    reposMocks.getRepositories.mockResolvedValue({
      repositories,
      page: 1,
      per_page: 100,
      has_more: false,
    });
    insightsMocks.getInsights.mockResolvedValue({
      items: [],
      page: 1,
      per_page: 50,
      total: 0,
      total_pages: 0,
    });
  });

  it('lists repositories in the generator selector', async () => {
    renderPage();

    expect(await screen.findByText('AI INTELLIGENCE')).toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: /repository/i })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'acme/webapp' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'acme/api' })).toBeInTheDocument();
    expect(screen.getByText('No reports yet')).toBeInTheDocument();
    expect(screen.getByText('No report displayed')).toBeInTheDocument();
  });

  it('shows a loading state while repositories are loading', () => {
    reposMocks.getRepositories.mockReturnValue(new Promise(() => {}));

    renderPage();

    expect(screen.getByText(/Loading repositories/)).toBeInTheDocument();
  });

  it('shows an error when repositories fail to load', async () => {
    reposMocks.getRepositories.mockRejectedValue(new Error('GitHub unreachable'));

    renderPage();

    expect(await screen.findByRole('alert')).toBeInTheDocument();
    expect(screen.getByText(/could not load repositories/i)).toBeInTheDocument();
  });

  it('generates a report for the selected repository', async () => {
    insightsMocks.generateInsight.mockResolvedValue(insightResponse);
    renderPage();

    const select = await screen.findByRole('combobox', { name: /repository/i });
    fireEvent.change(select, { target: { value: 'acme/webapp' } });

    fireEvent.click(screen.getByRole('button', { name: /generate report/i }));

    expect(await screen.findByText(/acme\/webapp/)).toBeInTheDocument();
    expect(screen.getByText('Total findings')).toBeInTheDocument();
    expect(screen.getByText('Recommended actions')).toBeInTheDocument();
    expect(screen.getByText('Triage the recurring critical finding cluster.')).toBeInTheDocument();
    expect(insightsMocks.generateInsight).toHaveBeenCalledWith(
      expect.objectContaining({ owner: 'acme', repository: 'webapp' }),
    );
  });

  it('sends the optional pull request number', async () => {
    insightsMocks.generateInsight.mockResolvedValue({
      ...insightResponse,
      report_type: 'pull_request',
      pull_request: 12,
      id: '888888888888888888888888',
    });
    renderPage();

    const select = await screen.findByRole('combobox', { name: /repository/i });
    fireEvent.change(select, { target: { value: 'acme/api' } });

    fireEvent.change(screen.getByLabelText(/pull request number \(optional\)/i), {
      target: { value: '12' },
    });

    fireEvent.click(screen.getByRole('button', { name: /generate report/i }));

    expect(await screen.findByText(/Pull request #12/)).toBeInTheDocument();
    expect(insightsMocks.generateInsight).toHaveBeenCalledWith(
      expect.objectContaining({ repository: 'api', pull_request: 12 }),
    );
  });

  it('shows an error message when generation fails', async () => {
    insightsMocks.generateInsight.mockRejectedValue(new Error('No reviews found for this repository'));
    renderPage();

    const select = await screen.findByRole('combobox', { name: /repository/i });
    fireEvent.change(select, { target: { value: 'acme/webapp' } });
    fireEvent.click(screen.getByRole('button', { name: /generate report/i }));

    expect(await screen.findByText('No reviews found for this repository')).toBeInTheDocument();
  });

  it('refreshes the archive after generating', async () => {
    insightsMocks.getInsights.mockResolvedValueOnce({
      items: [],
      page: 1,
      per_page: 50,
      total: 0,
      total_pages: 0,
    });
    insightsMocks.getInsights.mockResolvedValueOnce(insightHistory);
    insightsMocks.generateInsight.mockResolvedValue(insightResponse);

    renderPage();

    const select = await screen.findByRole('combobox', { name: /repository/i });
    fireEvent.change(select, { target: { value: 'acme/webapp' } });
    fireEvent.click(screen.getByRole('button', { name: /generate report/i }));

    expect(await screen.findByText('Recommended actions')).toBeInTheDocument();
    expect(insightsMocks.getInsights).toHaveBeenCalledTimes(2);
    expect(insightsMocks.generateInsight).toHaveBeenCalledTimes(1);
  });

  it('opens an archived report from the archive', async () => {
    insightsMocks.getInsights.mockResolvedValue(insightHistory);

    renderPage();

    expect(await screen.findByText('No report displayed')).toBeInTheDocument();

    fireEvent.click(await screen.findByRole('button', { name: /^acme\/webapp/ }));

    expect(await screen.findByText('Recommended actions')).toBeInTheDocument();
    expect(screen.getByText('Critical issues recurring')).toBeInTheDocument();
  });
});