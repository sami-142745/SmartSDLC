import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const apiMocks = vi.hoisted(() => ({
  getRepositoryReadme: vi.fn(),
}));

vi.mock('../api/repositoryIntelligence', () => apiMocks);

import { RepositoryReadmePage } from '../pages/RepositoryReadmePage';
import { readmeIntelligence } from '../test/fixtures';
import { renderRoute } from '../test/utils';

const ROUTE = '/repository-intelligence/:owner/:repo/readme';

function renderPage(route = '/repository-intelligence/acme/webapp/readme') {
  return renderRoute(ROUTE, <RepositoryReadmePage />, { route });
}

beforeEach(() => {
  vi.clearAllMocks();
  apiMocks.getRepositoryReadme.mockResolvedValue(readmeIntelligence);
});

describe('RepositoryReadmePage', () => {
  it('renders README metrics and the document outline', async () => {
    renderPage();

    expect(await screen.findByText('README intelligence')).toBeInTheDocument();
    expect(screen.getByText('Document outline')).toBeInTheDocument();
    expect(screen.getByText('Install')).toBeInTheDocument();
  });

  it('requests the README for the routed repository', async () => {
    renderPage();

    await waitFor(() =>
      expect(apiMocks.getRepositoryReadme).toHaveBeenCalledWith('acme', 'webapp', {
        provider: 'github',
      }),
    );
  });

  it('reports each coverage signal as present or missing', async () => {
    renderPage();
    await screen.findByText('README intelligence');

    expect(screen.getByText('Usage examples')).toBeInTheDocument();
    const present = screen.getAllByText('Present');
    const missing = screen.getAllByText('Missing');
    expect(present.length).toBe(3);
    expect(missing.length).toBe(1);
  });

  it('reveals the raw source on demand', async () => {
    renderPage();
    await screen.findByText('README intelligence');

    expect(screen.queryByText('README source')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /view source/i }));

    expect(await screen.findByText('README source')).toBeInTheDocument();
    expect(screen.getByText(/# Webapp/)).toBeInTheDocument();
  });

  it('explains a missing README rather than showing an empty document', async () => {
    apiMocks.getRepositoryReadme.mockResolvedValue({
      ...readmeIntelligence,
      available: false,
      reason: 'No README found on the default branch.',
      raw: null,
      path: null,
    });

    renderPage();

    expect(await screen.findByText('No README found')).toBeInTheDocument();
    expect(screen.getByText('No README found on the default branch.')).toBeInTheDocument();
  });

  it('surfaces a retryable error when the request fails', async () => {
    apiMocks.getRepositoryReadme.mockRejectedValue({ message: 'Not found.' });

    renderPage();

    expect(await screen.findByText('Could not analyse the README')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
  });

  it('does not call the API for an unresolved repository', async () => {
    renderRoute('/repository-intelligence/:owner', <RepositoryReadmePage />, {
      route: '/repository-intelligence/acme',
    });

    expect(await screen.findByText('No repository selected')).toBeInTheDocument();
    expect(apiMocks.getRepositoryReadme).not.toHaveBeenCalled();
  });
});
