import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const mocks = vi.hoisted(() => ({
  getArchitecture: vi.fn(),
}));

vi.mock('../api/architecture', () => ({
  getArchitecture: mocks.getArchitecture,
}));

import { RepositoryArchitecturePanel } from '../components/architecture/RepositoryArchitecturePanel';
import { architectureGraph, architectureIssue } from '../test/fixtures';
import { renderWithProviders } from '../test/utils';

const OPTIONS = [
  { owner: 'acme', repository: 'webapp' },
  { owner: 'acme', repository: 'api' },
];

beforeEach(() => {
  mocks.getArchitecture.mockReset().mockResolvedValue(architectureGraph());
});

describe('RepositoryArchitecturePanel', () => {
  it('renders module, dependency and signal counts for the selected repository', async () => {
    renderWithProviders(
      <RepositoryArchitecturePanel options={OPTIONS} provider="github" />,
      { route: '/architecture', authToken: undefined },
    );

    expect(await screen.findByText('Dependency graph')).toBeInTheDocument();
    expect(screen.getByText('Third-party packages')).toBeInTheDocument();
    // Three modules in the fixture, shown as a stat and in the module list.
    expect(screen.getAllByText('Modules').length).toBeGreaterThan(0);
    expect(mocks.getArchitecture).toHaveBeenCalledWith('acme', 'webapp', {
      provider: 'github',
      refresh: false,
    });
  });

  it('shows the selected module with the evidence for its classification', async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <RepositoryArchitecturePanel options={OPTIONS} provider="github" />,
      { route: '/architecture' },
    );

    await screen.findByText('Dependency graph');
    const graphButton = screen.getByRole('application');
    graphButton.focus();
    await user.keyboard('{ArrowRight}');

    expect(await screen.findByText('app.services.auth')).toBeInTheDocument();
    expect(screen.getByText(/defines a service module under the services package/i)).toBeInTheDocument();
  });

  it('states partial coverage instead of presenting a truncated graph as complete', async () => {
    mocks.getArchitecture.mockResolvedValue(
      architectureGraph({
        truncated: true,
        summary: { ...architectureGraph().summary, unresolved_imports: 4 },
        errors: ['app/legacy.py: could not be decoded'],
      }),
    );

    renderWithProviders(
      <RepositoryArchitecturePanel options={OPTIONS} provider="github" />,
      { route: '/architecture' },
    );

    expect(await screen.findByText(/partial analysis/i)).toBeInTheDocument();
    expect(screen.getByText(/4 imports could not be resolved/i)).toBeInTheDocument();
    expect(screen.getByText(/could not be read/i)).toBeInTheDocument();
  });

  it('filters the module list as the reviewer types', async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <RepositoryArchitecturePanel options={OPTIONS} provider="github" />,
      { route: '/architecture' },
    );

    await screen.findByText('Dependency graph');
    expect(screen.getByText('app.db.session')).toBeInTheDocument();

    await user.type(screen.getByLabelText(/search modules/i), 'routers');

    expect(screen.queryByText('app.db.session')).not.toBeInTheDocument();
    expect(screen.getByText('app.routers.auth')).toBeInTheDocument();
  });

  it('re-analyses when the reviewer asks for a refresh', async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <RepositoryArchitecturePanel options={OPTIONS} provider="github" />,
      { route: '/architecture' },
    );

    await screen.findByText('Dependency graph');
    await user.click(screen.getByRole('button', { name: /re-analyse/i }));

    await waitFor(() =>
      expect(mocks.getArchitecture).toHaveBeenLastCalledWith('acme', 'webapp', {
        provider: 'github',
        refresh: true,
      }),
    );
  });

  it('surfaces structural signals with the modules they affect', async () => {
    const user = userEvent.setup();
    mocks.getArchitecture.mockResolvedValue(
      architectureGraph({ issues: [architectureIssue()], summary: { ...architectureGraph().summary, cycles: 1, cycle_groups: 1 } }),
    );

    renderWithProviders(
      <RepositoryArchitecturePanel options={OPTIONS} provider="github" />,
      { route: '/architecture' },
    );

    await screen.findByText('Dependency graph');
    expect(screen.getByText('Circular dependency')).toBeInTheDocument();
    expect(screen.getByText(/form an import cycle/i)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'app.services.users' }));
    expect(await screen.findByText('app.services.users')).toBeInTheDocument();
  });

  it('shows an error state when the analysis request fails', async () => {
    mocks.getArchitecture.mockRejectedValue(new Error('Token expired'));

    renderWithProviders(
      <RepositoryArchitecturePanel options={OPTIONS} provider="github" />,
      { route: '/architecture' },
    );

    expect(await screen.findByRole('alert')).toHaveTextContent(/could not analyse this repository/i);
    expect(screen.getByText('Token expired')).toBeInTheDocument();
  });

  it('asks for a repository when none are available', () => {
    renderWithProviders(
      <RepositoryArchitecturePanel options={[]} provider="github" />,
      { route: '/architecture' },
    );

    expect(screen.getByText('No repository to analyse')).toBeInTheDocument();
    expect(mocks.getArchitecture).not.toHaveBeenCalled();
  });

  it('explains an empty repository rather than showing an empty graph', async () => {
    mocks.getArchitecture.mockResolvedValue(
      architectureGraph({
        modules: [],
        nodes: [],
        edges: [],
        summary: {
          ...architectureGraph().summary,
          total_modules: 0,
          kind_distribution: {},
          language_distribution: {},
        },
      }),
    );

    renderWithProviders(
      <RepositoryArchitecturePanel options={OPTIONS} provider="github" />,
      { route: '/architecture' },
    );

    expect(await screen.findByText('No analysable modules')).toBeInTheDocument();
  });
});
