import { useEffect, useRef, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';

import { exchangeCode } from '../api/auth';
import { useAuth } from '../auth/AuthContext';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';

export function LoginCallbackPage() {
  const { setSession } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const running = useRef(false);

  useEffect(() => {
    if (running.current) return;
    running.current = true;

    const params = new URLSearchParams(location.search);
    const code = params.get('code');
    const state = params.get('state');
    const from = (location.state as { from?: string } | null)?.from;

    if (!code || !state) {
      setError('GitHub did not return an authorization code. Please sign in again.');
      return;
    }

    exchangeCode(code, state)
      .then((response) => {
        setSession(response.access_token, response.user);
        navigate(from ?? '/dashboard', { replace: true });
      })
      .catch((err) => {
        setError((err as { message?: string }).message ?? 'Sign-in failed. Please try again.');
      });
  }, [location, setSession, navigate]);

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-900 px-4">
        <div className="w-full max-w-md">
          <ErrorState title="Sign-in failed" message={error}>
            <div className="mt-4">
              <Link
                to="/login"
                className="inline-flex items-center rounded-md bg-slate-100 px-4 py-2 text-sm font-semibold text-slate-900 hover:bg-white"
              >
                Back to sign in
              </Link>
            </div>
          </ErrorState>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-900 px-4">
      <LoadingState label="Confirming your GitHub sign-in…" />
    </div>
  );
}