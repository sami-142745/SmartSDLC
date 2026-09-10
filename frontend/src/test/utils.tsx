import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { ReactNode } from 'react';

import { AuthProvider } from '../auth/AuthContext';
import type { UserSummary } from '../types';

interface RenderOptions {
  route?: string;
  authToken?: string;
  authUser?: UserSummary;
}

export function renderWithProviders(ui: ReactNode, options: RenderOptions = {}) {
  const { route = '/', authToken, authUser } = options;
  return render(
    <AuthProvider initialToken={authToken} initialUser={authUser}>
      <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
    </AuthProvider>,
  );
}

export const TEST_USER: UserSummary = {
  github_id: 42,
  login: 'octocat',
  name: 'Octo Cat',
  email: 'octocat@example.com',
  avatar_url: null,
};