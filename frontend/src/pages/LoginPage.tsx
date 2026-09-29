import { Navigate } from 'react-router-dom';

import { getLoginUrl } from '../api/auth';
import { useAuth } from '../auth/AuthContext';
import { Logo } from '../components/Layout/Logo';
import { Ambient } from '../components/Layout/Ambient';

export function LoginPage() {
  const { token, initialized } = useAuth();
  const loginUrl = getLoginUrl();

  if (!initialized) return null;

  // Keyed on the token, not the user object, so a session whose profile could
  // not be decoded still lands on the dashboard instead of the login loop.
  if (token) {
    return <Navigate to="/dashboard" replace />;
  }

  return (
    <div className="relative min-h-screen overflow-hidden">
      <Ambient />

      <div className="relative z-10 flex min-h-screen flex-col items-center justify-center px-5 py-12">
        <div className="w-full max-w-sm">
          <div className="flex flex-col items-center text-center">
            <Logo className="h-9 w-9" />
            <h1 className="mt-5 text-[26px] font-semibold tracking-tight text-ink">SmartSDLC</h1>
            <p className="mt-2 max-w-xs text-[13.5px] leading-relaxed text-ink-subtle">
              AI-assisted code review, documentation and security intelligence for your pull requests.
            </p>
          </div>

          <div className="glass mt-8 p-6">
            <a
              href={loginUrl}
              className="btn btn-primary w-full justify-center gap-2.5"
            >
              <svg
                viewBox="0 0 24 24"
                fill="currentColor"
                className="h-4 w-4"
                aria-hidden="true"
              >
                <path d="M12 .3a12 12 0 0 0-3.8 23.4c.6.1.8-.3.8-.6v-2c-3.3.7-4-1.6-4-1.6-.6-1.4-1.4-1.8-1.4-1.8-1-.7 0-.7 0-.7 1.2.1 1.8 1.2 1.8 1.2 1 1.8 2.8 1.3 3.5 1 .1-.8.4-1.3.7-1.6-2.7-.3-5.5-1.3-5.5-5.9 0-1.3.5-2.4 1.2-3.2-.1-.3-.5-1.5.1-3.2 0 0 1-.3 3.3 1.2a11.5 11.5 0 0 1 6 0c2.3-1.5 3.3-1.2 3.3-1.2.6 1.7.2 2.9.1 3.2.8.8 1.2 1.9 1.2 3.2 0 4.6-2.8 5.6-5.5 5.9.4.4.8 1.1.8 2.2v3.3c0 .3.2.7.8.6A12 12 0 0 0 12 .3Z" />
              </svg>
              Continue with GitHub
            </a>

            <p className="mt-4 text-center text-[11.5px] leading-relaxed text-ink-faint">
              You will be redirected to GitHub to authorise access. SmartSDLC never sees your
              GitHub credentials.
            </p>
          </div>

          <ul className="mt-6 grid grid-cols-3 gap-2">
            {[
              { label: 'Code review', detail: 'Findings by severity' },
              { label: 'Security', detail: 'Weighted posture' },
              { label: 'Insights', detail: 'Trend and risk' },
            ].map((item) => (
              <li key={item.label} className="glass-subtle px-3 py-2.5 text-center">
                <p className="text-[11.5px] font-medium text-ink-muted">{item.label}</p>
                <p className="mt-0.5 text-[10.5px] text-ink-faint">{item.detail}</p>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
