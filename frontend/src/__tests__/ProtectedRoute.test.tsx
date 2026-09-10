import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { render, screen } from '@testing-library/react';

const authMocks = vi.hoisted(() => ({
  validateToken: vi.fn(),
  userFromToken: vi.fn(),
}));

vi.mock('../api/auth', () => ({
  ...authMocks,
  exchangeCode: vi.fn(),
  getLoginUrl: vi.fn(),
}));

import { AuthProvider } from '../auth/AuthContext';
import { ProtectedRoute } from '../auth/ProtectedRoute';

function renderProtected({ route = '/dashboard' } = {}) {
  return render(
    <AuthProvider>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route element={<ProtectedRoute />}>
            <Route path="/dashboard" element={<div>Protected dashboard</div>} />
          </Route>
          <Route path="/login" element={<div>Login page</div>} />
        </Routes>
      </MemoryRouter>
    </AuthProvider>,
  );
}

afterEach(() => {
  window.localStorage.clear();
});

describe('ProtectedRoute', () => {
  it('redirects to /login when there is no session', async () => {
    renderProtected();

    expect(await screen.findByText('Login page')).toBeInTheDocument();
    expect(screen.queryByText('Protected dashboard')).not.toBeInTheDocument();
  });

  it('shows a loading state while the session is being restored', async () => {
    authMocks.validateToken.mockReturnValue(new Promise(() => {}));
    window.localStorage.setItem('smartsdlc_token', 'jwt.pending');

    renderProtected();

    expect(await screen.findByText(/checking your session/i)).toBeInTheDocument();
  });

  it('redirects to login when the stored session is invalid', async () => {
    authMocks.validateToken.mockResolvedValue(false);
    window.localStorage.setItem('smartsdlc_token', 'jwt.expired');

    renderProtected();

    expect(await screen.findByText('Login page')).toBeInTheDocument();
    expect(window.localStorage.getItem('smartsdlc_token')).toBeNull();
  });
});