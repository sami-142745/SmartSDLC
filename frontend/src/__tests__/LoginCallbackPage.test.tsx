import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Route, Routes } from 'react-router-dom';
import { fireEvent, screen } from '@testing-library/react';

const authMocks = vi.hoisted(() => ({
  exchangeCode: vi.fn(),
  validateToken: vi.fn(async () => true),
}));

vi.mock('../api/auth', () => ({
  ...authMocks,
  getLoginUrl: vi.fn(),
  userFromToken: vi.fn(() => null),
}));

import { LoginCallbackPage } from '../pages/LoginCallbackPage';
import { renderWithProviders } from '../test/utils';
import { TEST_TOKEN } from '../test/fixtures';
import type { UserSummary } from '../types';

beforeEach(() => {
  window.localStorage.clear();
  authMocks.exchangeCode.mockReset();
});

afterEach(() => {
  window.localStorage.clear();
});

const callbackUser: UserSummary = {
  github_id: 42,
  login: 'octocat',
  name: 'Octo Cat',
  email: null,
  avatar_url: null,
};

describe('LoginCallbackPage', () => {
  it('exchanges the code and navigates to the dashboard on success', async () => {
    authMocks.exchangeCode.mockResolvedValue({
      access_token: TEST_TOKEN,
      user: callbackUser,
    });

    renderWithProviders(
      <Routes>
        <Route path="/login/callback" element={<LoginCallbackPage />} />
        <Route path="/dashboard" element={<div>Dashboard placeholder</div>} />
      </Routes>,
      { route: '/login/callback?code=abc123&state=xyz' },
    );

    expect(await screen.findByText('Dashboard placeholder')).toBeInTheDocument();
    expect(authMocks.exchangeCode).toHaveBeenCalledWith('abc123', 'xyz');
  });

  it('shows an error when the exchange fails', async () => {
    authMocks.exchangeCode.mockRejectedValue(new Error('Invalid code'));

    renderWithProviders(<LoginCallbackPage />, {
      route: '/login/callback?code=bad&state=xyz',
    });

    expect(await screen.findByRole('alert')).toHaveTextContent(/sign-in failed/i);
    fireEvent.click(screen.getByRole('link', { name: /back to sign in/i }));
  });

  it('shows an error when code or state is missing', async () => {
    renderWithProviders(<LoginCallbackPage />, { route: '/login/callback' });

    expect(await screen.findByRole('alert')).toHaveTextContent(
      /did not return an authorization code/i,
    );
    expect(authMocks.exchangeCode).not.toHaveBeenCalled();
  });
});