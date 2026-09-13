import { it, vi } from 'vitest';

const webhookMocks = vi.hoisted(() => ({
  getWebhookEvents: vi.fn(),
}));

vi.mock('../api/webhooks', () => ({
  ...webhookMocks,
}));

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
import { TEST_TOKEN, emptyWebhookEvents, webhookEventsResponse } from '../test/fixtures';

describe('SettingsPage', () => {
  beforeEach(() => {
    webhookMocks.getWebhookEvents.mockResolvedValue(emptyWebhookEvents);
  });

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

  it('shows the explicit empty state for webhook deliveries', async () => {
    renderWithProviders(<SettingsPage />, {
      route: '/settings',
      authToken: TEST_TOKEN,
      authUser: TEST_USER,
    });

    expect(await screen.findByText(/No webhook deliveries recorded yet/i)).toBeInTheDocument();
  });

  it('lists recent webhook deliveries', async () => {
    webhookMocks.getWebhookEvents.mockResolvedValue(webhookEventsResponse);

    renderWithProviders(<SettingsPage />, {
      route: '/settings',
      authToken: TEST_TOKEN,
      authUser: TEST_USER,
    });

    expect(await screen.findByText('opened')).toBeInTheDocument();
    expect(screen.getByText(/octocat\/Hello-World/i)).toBeInTheDocument();
    expect(screen.getByText(/#101/i)).toBeInTheDocument();
    expect(screen.getByText(/deliv-abcd1234efgh5678/i)).toBeInTheDocument();
  });
});