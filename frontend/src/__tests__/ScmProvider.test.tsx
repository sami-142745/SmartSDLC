import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { Route, Routes } from 'react-router-dom';

const mocks = vi.hoisted(() => ({
  getRepositories: vi.fn(),
  getPullRequests: vi.fn(),
  getPullRequest: vi.fn(),
  getPullRequestFiles: vi.fn(),
  getPullRequestDiff: vi.fn(),
  runReview: vi.fn(),
}));

vi.mock('../api/auth', () => ({
  exchangeCode: vi.fn(),
  getLoginUrl: vi.fn(),
  validateToken: vi.fn(),
  userFromToken: vi.fn(() => null),
}));

vi.mock('../api/reviews', () => ({
  getFeedbackHistory: vi.fn(async () => ({ items: [], total: 0 })),
  getFeedbackLearning: vi.fn(),
  getReviewFindings: vi.fn(),
  getReviews: vi.fn(async () => []),
  loadFeedbackAction: vi.fn(),
  recordFeedbackLearning: vi.fn(),
  runReview: mocks.runReview,
}));

vi.mock('../api/github', () => ({ ...mocks }));

import { RepositoriesPage } from '../pages/RepositoriesPage';
import { PullRequestsPage } from '../pages/PullRequestsPage';
import { RepoPage } from '../pages/RepoPage';
import { PullRequestDetailPage } from '../pages/PullRequestDetailPage';
import { repositories, pullRequests, pullRequestFiles, pullRequestDiff } from '../test/fixtures';
import { renderWithProviders, TEST_USER } from '../test/utils';
import { TEST_TOKEN } from '../test/fixtures';

const repositoriesResponse = {
  repositories,
  page: 1,
  per_page: 30,
  has_more: false,
};
const pullRequestsResponse = {
  pull_requests: pullRequests,
  page: 1,
  per_page: 30,
  has_more: false,
};

beforeEach(() => {
  mocks.getRepositories.mockReset().mockResolvedValue(repositoriesResponse);
  mocks.getPullRequests.mockReset().mockResolvedValue(pullRequestsResponse);
  mocks.getPullRequest.mockReset().mockResolvedValue(pullRequests[0]);
  mocks.getPullRequestFiles.mockReset().mockResolvedValue(pullRequestFiles);
  mocks.getPullRequestDiff.mockReset().mockResolvedValue(pullRequestDiff);
});

describe('source provider switching', () => {
  it('RepositoriesPage fetches GitLab repositories after toggling provider', async () => {
    renderWithProviders(<RepositoriesPage />, { route: '/repositories', authToken: TEST_TOKEN });
    await waitFor(() => expect(mocks.getRepositories).toHaveBeenCalledWith(1, 30, 'github'));

    mocks.getRepositories.mockResolvedValueOnce({
      repositories: [],
      page: 1,
      per_page: 30,
      has_more: false,
    });
    fireEvent.click(screen.getByRole('tab', { name: 'GitLab' }));

    await waitFor(() => expect(mocks.getRepositories).toHaveBeenLastCalledWith(1, 30, 'gitlab'));
    expect(screen.getByText(/GitLab account has access/i)).toBeInTheDocument();
    expect(screen.getByText(/GitLab · live feed/i)).toBeInTheDocument();
  });

  it('PullRequestsPage adopts merge request terminology for GitLab', async () => {
    renderWithProviders(<PullRequestsPage />, { route: '/pull-requests', authToken: TEST_TOKEN });
    await waitFor(() => expect(mocks.getRepositories).toHaveBeenCalledWith(1, 100, 'github'));
    expect(screen.getByText('PULL')).toBeInTheDocument();
    expect(screen.getByText('REQUESTS')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: 'GitLab' }));

    await waitFor(() =>
      expect(mocks.getRepositories).toHaveBeenLastCalledWith(1, 100, 'gitlab'),
    );
    expect(screen.getByRole('heading', { level: 1 }).textContent).toContain('MERGE');
    expect(screen.getByText(/Forwarded change pipeline · GitLab/i)).toBeInTheDocument();
  });

  it('RepoPage renders GitLab terminology and opens GitLab from ?provider=gitlab', async () => {
    renderWithProviders(
      <Routes>
        <Route path="/repositories/:owner/:repo" element={<RepoPage />} />
      </Routes>,
      { route: '/repositories/acme/webapp?provider=gitlab', authToken: TEST_TOKEN },
    );
    await waitFor(() =>
      expect(mocks.getPullRequests).toHaveBeenLastCalledWith('acme', 'webapp', 'open', 1, 30, 'gitlab'),
    );
    expect(screen.getByRole('link', { name: /Open on GitLab/i })).toBeInTheDocument();
    expect(screen.getByText(/Repository security map · GitLab/i)).toBeInTheDocument();
  });

  it('PullRequestDetailPage links out to GitLab and keeps provider on detail calls', async () => {
    renderWithProviders(
      <Routes>
        <Route path="/pull-requests/:owner/:repo/:number" element={<PullRequestDetailPage />} />
      </Routes>,
      {
        route: '/pull-requests/acme/webapp/101?provider=gitlab',
        authToken: TEST_TOKEN,
        authUser: TEST_USER,
      },
    );
    const gitlabLink = await screen.findByRole('link', { name: /Open on GitLab/i });
    expect(gitlabLink).toBeInTheDocument();
    await waitFor(() =>
      expect(mocks.getPullRequest).toHaveBeenLastCalledWith('acme', 'webapp', 101, 'gitlab'),
    );
  });
});