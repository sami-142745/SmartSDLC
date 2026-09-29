import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen } from '@testing-library/react';

const mocks = vi.hoisted(() => ({
  getRepositoryMetrics: vi.fn(),
  getTestGeneration: vi.fn(),
}));

vi.mock('../api/dashboard', () => ({
  getRepositoryMetrics: mocks.getRepositoryMetrics,
  getDashboard: vi.fn(),
  getFeedbackSummary: vi.fn(),
  getHistory: vi.fn(),
}));

vi.mock('../api/testGeneration', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/testGeneration')>();
  return { ...actual, getTestGeneration: mocks.getTestGeneration };
});

import { TestGeneratorPage } from '../pages/TestGeneratorPage';
import { repoMetrics, TEST_TOKEN, testGeneration } from '../test/fixtures';
import { renderWithProviders } from '../test/utils';

beforeEach(() => {
  mocks.getRepositoryMetrics.mockReset().mockResolvedValue(repoMetrics);
  mocks.getTestGeneration.mockReset().mockResolvedValue(testGeneration());
});

describe('TestGeneratorPage', () => {
  it('renders the page and proposes tests for the first repository', async () => {
    renderWithProviders(<TestGeneratorPage />, {
      route: '/test-generator',
      authToken: TEST_TOKEN,
    });

    expect(await screen.findByRole('heading', { name: 'Test generator' })).toBeInTheDocument();
    expect(await screen.findByText('Untested symbols')).toBeInTheDocument();
    expect(mocks.getTestGeneration).toHaveBeenCalledWith('acme', 'webapp', {
      provider: 'github',
      refresh: false,
    });
  });

  it('states the three boundaries on screen rather than leaving them implied', async () => {
    renderWithProviders(<TestGeneratorPage />, {
      route: '/test-generator',
      authToken: TEST_TOKEN,
    });

    expect(await screen.findByText(/Targets are chosen by measurement/i)).toBeInTheDocument();
    expect(screen.getByText(/Nothing generated is ever run/i)).toBeInTheDocument();
    // Preview-only: there is no route that writes to the repository.
    expect(screen.getByText(/no route that commits, pushes or opens a pull request/i)).toBeInTheDocument();
  });

  it('shows an error state when the metrics call fails', async () => {
    mocks.getRepositoryMetrics.mockRejectedValue(new Error('Backend unreachable'));

    renderWithProviders(<TestGeneratorPage />, {
      route: '/test-generator',
      authToken: TEST_TOKEN,
    });

    expect(await screen.findByRole('alert')).toHaveTextContent(
      /could not load the test generation view/i,
    );
  });
});
