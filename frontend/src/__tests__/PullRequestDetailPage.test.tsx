import { describe, expect, it, vi } from 'vitest';
import { fireEvent, screen } from '@testing-library/react';
import { Route, Routes } from 'react-router-dom';

const mocks = vi.hoisted(() => ({
  getPullRequest: vi.fn(),
  getPullRequestFiles: vi.fn(),
  getPullRequestDiff: vi.fn(),
}));

vi.mock('../api/github', () => ({
  ...mocks,
  getRepositories: vi.fn(),
  getPullRequests: vi.fn(),
}));

vi.mock('../api/auth', () => ({
  exchangeCode: vi.fn(),
  getLoginUrl: vi.fn(),
  validateToken: vi.fn(),
  userFromToken: vi.fn(() => null),
}));

import { PullRequestDetailPage } from '../pages/PullRequestDetailPage';
import { pullRequestDiff, pullRequestFiles, pullRequests } from '../test/fixtures';
import { renderWithProviders } from '../test/utils';
import { TEST_TOKEN } from '../test/fixtures';

describe('PullRequestDetailPage', () => {
  it('shows pull request info, changed files, and the diff', async () => {
    mocks.getPullRequest.mockResolvedValue(pullRequests[0]);
    mocks.getPullRequestFiles.mockResolvedValue(pullRequestFiles);
    mocks.getPullRequestDiff.mockResolvedValue(pullRequestDiff);

    renderWithProviders(
      <Routes>
        <Route path="/pull-requests/:owner/:repo/:number" element={<PullRequestDetailPage />} />
        <Route path="/reviews/:owner/:repo/:number" element={<div>Review page placeholder</div>} />
      </Routes>,
      { route: '/pull-requests/acme/webapp/101', authToken: TEST_TOKEN },
    );

    expect(await screen.findByRole('heading', { name: /Add auth flow/i })).toBeInTheDocument();
    expect(screen.getByText(/feature\/auth/)).toBeInTheDocument();
    expect(await screen.findByText('src/auth.ts')).toBeInTheDocument();
    expect(screen.getByText('+12')).toBeInTheDocument();
    expect(await screen.findByText(/secureLogin/)).toBeInTheDocument();
    expect(screen.getByText(/const token = process.env.TOKEN/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /run ai review/i }));
    expect(await screen.findByText('Review page placeholder')).toBeInTheDocument();
  });

  it('shows an error state when the pull request cannot be loaded', async () => {
    mocks.getPullRequest.mockRejectedValue(new Error('Could not fetch pull request'));

    renderWithProviders(<PullRequestDetailPage />, {
      route: '/pull-requests/acme/webapp/101',
      authToken: TEST_TOKEN,
    });

    expect(await screen.findByRole('alert')).toHaveTextContent(/could not load this pull request/i);
  });
});