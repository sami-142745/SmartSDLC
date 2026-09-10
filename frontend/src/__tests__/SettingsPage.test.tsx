import { it, vi } from 'vitest';

vi.mock('../api/auth', () => ({
  exchangeCode: vi.fn(),
  getLoginUrl: vi.fn(),
  validateToken: vi.fn(),
  userFromToken: vi.fn(() => null),
}));

import { describe, expect } from 'vitest';
import { screen } from '@testing-library/react';
import { SettingsPage } from '../pages/SettingsPage';
import { renderWithProviders, TEST_USER } from '../test/utils';
import { TEST_TOKEN } from '../test/fixtures';

describe('SettingsPage', () => {
  it('shows the signed-in GitHub account', () => {
    renderWithProviders(<SettingsPage />, {
      route: '/settings',
      authToken: TEST_TOKEN,
      authUser: TEST_USER,
    });

    expect(screen.getByRole('heading', { name: /settings/i })).toBeInTheDocument();
    expect(screen.getByText('Octo Cat')).toBeInTheDocument();
    expect(screen.getByText('@octocat')).toBeInTheDocument();
    expect(screen.getByText('octocat@example.com')).toBeInTheDocument();
  });

  it('explains that OAuth tokens stay on the backend', () => {
    renderWithProviders(<SettingsPage />, {
      route: '/settings',
      authToken: TEST_TOKEN,
      authUser: TEST_USER,
    });

    expect(screen.getByText(/never exposed to this app/i)).toBeInTheDocument();
  });
});