import { Link } from 'react-router-dom';

import { Ambient } from '../components/Layout/Ambient';

export function NotFoundPage() {
  return (
    <div className="relative min-h-screen overflow-hidden">
      <Ambient />

      <div className="relative z-10 flex min-h-screen items-center justify-center px-5 py-12">
        <div className="w-full max-w-md text-center">
          <h1 className="font-mono text-[76px] font-semibold leading-none tracking-tight text-ink-faint">
            404
          </h1>

          <div className="glass mt-6 px-6 py-7">
            <p className="text-[19px] font-semibold tracking-tight text-ink">Page not found</p>
            <p className="mt-2 text-[13.5px] leading-relaxed text-ink-subtle">
              The page you requested does not exist or may have been moved.
            </p>

            <Link to="/dashboard" className="btn btn-primary mt-6 w-full justify-center">
              Back to dashboard
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
