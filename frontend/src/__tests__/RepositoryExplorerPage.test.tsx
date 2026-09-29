import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const apiMocks = vi.hoisted(() => ({
  getRepositoryTree: vi.fn(),
  getRepositoryFile: vi.fn(),
}));

vi.mock('../api/repositoryIntelligence', () => apiMocks);
vi.mock('@monaco-editor/react', () => ({
  Editor: ({ value }: { value: string }) => <pre data-testid="monaco-editor">{value}</pre>,
  DiffEditor: () => <div data-testid="monaco-diff" />,
}));

import { RepositoryExplorerPage } from '../pages/RepositoryExplorerPage';
import { repositoryFile, repositoryTree } from '../test/fixtures';
import { renderRoute } from '../test/utils';

const ROUTE = '/repository-intelligence/:owner/:repo/explorer';

function renderPage(route = '/repository-intelligence/acme/webapp/explorer') {
  return renderRoute(ROUTE, <RepositoryExplorerPage />, { route });
}

beforeEach(() => {
  vi.clearAllMocks();
  apiMocks.getRepositoryTree.mockResolvedValue(repositoryTree);
  apiMocks.getRepositoryFile.mockResolvedValue(repositoryFile);
});

describe('RepositoryExplorerPage', () => {
  it('renders the tree with file and directory counts', async () => {
    renderPage();

    expect(await screen.findByText('File tree')).toBeInTheDocument();
    expect(screen.getByText('2 files')).toBeInTheDocument();
    expect(screen.getByText('1 dirs')).toBeInTheDocument();
  });

  it('requests the tree for the routed repository', async () => {
    renderPage();

    await waitFor(() =>
      expect(apiMocks.getRepositoryTree).toHaveBeenCalledWith('acme', 'webapp', {
        provider: 'github',
      }),
    );
  });

  it('loads a file when a file entry is selected', async () => {
    renderPage();
    await screen.findByText('index.ts');

    await userEvent.click(screen.getByRole('button', { name: /index\.ts/ }));

    await waitFor(() =>
      expect(apiMocks.getRepositoryFile).toHaveBeenCalledWith('acme', 'webapp', 'src/index.ts', {
        provider: 'github',
      }),
    );
    expect(await screen.findByTestId('monaco-editor')).toHaveTextContent('export const main');
  });

  it('does not request a file when a directory is selected', async () => {
    renderPage();
    await screen.findByText('src');

    // Directory rows are not actionable.
    expect(screen.getByRole('button', { name: /^src/ })).toBeDisabled();
    expect(apiMocks.getRepositoryFile).not.toHaveBeenCalled();
  });

  it('reports a failure to open a single file without losing the tree', async () => {
    apiMocks.getRepositoryFile.mockRejectedValue({ message: 'File too large.' });

    renderPage();
    await screen.findByText('index.ts');
    await userEvent.click(screen.getByRole('button', { name: /index\.ts/ }));

    expect(await screen.findByText('Could not open this file')).toBeInTheDocument();
    expect(screen.getByText('File tree')).toBeInTheDocument();
  });

  it('flags a truncated tree as a partial listing', async () => {
    apiMocks.getRepositoryTree.mockResolvedValue({
      ...repositoryTree,
      truncated: true,
    });

    renderPage();

    expect(await screen.findByText(/Partial listing/)).toBeInTheDocument();
  });

  it('explains a binary file instead of rendering it', async () => {
    apiMocks.getRepositoryFile.mockResolvedValue({
      ...repositoryFile,
      binary: true,
      path: 'assets/logo.png',
      content: '',
      language: null,
    });

    renderPage();
    await screen.findByText('index.ts');
    await userEvent.click(screen.getByRole('button', { name: /index\.ts/ }));

    expect(await screen.findByText('Binary file')).toBeInTheDocument();
    expect(screen.queryByTestId('monaco-editor')).not.toBeInTheDocument();
  });

  it('surfaces a retryable error when the tree request fails', async () => {
    apiMocks.getRepositoryTree.mockRejectedValue({ message: 'Provider unreachable.' });

    renderPage();

    expect(await screen.findByText('Could not load the repository tree')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
  });

  it('does not call the API for an unresolved repository', async () => {
    renderRoute('/repository-intelligence/:owner', <RepositoryExplorerPage />, {
      route: '/repository-intelligence/acme',
    });

    expect(await screen.findByText('No repository selected')).toBeInTheDocument();
    expect(apiMocks.getRepositoryTree).not.toHaveBeenCalled();
  });
});
