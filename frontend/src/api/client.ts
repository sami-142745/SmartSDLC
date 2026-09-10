import axios, { AxiosError } from 'axios';

export const API_BASE_URL = (
  (import.meta.env.VITE_API_BASE_URL as string | undefined) || 'http://localhost:8000'
).replace(/\/+$/, '');

/**
 * The JWT is the only credential stored in the browser. GitHub OAuth access
 * tokens, client secrets, and API keys never reach the frontend.
 */
const TOKEN_KEY = 'smartsdlc_token';

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export interface ApiError {
  status?: number;
  message: string;
}

export function normalizeApiError(error: unknown): ApiError {
  if (axios.isAxiosError(error)) {
    const status = Number(error.response?.status ?? 0);
    const detail = (error.response?.data as { detail?: unknown } | undefined)?.detail;

    if (status === 401) {
      return { status, message: 'Your session has expired. Please sign in again.' };
    }
    if (status === 403) {
      return { status, message: 'You do not have permission to perform this action.' };
    }
    if (status === 404) {
      return { status, message: 'The requested resource was not found.' };
    }
    if (status === 429) {
      return { status, message: 'Rate limit exceeded. Please wait a moment and try again.' };
    }
    if (status >= 500) {
      return { status, message: 'Sorry, something went wrong on the server. Please try again later.' };
    }
    if ((detail && typeof detail === 'string') || (detail && typeof detail === 'number')) {
      return { status, message: String(detail) };
    }
    if (!error.response) {
      return {
        status: undefined,
        message: 'Cannot reach the SmartSDLC backend. Make sure it is running on port 8000.',
      };
    }
    return { status, message: `Request failed with status ${status}.` };
  }

  const raw = error as { message?: unknown } | undefined;
  if (raw?.message && typeof raw.message === 'string') {
    return { message: raw.message };
  }
  return { message: 'Something went wrong. Please try again.' };
}

/**
 * Central 401 handling: clear the session and send the user back to the login
 * page. Pages that run while already inside the login flow keep control so they
 * can render their own error.
 */
export function handleResponseError(error: AxiosError): Promise<ApiError> {
  const status = Number(error.response?.status ?? 0);
  if (status === 401) {
    clearToken();
    if (typeof window !== 'undefined') {
      const path = window.location.pathname || '';
      if (!path.startsWith('/login')) {
        window.location.href = '/login';
      }
    }
  }
  return Promise.reject(normalizeApiError(error));
}

export const http = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000,
});

http.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.set('Authorization', `Bearer ${token}`);
  }
  return config;
});

http.interceptors.response.use(
  (response) => response,
  (error) => handleResponseError(error),
);