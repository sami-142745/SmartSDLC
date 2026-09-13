import { describe, expect, it, vi } from 'vitest';
import { fireEvent, screen } from '@testing-library/react';
import { Route, Routes } from 'react-router-dom';

const workflowsMocks = vi.hoisted(() => ({
  getWorkflow: vi.fn(),
}));

vi.mock('../api/workflows', () => ({
  getWorkflows: vi.fn(),
  ...workflowsMocks,
}));

vi.mock('../api/auth', () => ({
  exchangeCode: vi.fn(),
  getLoginUrl: vi.fn(),
  validateToken: vi.fn(),
  userFromToken: vi.fn(() => null),
}));

import { WorkflowDetailPage } from '../pages/WorkflowDetailPage';
import { renderWithProviders } from '../test/utils';
import { TEST_TOKEN, failedWorkflow, workflow } from '../test/fixtures';

describe('WorkflowDetailPage', () => {
  it('renders stage pipeline, timeline, and metadata', async () => {
    workflowsMocks.getWorkflow.mockResolvedValue(workflow);

    renderWithProviders(
      <Routes>
        <Route path="/workflows/:workflowId" element={<WorkflowDetailPage />} />
        <Route path="/workflows" element={<div>Workflows list placeholder</div>} />
      </Routes>,
      { route: '/workflows/wf_123abc', authToken: TEST_TOKEN },
    );

    expect(await screen.findByText(/acme\/webapp/i)).toBeInTheDocument();
    expect(screen.getByText('completed')).toBeInTheDocument();
    expect(screen.getByText('Stage pipeline', { exact: false })).toBeInTheDocument();
    expect(screen.getAllByText('ANALYZING').length).toBeGreaterThan(0);
    expect(screen.getAllByText('RECEIVED').length).toBeGreaterThan(0);
    expect(screen.getByText(/manual · github/i)).toBeInTheDocument();
    expect(screen.getByText('wf_123abc')).toBeInTheDocument();
    expect(screen.getByText('review_xyz')).toBeInTheDocument();
    expect(screen.getByText('2.4 s')).toBeInTheDocument();
  });

  it('links back to the workflow list', async () => {
    workflowsMocks.getWorkflow.mockResolvedValue(workflow);

    renderWithProviders(
      <Routes>
        <Route path="/workflows/:workflowId" element={<WorkflowDetailPage />} />
        <Route path="/workflows" element={<div>Workflows list placeholder</div>} />
      </Routes>,
      { route: '/workflows/wf_123abc', authToken: TEST_TOKEN },
    );

    fireEvent.click(await screen.findByText(/back to workflow runs/i));
    expect(await screen.findByText('Workflows list placeholder')).toBeInTheDocument();
  });

  it('surfaces workflow error for failed runs', async () => {
    workflowsMocks.getWorkflow.mockResolvedValue(failedWorkflow);

    renderWithProviders(
      <Routes>
        <Route path="/workflows/:workflowId" element={<WorkflowDetailPage />} />
      </Routes>,
      { route: '/workflows/wf_fail', authToken: TEST_TOKEN },
    );

    expect(await screen.findByText('failed')).toBeInTheDocument();
    expect(screen.getByText('Not Found')).toBeInTheDocument();
  });

  it('shows error state when the run cannot be loaded', async () => {
    workflowsMocks.getWorkflow.mockRejectedValue(new Error('boom'));

    renderWithProviders(
      <Routes>
        <Route path="/workflows/:workflowId" element={<WorkflowDetailPage />} />
      </Routes>,
      { route: '/workflows/wf_nope', authToken: TEST_TOKEN },
    );

    expect(await screen.findByText(/could not load this workflow/i)).toBeInTheDocument();
  });
});