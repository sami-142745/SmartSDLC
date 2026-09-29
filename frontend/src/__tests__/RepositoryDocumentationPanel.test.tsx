import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const mocks = vi.hoisted(() => ({
  getDocumentationIntelligence: vi.fn(),
}));

vi.mock('../api/documentationIntelligence', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/documentationIntelligence')>();
  return { ...actual, getDocumentationIntelligence: mocks.getDocumentationIntelligence };
});

import { RepositoryDocumentationPanel } from '../components/documentation/RepositoryDocumentationPanel';
import { documentationIntelligence } from '../test/fixtures';
import { renderWithProviders } from '../test/utils';

const OPTIONS = [
  { owner: 'acme', repository: 'webapp' },
  { owner: 'acme', repository: 'api' },
];

beforeEach(() => {
  mocks.getDocumentationIntelligence.mockReset().mockResolvedValue(documentationIntelligence());
});

describe('RepositoryDocumentationPanel', () => {
  it('renders the coverage score and the measured counts', async () => {
    renderWithProviders(
      <RepositoryDocumentationPanel options={OPTIONS} provider="github" />,
      { route: '/documentation-coverage' },
    );

    expect(await screen.findByText('Coverage score')).toBeInTheDocument();
    expect(screen.getByText('62/100')).toBeInTheDocument();
    expect(screen.getByText('67%')).toBeInTheDocument();
    expect(screen.getByText('Docs / source')).toBeInTheDocument();
    expect(mocks.getDocumentationIntelligence).toHaveBeenCalledWith('acme', 'webapp', {
      provider: 'github',
      refresh: false,
    });
  });

  it('shows the evidence behind each gap rather than a bare verdict', async () => {
    renderWithProviders(
      <RepositoryDocumentationPanel options={OPTIONS} provider="github" />,
      { route: '/documentation-coverage' },
    );

    await screen.findByText('No license file');
    expect(
      screen.getByText('No LICENSE/COPYING file was found in the repository tree.'),
    ).toBeInTheDocument();
  });

  it('lists the files least covered by docstrings with their undocumented names', async () => {
    renderWithProviders(
      <RepositoryDocumentationPanel options={OPTIONS} provider="github" />,
      { route: '/documentation-coverage' },
    );

    expect(await screen.findByText('app/services/auth.py')).toBeInTheDocument();
    expect(screen.getByText(/verify_token/)).toBeInTheDocument();
  });

  it('states partial coverage instead of presenting a truncated report as complete', async () => {
    mocks.getDocumentationIntelligence.mockResolvedValue(
      documentationIntelligence({ truncated: true }),
    );
    renderWithProviders(
      <RepositoryDocumentationPanel options={OPTIONS} provider="github" />,
      { route: '/documentation-coverage' },
    );

    expect(await screen.findByText(/Partial analysis/)).toBeInTheDocument();
  });

  it('warns when no public symbols were measured, so a 0% is not read as a verdict', async () => {
    mocks.getDocumentationIntelligence.mockResolvedValue(
      documentationIntelligence({
        coverage: [],
        summary: {
          ...documentationIntelligence().summary,
          public_symbols: 0,
          documented_symbols: 0,
          docstring_coverage: 0,
        },
      }),
    );
    renderWithProviders(
      <RepositoryDocumentationPanel options={OPTIONS} provider="github" />,
      { route: '/documentation-coverage' },
    );

    expect(await screen.findByText(/No public source symbols were measured/)).toBeInTheDocument();
  });

  it('filters gaps by severity', async () => {
    const user = userEvent.setup();
    mocks.getDocumentationIntelligence.mockResolvedValue(
      documentationIntelligence({
        gaps: [
          {
            kind: 'missing_license',
            severity: 'warning',
            title: 'No license file',
            detail: '',
            evidence: '',
            paths: [],
          },
          {
            kind: 'no_docs_directory',
            severity: 'info',
            title: 'No docs directory',
            detail: '',
            evidence: '',
            paths: [],
          },
        ],
      }),
    );
    renderWithProviders(
      <RepositoryDocumentationPanel options={OPTIONS} provider="github" />,
      { route: '/documentation-coverage' },
    );

    await screen.findByText('No license file');
    await user.click(screen.getByRole('button', { name: 'info' }));

    expect(screen.getByText('No docs directory')).toBeInTheDocument();
    expect(screen.queryByText('No license file')).not.toBeInTheDocument();
  });

  it('searches documentation files by path', async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <RepositoryDocumentationPanel options={OPTIONS} provider="github" />,
      { route: '/documentation-coverage' },
    );

    await screen.findByText('Documentation files');
    await user.type(screen.getByLabelText(/search documents/i), 'guide');

    expect(screen.getByText('docs/guide.md')).toBeInTheDocument();
    expect(screen.queryByText('README.md')).not.toBeInTheDocument();
  });

  it('counts broken links per document', async () => {
    renderWithProviders(
      <RepositoryDocumentationPanel options={OPTIONS} provider="github" />,
      { route: '/documentation-coverage' },
    );

    const table = await screen.findByRole('table');
    const row = within(table).getByText('docs/guide.md').closest('tr');
    expect(row).not.toBeNull();
    const cells = within(row as HTMLElement).getAllByRole('cell');
    // The final column is the broken-link count: one unresolvable relative link.
    expect(cells[cells.length - 1]).toHaveTextContent('1');
    expect(cells[cells.length - 1].className).toContain('text-amber-300');
  });

  it('re-analyses on request', async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <RepositoryDocumentationPanel options={OPTIONS} provider="github" />,
      { route: '/documentation-coverage' },
    );

    await screen.findByText('Coverage score');
    await user.click(screen.getByRole('button', { name: /re-analyse/i }));

    expect(mocks.getDocumentationIntelligence).toHaveBeenLastCalledWith('acme', 'webapp', {
      provider: 'github',
      refresh: true,
    });
  });

  it('switches repository when another option is selected', async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <RepositoryDocumentationPanel options={OPTIONS} provider="github" />,
      { route: '/documentation-coverage' },
    );

    await screen.findByText('Coverage score');
    await user.selectOptions(screen.getByLabelText(/repository/i), 'acme/api');

    expect(mocks.getDocumentationIntelligence).toHaveBeenLastCalledWith('acme', 'api', {
      provider: 'github',
      refresh: false,
    });
  });

  it('surfaces an error with a retry when the analysis fails', async () => {
    mocks.getDocumentationIntelligence.mockRejectedValue(new Error('Token expired'));
    renderWithProviders(
      <RepositoryDocumentationPanel options={OPTIONS} provider="github" />,
      { route: '/documentation-coverage' },
    );

    expect(
      await screen.findByText(/Could not measure this repository's documentation/),
    ).toBeInTheDocument();
  });

  it('explains an empty repository rather than showing a zeroed report', async () => {
    mocks.getDocumentationIntelligence.mockResolvedValue(
      documentationIntelligence({ assets: [], coverage: [], gaps: [] }),
    );
    renderWithProviders(
      <RepositoryDocumentationPanel options={OPTIONS} provider="github" />,
      { route: '/documentation-coverage' },
    );

    expect(await screen.findByText('Nothing to measure')).toBeInTheDocument();
  });

  it('does not call the API when there is no repository to analyse', () => {
    renderWithProviders(<RepositoryDocumentationPanel options={[]} provider="github" />, {
      route: '/documentation-coverage',
    });

    expect(screen.getByText('No repository to analyse')).toBeInTheDocument();
    expect(mocks.getDocumentationIntelligence).not.toHaveBeenCalled();
  });
});
