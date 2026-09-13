import { useEffect, useRef, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';

import { exchangeCode } from '../api/auth';
import { useAuth } from '../auth/AuthContext';
import { AppBackground } from '../components/Background';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import { LoginVisual } from '../components/LoginVisual';

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
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-surface-0 px-4 py-12 text-slate-200">
      <AppBackground />
      <LoginVisual />
      <div className="relative z-10 w-full max-w-md">
        <p className="tech-label mb-3 text-center text-accent-indigo/70">SMARTSDLC SECURITY GATEWAY</p>
        {error ? (
          <div className="corner-ticks border border-white/[0.08] bg-[#0c0d16]/80 p-7 backdrop-blur-2xl sm:p-8">
            <span aria-hidden className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-rose-400/50 to-transparent" />
            <ErrorState title="Sign-in failed" message={error}>
              <div className="mt-4">
                <Link to="/login" className="btn-primary">
                  Back to sign in
                </Link>
              </div>
            </ErrorState>
          </div>
        ) : (
          <div className="corner-ticks border border-white/[0.08] bg-[#0c0d16]/80 p-8 backdrop-blur-2xl">
            <span aria-hidden className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-accent-indigo/50 to-transparent" />
            <LoadingState label="Confirming your GitHub sign-in\u2026" />
          </div>
        )}
      </div>
    </div>
  );
}
