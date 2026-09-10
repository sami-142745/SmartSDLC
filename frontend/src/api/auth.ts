import { API_BASE_URL, http } from './client';
import type { AuthResponse, UserSummary } from '../types';

/**
 * Exchange a GitHub OAuth authorization code (received on /login/callback) for
 * a SmartSDLC JWT + user profile. No GitHub token ever leaves the backend.
 */
export async function exchangeCode(code: string, state: string): Promise<AuthResponse> {
  const { data } = await http.get<AuthResponse>('/auth/github/callback', {
    params: { code, state },
  });
  return data;
}

/** Backend endpoint that kicks off the GitHub OAuth redirect flow. */
export function getLoginUrl(): string {
  return `${API_BASE_URL}/auth/github/login`;
}

/**
 * Best-effort token validation against the backend. A 401 means the session is
 * invalid; any other failure (e.g. backend temporarily unreachable) keeps the
 * existing session so the app can surface error states per-page.
 */
export async function validateToken(): Promise<boolean> {
  try {
    await http.get('/dashboard');
    return true;
  } catch (error) {
    const status = (error as { status?: number }).status;
    if (status === 401) {
      return false;
    }
    return true;
  }
}

export function userFromToken(token: string): UserSummary | null {
  try {
    const payload = token.split('.')[1];
    if (!payload) return null;
    const normalized = payload.replace(/-/g, '+').replace(/_/g, '/');
    const decoded = JSON.parse(atob(normalized)) as { sub?: string; login?: string };
    if (!decoded.sub) return null;
    return {
      github_id: Number(decoded.sub),
      login: decoded.login ?? 'github-user',
      name: null,
      email: null,
      avatar_url: null,
    };
  } catch {
    return null;
  }
}