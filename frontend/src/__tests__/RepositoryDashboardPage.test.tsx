import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const apiMocks = vi.hoisted(() => ({
  getRepositoryDashboard: vi.fn(),
  invalidateRepositoryCache: vi.fn(),
}));

vi.mock('../api/repositoryIntelligence', () => apiMocks);

import { RepositoryDashboardPage } from '../pages/RepositoryDashboardPage';
import { repositoryDashboard } from '../test/fixtures';
import { renderRoute } from '../test/utils';

const ROUTE = '/repository-intelligence/:owner/:repo';

function renderPage(route = '/repository-intelligence/acme/webapp') {
  return renderRoute(ROUTE, <RepositoryDashboardPage />, { route });
}

beforeEach(() => {
  vi.clearAllMocks();
  apiMocks.getRepositoryDashboard.mockResolvedValue(repositoryDashboard);
  apiMocks.invalidateRepositoryCache.mockResolvedValue({
    owner: 'acme',
    repository: 'webapp',
    invalidated: 3,
  });
});

describe('RepositoryDashboardPage', () => {
  it('renders the profile, health score and language breakdown', async () => {
    renderPage();

    expect(await screen.findByText('Repository health')).toBeInTheDocument();
    expect(screen.getByText('Language composition')).toBeInTheDocument();
    expect(screen.getByText('README intelligence')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Dependencies' })).toBeInTheDocument();
    expect(screen.getByText('1,240')).toBeInTheDocument();
  });

  it('requests the dashboard for the routed repository', async () => {
    renderPage();

    await waitFor(() =>
      expect(apiMocks.getRepositoryDashboard).toHaveBeenCalledWith('acme', 'webapp', {
        provider: 'github',
        refresh: false,
      }),
    );
  });

  it('sends the gitlab provider when the query string selects it', async () => {
    renderPage('/repository-intelligence/acme/webapp?provider=gitlab');

    await waitFor(() =>
      expect(apiMocks.getRepositoryDashboard).toHaveBeenCalledWith('acme', 'webapp', {
        provider: 'gitlab',
        refresh: false,
      }),
    );
  });

  it('lists unmeasurable signals instead of scoring them as zero', async () => {
    renderPage();

    expect(await screen.findByText('Not measurable')).toBeInTheDocument();
    expect(screen.getByText(/Description/)).toBeInTheDocument();
  });

  it('shows a retryable error state when the dashboard request fails', async () => {
    apiMocks.getRepositoryDashboard.mockRejectedValue({ message: 'Provider unavailable.' });

    renderPage();

    expect(await screen.findByText('Could not analyse this repository')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
  });

  it('forces a refresh when the refresh action is used', async () => {
    renderPage();
    await screen.findByText('Repository health');

    await userEvent.click(screen.getByRole('button', { name: /^refresh$/i }));

    await waitFor(() =>
      expect(
        apiMocks.getRepositoryDashboard.mock.calls.some(([, , options]) => options?.refresh === true),
      ).toBe(true),
    );
  });

  it('clears the cached analysis and reloads', async () => {
    renderPage();
    await screen.findByText('Repository health');

    await userEvent.click(screen.getByRole('button', { name: /clear cache/i }));

    await waitFor(() =>
      expect(apiMocks.invalidateRepositoryCache).toHaveBeenCalledWith('acme', 'webapp'),
    );
  });

  it('guards against a half-resolved route instead of calling the API', async () => {
    // Only :owner matches, so the repository parameter stays blank.
    renderRoute('/repository-intelligence/:owner', <RepositoryDashboardPage />, {
      route: '/repository-intelligence/acme',
    });

    expect(await screen.findByText('No repository selected')).toBeInTheDocument();
    expect(apiMocks.getRepositoryDashboard).not.toHaveBeenCalled();
  });
});
