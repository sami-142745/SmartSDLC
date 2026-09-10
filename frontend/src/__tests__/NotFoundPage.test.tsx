import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';

import { NotFoundPage } from '../pages/NotFoundPage';
import { renderWithProviders } from '../test/utils';

describe('NotFoundPage', () => {
  it('renders a 404 message with a link back to the dashboard', () => {
    renderWithProviders(<NotFoundPage />, { route: '/nope' });

    expect(screen.getByRole('heading', { name: '404' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /back to dashboard/i })).toHaveAttribute(
      'href',
      '/dashboard',
    );
  });
});