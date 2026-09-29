import { render } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
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

/**
 * Renders a page behind a matching `<Route>` so `useParams` resolves.
 *
 * `renderWithProviders` alone is not enough for parametrised pages: without a
 * matching route element, `useParams` returns an empty object and the page sees
 * blank parameters regardless of the initial entry.
 */
export function renderRoute(
  path: string,
  element: ReactNode,
  options: RenderOptions = {},
) {
  return renderWithProviders(
    <Routes>
      <Route path={path} element={element} />
    </Routes>,
    options,
  );
}

export const TEST_USER: UserSummary = {
  github_id: 42,
  login: 'octocat',
  name: 'Octo Cat',
  email: 'octocat@example.com',
  avatar_url: null,
};