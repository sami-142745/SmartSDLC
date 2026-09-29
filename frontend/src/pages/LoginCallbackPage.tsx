import { useEffect, useRef, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';

import { exchangeCode } from '../api/auth';
import { useAuth } from '../auth/AuthContext';
import { Ambient } from '../components/Layout/Ambient';
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

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-surface-0 px-4 py-12 text-ink-muted">
      <Ambient />

      <div className="relative z-10 w-full max-w-md">
        <p className="eyebrow mb-3 text-center">Confirming sign-in</p>

        {error ? (
          <div className="glass p-7 sm:p-8">
            <ErrorState title="Sign-in failed" message={error}>
              <div className="mt-4">
                <Link to="/login" className="btn btn-primary">
                  Back to sign in
                </Link>
              </div>
            </ErrorState>
          </div>
        ) : (
          <div className="glass p-8">
            <LoadingState label="Confirming your GitHub sign-in…" />
          </div>
        )}
      </div>
    </div>
  );
}
