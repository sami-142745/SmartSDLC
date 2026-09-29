import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen } from '@testing-library/react';

const mocks = vi.hoisted(() => ({
  getRepositoryMetrics: vi.fn(),
  getDocumentationIntelligence: vi.fn(),
}));

vi.mock('../api/dashboard', () => ({
  getRepositoryMetrics: mocks.getRepositoryMetrics,
  getDashboard: vi.fn(),
  getFeedbackSummary: vi.fn(),
  getHistory: vi.fn(),
}));

vi.mock('../api/documentationIntelligence', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/documentationIntelligence')>();
  return { ...actual, getDocumentationIntelligence: mocks.getDocumentationIntelligence };
});

import { DocumentationCoveragePage } from '../pages/DocumentationCoveragePage';
import { documentationIntelligence, repoMetrics, TEST_TOKEN } from '../test/fixtures';
import { renderWithProviders } from '../test/utils';

beforeEach(() => {
  mocks.getRepositoryMetrics.mockReset().mockResolvedValue(repoMetrics);
  mocks.getDocumentationIntelligence.mockReset().mockResolvedValue(documentationIntelligence());
});

describe('DocumentationCoveragePage', () => {
  it('renders the page and measures the first repository', async () => {
    renderWithProviders(<DocumentationCoveragePage />, {
      route: '/documentation-coverage',
      authToken: TEST_TOKEN,
    });

    expect(
      await screen.findByRole('heading', { name: 'Documentation coverage' }),
    ).toBeInTheDocument();
    expect(await screen.findByText('Coverage score')).toBeInTheDocument();
    expect(mocks.getDocumentationIntelligence).toHaveBeenCalledWith('acme', 'webapp', {
      provider: 'github',
      refresh: false,
    });
  });

  it('states that no model is involved', async () => {
    renderWithProviders(<DocumentationCoveragePage />, {
      route: '/documentation-coverage',
      authToken: TEST_TOKEN,
    });

    expect(await screen.findByText(/no model is involved/i)).toBeInTheDocument();
  });

  it('shows an error state when the metrics call fails', async () => {
    mocks.getRepositoryMetrics.mockRejectedValue(new Error('Backend unreachable'));

    renderWithProviders(<DocumentationCoveragePage />, {
      route: '/documentation-coverage',
      authToken: TEST_TOKEN,
    });

    expect(await screen.findByRole('alert')).toHaveTextContent(
      /could not load the documentation coverage view/i,
    );
  });
});
