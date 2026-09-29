import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen } from '@testing-library/react';

const mocks = vi.hoisted(() => ({
  getRepositoryMetrics: vi.fn(),
  getDocumentations: vi.fn(),
  getInsights: vi.fn(),
}));

vi.mock('../api/dashboard', () => ({
  getRepositoryMetrics: mocks.getRepositoryMetrics,
  getDashboard: vi.fn(),
  getFeedbackSummary: vi.fn(),
  getHistory: vi.fn(),
}));
vi.mock('../api/documents', () => ({
  getDocumentations: mocks.getDocumentations,
  generateDocumentation: vi.fn(),
  getDocumentation: vi.fn(),
  getRepositoryDocumentation: vi.fn(),
}));
vi.mock('../api/insights', () => ({
  getInsights: mocks.getInsights,
  generateInsight: vi.fn(),
  getLatestRepositoryInsight: vi.fn(),
  getInsight: vi.fn(),
}));

import { ArchitecturePage } from '../pages/ArchitecturePage';
import { repoMetrics, TEST_TOKEN } from '../test/fixtures';
import { renderWithProviders } from '../test/utils';

beforeEach(() => {
  mocks.getRepositoryMetrics.mockReset().mockResolvedValue(repoMetrics);
  mocks.getDocumentations.mockReset().mockResolvedValue({
    items: [],
    page: 1,
    per_page: 25,
    total: 0,
    total_pages: 0,
  });
  mocks.getInsights.mockReset().mockResolvedValue({
    items: [],
    page: 1,
    per_page: 10,
    total: 0,
    total_pages: 0,
  });
});

describe('ArchitecturePage', () => {
  it('renders the service topology and defect density by default', async () => {
    renderWithProviders(<ArchitecturePage />, { route: '/architecture', authToken: TEST_TOKEN });

    expect(await screen.findByRole('heading', { name: 'Architecture' })).toBeInTheDocument();
    expect(screen.getByText('Service topology')).toBeInTheDocument();
    expect(screen.getByText('Defect density')).toBeInTheDocument();
    expect(screen.getByText('Services')).toBeInTheDocument();
    expect(screen.getByText('acme/webapp')).toBeInTheDocument();
  });

  it('switches to the module inventory tab', async () => {
    renderWithProviders(<ArchitecturePage />, { route: '/architecture', authToken: TEST_TOKEN });

    const tab = await screen.findByRole('tab', { name: /modules/i });
    tab.click();

    expect(await screen.findByText('Module inventory')).toBeInTheDocument();
  });

  it('shows an error state when the metrics call fails', async () => {
    mocks.getRepositoryMetrics.mockRejectedValue(new Error('Backend unreachable'));

    renderWithProviders(<ArchitecturePage />, { route: '/architecture', authToken: TEST_TOKEN });

    expect(await screen.findByRole('alert')).toHaveTextContent(/could not load the architecture view/i);
  });
});
