import { describe, expect, it, vi } from 'vitest';
import { fireEvent, screen } from '@testing-library/react';
import { Route, Routes } from 'react-router-dom';

const mocks = vi.hoisted(() => ({
  getPullRequests: vi.fn(),
}));

vi.mock('../api/github', () => ({
  ...mocks,
  getRepositories: vi.fn(),
  getPullRequest: vi.fn(),
  getPullRequestFiles: vi.fn(),
  getPullRequestDiff: vi.fn(),
}));

vi.mock('../api/auth', () => ({
  exchangeCode: vi.fn(),
  getLoginUrl: vi.fn(),
  validateToken: vi.fn(),
  userFromToken: vi.fn(() => null),
}));

import { RepoPage } from '../pages/RepoPage';
import { pullRequests } from '../test/fixtures';
import { renderWithProviders } from '../test/utils';
import { TEST_TOKEN } from '../test/fixtures';

describe('RepoPage', () => {
  it('lists pull requests for the repository and links to the detail page', async () => {
    mocks.getPullRequests.mockResolvedValue({
      pull_requests: pullRequests,
      page: 1,
      per_page: 30,
      has_more: false,
    });

    renderWithProviders(
      <Routes>
        <Route path="/repositories/:owner/:repo" element={<RepoPage />} />
        <Route path="/pull-requests/:owner/:repo/:number" element={<div>PR detail placeholder</div>} />
      </Routes>,
      { route: '/repositories/acme/webapp', authToken: TEST_TOKEN },
    );

    expect(await screen.findByText(/Add auth flow/i)).toBeInTheDocument();
    expect(screen.getByText(/#100 · Fix rate limiting/i)).toBeInTheDocument();

    const card = screen.getByRole('button', { name: /Add auth flow/i });
    fireEvent.click(card);

    expect(await screen.findByText('PR detail placeholder')).toBeInTheDocument();
  });

  it('switches between open and closed tabs', async () => {
    mocks.getPullRequests.mockResolvedValue({
      pull_requests: pullRequests,
      page: 1,
      per_page: 30,
      has_more: false,
    });

    renderWithProviders(
      <Routes>
        <Route path="/repositories/:owner/:repo" element={<RepoPage />} />
        <Route path="/pull-requests/:owner/:repo/:number" element={<div>PR detail placeholder</div>} />
      </Routes>,
      { route: '/repositories/acme/webapp', authToken: TEST_TOKEN },
    );

    expect(await screen.findByText(/Add auth flow/i)).toBeInTheDocument();

    const closedTab = screen.getByRole('button', { name: /^closed$/i });
    fireEvent.click(closedTab);
    expect(mocks.getPullRequests).toHaveBeenLastCalledWith('acme', 'webapp', 'closed', 1, 30);
  });

  it('shows an empty state when there are no pull requests', async () => {
    mocks.getPullRequests.mockResolvedValue({
      pull_requests: [],
      page: 1,
      per_page: 30,
      has_more: false,
    });

    renderWithProviders(<RepoPage />, { route: '/repositories/acme/webapp', authToken: TEST_TOKEN });

    expect(await screen.findByText(/no open pull requests/i)).toBeInTheDocument();
  });
});