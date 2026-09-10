import { describe, expect, it } from 'vitest';
import { AxiosError, AxiosHeaders } from 'axios';

import { normalizeApiError } from '../api/client';

function makeAxiosError(status: number, detail?: unknown): AxiosError {
  return new AxiosError(
    'Request failed',
    status >= 500 ? 'ERR_BAD_RESPONSE' : undefined,
    undefined,
    undefined,
    {
      status,
      statusText: 'Error',
      data: detail !== undefined ? { detail } : {},
      headers: new AxiosHeaders(),
      config: {} as never,
    },
  );
}

describe('normalizeApiError', () => {
  it('returns a session-expired message for 401', () => {
    const error = normalizeApiError(makeAxiosError(401));
    expect(error.status).toBe(401);
    expect(error.message).toMatch(/session has expired/i);
  });

  it('maps specific status codes to friendly messages', () => {
    expect(normalizeApiError(makeAxiosError(403)).message).toMatch(/permission/i);
    expect(normalizeApiError(makeAxiosError(404)).message).toMatch(/not found/i);
    expect(normalizeApiError(makeAxiosError(429)).message).toMatch(/rate limit/i);
    expect(normalizeApiError(makeAxiosError(500)).message).toMatch(/something went wrong/i);
  });

  it('uses the backend detail message when present', () => {
    const error = normalizeApiError(makeAxiosError(422, 'Review is still running'));
    expect(error.message).toBe('Review is still running');
  });

  it('reports a network failure when there is no response', () => {
    const network = new AxiosError('Network Error');
    const error = normalizeApiError(network);
    expect(error.message).toMatch(/cannot reach the smartsdlc backend/i);
  });

  it('falls back for unexpected values', () => {
    expect(normalizeApiError({}).message).toMatch(/please try again/i);
  });
});