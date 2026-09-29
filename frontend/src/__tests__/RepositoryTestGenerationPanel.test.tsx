import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const mocks = vi.hoisted(() => ({
  getTestGeneration: vi.fn(),
}));

vi.mock('../api/testGeneration', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/testGeneration')>();
  return { ...actual, getTestGeneration: mocks.getTestGeneration };
});

import { RepositoryTestGenerationPanel } from '../components/test-generation/RepositoryTestGenerationPanel';
import { generatedTestFile, testGeneration } from '../test/fixtures';
import { renderWithProviders } from '../test/utils';

const OPTIONS = [
  { owner: 'acme', repository: 'webapp' },
  { owner: 'acme', repository: 'api' },
];

beforeEach(() => {
  mocks.getTestGeneration.mockReset().mockResolvedValue(testGeneration());
});

describe('RepositoryTestGenerationPanel', () => {
  it('renders the measured counts and the detected framework', async () => {
    renderWithProviders(
      <RepositoryTestGenerationPanel options={OPTIONS} provider="github" />,
      { route: '/test-generator' },
    );

    expect(await screen.findByText('Framework')).toBeInTheDocument();
    expect(screen.getByText('pytest')).toBeInTheDocument();
    expect(screen.getByText('Untested')).toBeInTheDocument();
    expect(mocks.getTestGeneration).toHaveBeenCalledWith('acme', 'webapp', {
      provider: 'github',
      refresh: false,
    });
  });

  it('shows the evidence behind each target rather than a bare symbol name', async () => {
    renderWithProviders(
      <RepositoryTestGenerationPanel options={OPTIONS} provider="github" />,
      { route: '/test-generator' },
    );

    expect(await screen.findByText('normalise_path')).toBeInTheDocument();
    expect(
      screen.getByText('3 test file(s) in the repository reference none of `normalise_path`.'),
    ).toBeInTheDocument();
  });

  it('orders targets by priority, highest first', async () => {
    renderWithProviders(
      <RepositoryTestGenerationPanel options={OPTIONS} provider="github" />,
      { route: '/test-generator' },
    );

    const list = await screen.findByText('ScmProvider.authorise_request');
    const rows = screen.getAllByRole('listitem').map((item) => item.textContent ?? '');
    const high = rows.findIndex((text) => text.includes('authorise_request'));
    const low = rows.findIndex((text) => text.includes('normalise_path'));
    expect(high).toBeLessThan(low);
    expect(list).toBeInTheDocument();
  });

  it('separates a model-written run from a scaffold-only run', async () => {
    renderWithProviders(
      <RepositoryTestGenerationPanel options={OPTIONS} provider="github" />,
      { route: '/test-generator' },
    );

    // The fixture has one of each, so the badge must reflect the model-written
    // file rather than claiming the scaffolds are the whole output.
    expect(await screen.findByText('1 model-written file')).toBeInTheDocument();

    mocks.getTestGeneration.mockResolvedValue(
      testGeneration({
        files: [generatedTestFile({ source: 'deterministic', model: null })],
      }),
    );
    renderWithProviders(
      <RepositoryTestGenerationPanel options={OPTIONS} provider="github" />,
      { route: '/test-generator' },
    );

    expect(await screen.findByText('Scaffolds only — no assertions were written')).toBeInTheDocument();
  });

  it('names a flagged file as needing review instead of counting it as a success', async () => {
    renderWithProviders(
      <RepositoryTestGenerationPanel options={OPTIONS} provider="github" />,
      { route: '/test-generator' },
    );

    // The fixture's second file is a rejected scaffold. The verdict has to
    // appear on the review summary and on the file row: two occurrences, so
    // dropping either surface fails here rather than silently hiding it.
    await screen.findByText('tests/test_scm_scaffold.py');
    expect(screen.getAllByText('Rejected')).toHaveLength(2);
    // The finding behind it is named, not just counted.
    expect(screen.getAllByText('Placeholder').length).toBeGreaterThan(0);
    expect(
      screen.getAllByText('No language model was available, so these tests assert nothing.').length,
    ).toBeGreaterThan(0);
  });

  it('shows no review badges when every proposed file passed screening', async () => {
    mocks.getTestGeneration.mockResolvedValue(
      testGeneration({ files: [generatedTestFile({ path: 'tests/clean.py' })] }),
    );
    renderWithProviders(
      <RepositoryTestGenerationPanel options={OPTIONS} provider="github" />,
      { route: '/test-generator' },
    );

    expect(await screen.findByText('No proposed file carries a screening finding.')).toBeInTheDocument();
    expect(screen.queryByText('Rejected')).not.toBeInTheDocument();
  });

  it('expands a proposed file to show its content', async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <RepositoryTestGenerationPanel options={OPTIONS} provider="github" />,
      { route: '/test-generator' },
    );

    await screen.findByText('tests/test_scm.py');
    expect(screen.queryByText(/from app.services.scm import normalise_path/)).not.toBeInTheDocument();

    await user.click(screen.getAllByRole('button', { name: 'View' })[0]);

    expect(await screen.findByText(/from app.services.scm import normalise_path/)).toBeInTheDocument();
  });

  it('states that nothing is written to the repository', async () => {
    renderWithProviders(
      <RepositoryTestGenerationPanel options={OPTIONS} provider="github" />,
      { route: '/test-generator' },
    );

    expect(await screen.findByText(/nothing is written to the repository/i)).toBeInTheDocument();
  });

  it('searches proposed files by path and by covered symbol', async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <RepositoryTestGenerationPanel options={OPTIONS} provider="github" />,
      { route: '/test-generator' },
    );

    await screen.findByText('tests/test_scm.py');
    await user.type(screen.getByLabelText(/search files and symbols/i), 'scaffold');

    expect(screen.getByText('tests/test_scm_scaffold.py')).toBeInTheDocument();
    expect(screen.queryByText('tests/test_scm.py')).not.toBeInTheDocument();
    // The review summary follows the same filter, so it cannot keep describing
    // a file the search has hidden.
    expect(screen.queryByText('2 files')).not.toBeInTheDocument();
  });

  it('says a capped run is partial rather than presenting it as complete', async () => {
    mocks.getTestGeneration.mockResolvedValue(testGeneration({ truncated: true }));
    renderWithProviders(
      <RepositoryTestGenerationPanel options={OPTIONS} provider="github" />,
      { route: '/test-generator' },
    );

    expect(await screen.findByText(/Partial analysis/)).toBeInTheDocument();
  });

  it('regenerates on request', async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <RepositoryTestGenerationPanel options={OPTIONS} provider="github" />,
      { route: '/test-generator' },
    );

    await screen.findByText('Framework');
    await user.click(screen.getByRole('button', { name: /regenerate/i }));

    expect(mocks.getTestGeneration).toHaveBeenLastCalledWith('acme', 'webapp', {
      provider: 'github',
      refresh: true,
    });
  });

  it('switches repository when another option is selected', async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <RepositoryTestGenerationPanel options={OPTIONS} provider="github" />,
      { route: '/test-generator' },
    );

    await screen.findByText('Framework');
    await user.selectOptions(screen.getByLabelText(/repository/i), 'acme/api');

    expect(mocks.getTestGeneration).toHaveBeenLastCalledWith('acme', 'api', {
      provider: 'github',
      refresh: false,
    });
  });

  it('surfaces an error with a retry when generation fails', async () => {
    mocks.getTestGeneration.mockRejectedValue(new Error('Token expired'));
    renderWithProviders(
      <RepositoryTestGenerationPanel options={OPTIONS} provider="github" />,
      { route: '/test-generator' },
    );

    expect(
      await screen.findByText(/Could not propose tests for this repository/),
    ).toBeInTheDocument();
  });

  it('explains an empty result instead of showing a zeroed report', async () => {
    mocks.getTestGeneration.mockResolvedValue(testGeneration({ targets: [] }));
    renderWithProviders(
      <RepositoryTestGenerationPanel options={OPTIONS} provider="github" />,
      { route: '/test-generator' },
    );

    expect(await screen.findByText('No untested symbols found')).toBeInTheDocument();
  });

  it('does not call the API when there is no repository', () => {
    renderWithProviders(<RepositoryTestGenerationPanel options={[]} provider="github" />, {
      route: '/test-generator',
    });

    expect(screen.getByText('No repository to propose tests for')).toBeInTheDocument();
    expect(mocks.getTestGeneration).not.toHaveBeenCalled();
  });
});
