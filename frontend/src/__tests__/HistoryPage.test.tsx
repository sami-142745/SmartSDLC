import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { Route, Routes } from 'react-router-dom';

const mocks = vi.hoisted(() => ({
  getHistory: vi.fn(),
}));

vi.mock('../api/dashboard', () => mocks);

vi.mock('../api/auth', () => ({
  exchangeCode: vi.fn(),
  getLoginUrl: vi.fn(),
  validateToken: vi.fn(),
  userFromToken: vi.fn(() => null),
}));

import { HistoryPage } from '../pages/HistoryPage';
import { history } from '../test/fixtures';
import { renderWithProviders } from '../test/utils';
import { TEST_TOKEN } from '../test/fixtures';

const secondPage = {
  ...history,
  items: history.items.map((item) => ({ ...item, pull_request_number: 200, pull_request_title: 'Seventh review' })),
  page: 2,
  total_pages: 2,
};

beforeEach(() => {
  mocks.getHistory.mockReset();
});

describe('HistoryPage', () => {
  it('lists review history and navigates to a review on click', async () => {
    mocks.getHistory.mockResolvedValue(history);

    renderWithProviders(
      <Routes>
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/reviews/:owner/:repo/:number" element={<div>Review page placeholder</div>} />
      </Routes>,
      { route: '/history', authToken: TEST_TOKEN },
    );

    expect(await screen.findByText(/Add auth flow/i)).toBeInTheDocument();
    expect(screen.getByText(/1–1 of 1/)).toBeInTheDocument();

    fireEvent.click(screen.getByText(/Add auth flow/i));
    expect(await screen.findByText('Review page placeholder')).toBeInTheDocument();
  });

  it('paginates through history', async () => {
    mocks.getHistory
      .mockResolvedValueOnce({ ...history, total: 25, total_pages: 2 })
      .mockResolvedValueOnce(secondPage);

    renderWithProviders(<HistoryPage />, { route: '/history', authToken: TEST_TOKEN });

    expect(await screen.findByText(/Add auth flow/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /next/i }));

    await waitFor(() => expect(mocks.getHistory).toHaveBeenCalledTimes(2));
    expect(await screen.findByText(/Seventh review/i)).toBeInTheDocument();
    expect(screen.getByText(/acme\/webapp #200/i)).toBeInTheDocument();
  });

  it('applies repository and status filters', async () => {
    mocks.getHistory.mockResolvedValue(history);

    renderWithProviders(<HistoryPage />, { route: '/history', authToken: TEST_TOKEN });

    fireEvent.change(screen.getByPlaceholderText('owner/name'), {
      target: { value: 'acme/webapp' },
    });
    fireEvent.change(screen.getByDisplayValue('All'), { target: { value: 'complete' } });
    fireEvent.click(screen.getByRole('button', { name: /apply filters/i }));

    await waitFor(() =>
      expect(mocks.getHistory).toHaveBeenLastCalledWith({
        page: 1,
        perPage: 20,
        repository: 'acme/webapp',
        status: 'complete',
      }),
    );
  });
});