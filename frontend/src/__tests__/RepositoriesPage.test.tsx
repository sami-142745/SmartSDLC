import { describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { Route, Routes } from 'react-router-dom';

const mocks = vi.hoisted(() => ({
  getRepositories: vi.fn(),
}));

vi.mock('../api/github', () => ({
  ...mocks,
  getPullRequests: vi.fn(),
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

import { RepositoriesPage } from '../pages/RepositoriesPage';
import { repositories } from '../test/fixtures';
import { renderWithProviders } from '../test/utils';
import { TEST_TOKEN } from '../test/fixtures';

describe('RepositoriesPage', () => {
  it('lists repositories and navigates to a repository on click', async () => {
    mocks.getRepositories.mockResolvedValue({
      repositories,
      page: 1,
      per_page: 30,
      has_more: false,
    });

    renderWithProviders(
      <Routes>
        <Route path="/repositories" element={<RepositoriesPage />} />
        <Route path="/repositories/:owner/:repo" element={<div>Repo page placeholder</div>} />
      </Routes>,
      { route: '/repositories', authToken: TEST_TOKEN },
    );

    expect(await screen.findByText('acme/webapp')).toBeInTheDocument();
    expect(screen.getByText('acme/api')).toBeInTheDocument();
    expect(screen.getByText('Private')).toBeInTheDocument();
    expect(screen.getByText('Public')).toBeInTheDocument();

    const card = screen.getByRole('button', { name: /acme\/webapp/i });
    fireEvent.click(card);

    expect(await screen.findByText('Repo page placeholder')).toBeInTheDocument();
  });

  it('shows an empty state when there are no repositories', async () => {
    mocks.getRepositories.mockResolvedValue({
      repositories: [],
      page: 1,
      per_page: 30,
      has_more: false,
    });

    renderWithProviders(<RepositoriesPage />, { route: '/repositories', authToken: TEST_TOKEN });

    expect(await screen.findByText('No repositories found')).toBeInTheDocument();
  });
});