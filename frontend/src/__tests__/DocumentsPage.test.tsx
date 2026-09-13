import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen } from '@testing-library/react';

const reposMocks = vi.hoisted(() => ({
  getRepositories: vi.fn(),
}));

const documentsMocks = vi.hoisted(() => ({
  generateDocumentation: vi.fn(),
  getDocumentations: vi.fn(),
  getDocumentation: vi.fn(),
  getRepositoryDocumentation: vi.fn(),
}));

vi.mock('../api/github', () => ({
  ...reposMocks,
  getPullRequests: vi.fn(),
  getPullRequest: vi.fn(),
  getPullRequestFiles: vi.fn(),
  getPullRequestDiff: vi.fn(),
}));

vi.mock('../api/documents', () => documentsMocks);

vi.mock('../api/auth', () => ({
  exchangeCode: vi.fn(),
  getLoginUrl: vi.fn(),
  validateToken: vi.fn(),
  userFromToken: vi.fn(() => null),
}));

import { DocumentsPage } from '../pages/DocumentsPage';
import { repositories, documentationHistory, documentationResponse } from '../test/fixtures';
import { renderWithProviders } from '../test/utils';
import { TEST_TOKEN } from '../test/fixtures';

function renderPage() {
  return renderWithProviders(<DocumentsPage />, {
    route: '/documents',
    authToken: TEST_TOKEN,
  });
}

describe('DocumentsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    reposMocks.getRepositories.mockResolvedValue({
      repositories,
      page: 1,
      per_page: 100,
      has_more: false,
    });
    documentsMocks.getDocumentations.mockResolvedValue({
      items: [],
      page: 1,
      per_page: 50,
      total: 0,
      total_pages: 0,
    });
  });

  it('lists repositories in the generator selector', async () => {
    renderPage();

    expect(await screen.findByText('AI DOCUMENTATION')).toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: /repository/i })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'acme/webapp' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'acme/api' })).toBeInTheDocument();
    expect(screen.getByText('No documentation yet')).toBeInTheDocument();
  });

  it('shows a loading state while repositories are loading', () => {
    reposMocks.getRepositories.mockReturnValue(new Promise(() => {}));

    renderPage();

    expect(screen.getByText(/Loading repositories/)).toBeInTheDocument();
  });

  it('shows an error when repositories fail to load', async () => {
    reposMocks.getRepositories.mockRejectedValue(new Error('GitHub unreachable'));

    renderPage();

    expect(await screen.findByRole('alert')).toBeInTheDocument();
    expect(screen.getByText(/could not load repositories/i)).toBeInTheDocument();
  });

  it('generates documentation for the selected repository', async () => {
    documentsMocks.generateDocumentation.mockResolvedValue(documentationResponse);
    renderPage();

    const select = await screen.findByRole('combobox', { name: /repository/i });
    fireEvent.change(select, { target: { value: 'acme/webapp' } });

    fireEvent.click(screen.getByRole('button', { name: /generate documentation/i }));

    expect(await screen.findByText('acme/webapp guide')).toBeInTheDocument();
    expect(screen.getByText('Summarizes the web application.')).toBeInTheDocument();
    expect(screen.getByText(/acme\/webapp · #12 · branch main/)).toBeInTheDocument();
    expect(documentsMocks.generateDocumentation).toHaveBeenCalledWith(
      expect.objectContaining({ owner: 'acme', repository: 'webapp' }),
    );
  });

  it('sends the optional pull request number', async () => {
    documentsMocks.generateDocumentation.mockResolvedValue(documentationResponse);
    renderPage();

    const select = await screen.findByRole('combobox', { name: /repository/i });
    fireEvent.change(select, { target: { value: 'acme/api' } });

    fireEvent.change(screen.getByLabelText(/pull request number \(optional\)/i), {
      target: { value: '12' },
    });

    fireEvent.click(screen.getByRole('button', { name: /generate documentation/i }));

    expect(await screen.findByText('acme/webapp guide')).toBeInTheDocument();
    expect(documentsMocks.generateDocumentation).toHaveBeenCalledWith(
      expect.objectContaining({ repository: 'api', pull_request: 12 }),
    );
  });

  it('shows an error message when generation fails', async () => {
    documentsMocks.generateDocumentation.mockRejectedValue(new Error('AI engine unavailable'));
    renderPage();

    const select = await screen.findByRole('combobox', { name: /repository/i });
    fireEvent.change(select, { target: { value: 'acme/webapp' } });
    fireEvent.click(screen.getByRole('button', { name: /generate documentation/i }));

    expect(await screen.findByText('AI engine unavailable')).toBeInTheDocument();
  });

  it('refreshes the vault after generating', async () => {
    documentsMocks.getDocumentations.mockResolvedValueOnce({
      items: [],
      page: 1,
      per_page: 50,
      total: 0,
      total_pages: 0,
    });
    documentsMocks.getDocumentations.mockResolvedValueOnce(documentationHistory);
    documentsMocks.generateDocumentation.mockResolvedValue(documentationResponse);

    renderPage();

    const select = await screen.findByRole('combobox', { name: /repository/i });
    fireEvent.change(select, { target: { value: 'acme/webapp' } });
    fireEvent.click(screen.getByRole('button', { name: /generate documentation/i }));

    expect(await screen.findByText('Summarizes the web application.')).toBeInTheDocument();
    expect(documentsMocks.getDocumentations).toHaveBeenCalledTimes(2);
    expect(documentsMocks.generateDocumentation).toHaveBeenCalledTimes(1);
  });

  it('opens an archived document from the vault', async () => {
    documentsMocks.getDocumentations.mockResolvedValue(documentationHistory);

    renderPage();

    expect(await screen.findByText('No documentation displayed')).toBeInTheDocument();

    fireEvent.click(await screen.findByRole('button', { name: /^acme\/webapp guide/ }));

    expect(screen.getByText('Summarizes the web application.')).toBeInTheDocument();
    expect(screen.getByText('Client-server.')).toBeInTheDocument();
  });
});