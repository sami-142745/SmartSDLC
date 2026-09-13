import { describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, within } from '@testing-library/react';
import { Route, Routes } from 'react-router-dom';

const workflowsMocks = vi.hoisted(() => ({
  getWorkflows: vi.fn(),
  getWorkflow: vi.fn(),
}));

vi.mock('../api/workflows', () => ({
  ...workflowsMocks,
}));

vi.mock('../api/auth', () => ({
  exchangeCode: vi.fn(),
  getLoginUrl: vi.fn(),
  validateToken: vi.fn(),
  userFromToken: vi.fn(() => null),
}));

import { WorkflowsPage } from '../pages/WorkflowsPage';
import { renderWithProviders } from '../test/utils';
import { TEST_TOKEN, emptyWorkflowsResponse, workflowsResponse } from '../test/fixtures';

describe('WorkflowsPage', () => {
  it('shows pipeline stats and workflow rows', async () => {
    workflowsMocks.getWorkflows.mockResolvedValue(workflowsResponse);

    renderWithProviders(
      <Routes>
        <Route path="/workflows" element={<WorkflowsPage />} />
        <Route path="/workflows/:workflowId" element={<div>Workflow detail placeholder</div>} />
      </Routes>,
      { route: '/workflows', authToken: TEST_TOKEN },
    );

    expect(await screen.findAllByText(/acme\/webapp/i)).toHaveLength(2);
    expect(screen.getAllByText(/manual · github/i)).toHaveLength(2);
    const table = await screen.findByRole('table');
    expect(within(table).getByText('completed')).toBeInTheDocument();
    expect(within(table).getByText('failed')).toBeInTheDocument();
    expect(within(table).getByText('2.4 s')).toBeInTheDocument();
    expect(screen.getByText('Total runs')).toBeInTheDocument();
  });

  it('navigates to the detail page on row click', async () => {
    workflowsMocks.getWorkflows.mockResolvedValue(workflowsResponse);

    renderWithProviders(
      <Routes>
        <Route path="/workflows" element={<WorkflowsPage />} />
        <Route path="/workflows/:workflowId" element={<div>Workflow detail placeholder</div>} />
      </Routes>,
      { route: '/workflows', authToken: TEST_TOKEN },
    );

    const row = (await screen.findAllByText(/acme\/webapp/i))[0];
    fireEvent.click(row);
    expect(await screen.findByText('Workflow detail placeholder')).toBeInTheDocument();
  });

  it('shows the explicit empty state when no runs exist', async () => {
    workflowsMocks.getWorkflows.mockResolvedValue(emptyWorkflowsResponse);

    renderWithProviders(
      <Routes>
        <Route path="/workflows" element={<WorkflowsPage />} />
      </Routes>,
      { route: '/workflows', authToken: TEST_TOKEN },
    );

    expect(await screen.findByText(/no workflows recorded yet/i)).toBeInTheDocument();
  });
});