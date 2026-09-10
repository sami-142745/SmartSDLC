import { describe, expect, it, vi } from 'vitest';
import { Route, Routes } from 'react-router-dom';

vi.mock('../api/auth', () => ({
  exchangeCode: vi.fn(),
  getLoginUrl: vi.fn(() => 'http://localhost:8000/auth/github/login'),
  validateToken: vi.fn(),
  userFromToken: vi.fn(() => null),
}));

import { render, screen } from '@testing-library/react';
import { LoginPage } from '../pages/LoginPage';
import { renderWithProviders, TEST_USER } from '../test/utils';
import { TEST_TOKEN } from '../test/fixtures';

describe('LoginPage', () => {
  it('shows a sign-in link to the GitHub OAuth endpoint', () => {
    renderWithProviders(<LoginPage />, { route: '/login' });

    expect(screen.getByRole('link', { name: /continue with github/i })).toHaveAttribute(
      'href',
      'http://localhost:8000/auth/github/login',
    );
  });

  it('redirects to the dashboard when already authenticated', async () => {
    renderWithProviders(
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/dashboard" element={<div>Dashboard placeholder</div>} />
      </Routes>,
      { route: '/login', authToken: TEST_TOKEN, authUser: TEST_USER },
    );

    expect(await screen.findByText('Dashboard placeholder')).toBeInTheDocument();
  });
});