import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const apiMocks = vi.hoisted(() => ({
  getCachedRepositories: vi.fn(),
}));

vi.mock('../api/repositoryIntelligence', () => apiMocks);

import { RepositoryIntelligencePage } from '../pages/RepositoryIntelligencePage';
import { renderWithProviders } from '../test/utils';

beforeEach(() => {
  vi.clearAllMocks();
  apiMocks.getCachedRepositories.mockResolvedValue([]);
});

describe('RepositoryIntelligencePage', () => {
  it('shows the empty state when nothing has been analysed', async () => {
    renderWithProviders(<RepositoryIntelligencePage />, { route: '/repository-intelligence' });

    expect(await screen.findByText('Nothing analysed yet')).toBeInTheDocument();
  });

  it('lists previously analysed repositories and opens one on click', async () => {
    apiMocks.getCachedRepositories.mockResolvedValue([
      {
        owner: 'acme',
        repository: 'webapp',
        full_name: 'acme/webapp',
        cached_at: '2026-02-21T10:00:00Z',
      },
    ]);

    renderWithProviders(<RepositoryIntelligencePage />, { route: '/repository-intelligence' });

    const entry = await screen.findByRole('button', { name: /acme\/webapp/ });
    await userEvent.click(entry);

    expect(apiMocks.getCachedRepositories).toHaveBeenCalled();
  });

  it('rejects a malformed slug before navigating', async () => {
    renderWithProviders(<RepositoryIntelligencePage />, { route: '/repository-intelligence' });

    const input = screen.getByLabelText('Repository');
    await userEvent.type(input, 'not-a-slug');
    await userEvent.click(screen.getByRole('button', { name: 'Analyse' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/owner\/name/i);
  });

  it('surfaces a retryable error when the listing request fails', async () => {
    apiMocks.getCachedRepositories.mockRejectedValue({
      message: 'Cannot reach the SmartSDLC backend.',
    });

    renderWithProviders(<RepositoryIntelligencePage />, { route: '/repository-intelligence' });

    expect(
      await screen.findByText('Could not load your analysed repositories'),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
  });

  it('refreshes the listing on demand', async () => {
    apiMocks.getCachedRepositories.mockResolvedValue([
      {
        owner: 'acme',
        repository: 'webapp',
        full_name: 'acme/webapp',
        cached_at: null,
      },
    ]);

    renderWithProviders(<RepositoryIntelligencePage />, { route: '/repository-intelligence' });

    const refresh = await screen.findByRole('button', { name: /refresh/i });
    await userEvent.click(refresh);

    await waitFor(() => expect(apiMocks.getCachedRepositories).toHaveBeenCalledTimes(2));
  });
});
