import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const apiMocks = vi.hoisted(() => ({
  getRepositoryDependencies: vi.fn(),
}));

vi.mock('../api/repositoryIntelligence', () => apiMocks);

import { RepositoryDependenciesPage } from '../pages/RepositoryDependenciesPage';
import { dependencyReport } from '../test/fixtures';
import { renderRoute } from '../test/utils';

const ROUTE = '/repository-intelligence/:owner/:repo/dependencies';

function renderPage(route = '/repository-intelligence/acme/webapp/dependencies') {
  return renderRoute(ROUTE, <RepositoryDependenciesPage />, { route });
}

beforeEach(() => {
  vi.clearAllMocks();
  apiMocks.getRepositoryDependencies.mockResolvedValue(dependencyReport);
});

describe('RepositoryDependenciesPage', () => {
  it('summarises the dependency report', async () => {
    renderPage();

    expect(await screen.findByRole('heading', { name: 'Dependencies' })).toBeInTheDocument();
    expect(screen.getByText('Declared')).toBeInTheDocument();
    // "Not pinned" labels both a summary stat and a filter, so assert on both.
    expect(screen.getAllByText('Not pinned')).toHaveLength(2);
  });

  it('requests dependencies for the routed repository', async () => {
    renderPage();

    await waitFor(() =>
      expect(apiMocks.getRepositoryDependencies).toHaveBeenCalledWith('acme', 'webapp', {
        provider: 'github',
      }),
    );
  });

  it('labels an exact pin and a floating range differently', async () => {
    renderPage();
    await screen.findByText('react');

    // The risk cell badge reads "Pinned"; the filter button of the same name is
    // separate, so scope the assertion to the table.
    const table = screen.getByRole('table');
    expect(within(table).getByText('Pinned')).toBeInTheDocument();
    expect(within(table).getByText('Floating range')).toBeInTheDocument();
  });

  it('narrows the table to flagged dependencies', async () => {
    renderPage();
    await screen.findByText('react');

    await userEvent.click(screen.getByRole('button', { name: 'Flagged' }));

    await waitFor(() => expect(screen.queryByText('react')).not.toBeInTheDocument());
    expect(screen.getByText('lodash')).toBeInTheDocument();
  });

  it('shows an empty state when no manifest was found', async () => {
    apiMocks.getRepositoryDependencies.mockResolvedValue({
      ...dependencyReport,
      manifests: [],
      dependencies: [],
      total: 0,
      direct_count: 0,
      flagged_count: 0,
      ecosystems: [],
    });

    renderPage();

    expect(
      await screen.findByText('No supported manifest was found in this repository.'),
    ).toBeInTheDocument();
  });

  it('surfaces a retryable error when the request fails', async () => {
    apiMocks.getRepositoryDependencies.mockRejectedValue({ message: 'Rate limited.' });

    renderPage();

    expect(await screen.findByText('Could not load dependencies')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
  });

  it('does not call the API for an unresolved repository', async () => {
    renderRoute('/repository-intelligence/:owner', <RepositoryDependenciesPage />, {
      route: '/repository-intelligence/acme',
    });

    expect(await screen.findByText('No repository selected')).toBeInTheDocument();
    expect(apiMocks.getRepositoryDependencies).not.toHaveBeenCalled();
  });
});
