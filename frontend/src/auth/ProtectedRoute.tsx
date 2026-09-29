import { Navigate, Outlet, useLocation } from 'react-router-dom';

import { useAuth } from './AuthContext';
import { Ambient } from '../components/Layout/Ambient';
import { LoadingState } from '../components/LoadingState';

export function ProtectedRoute() {
  const { token, initialized } = useAuth();
  const location = useLocation();

  if (!initialized) {
    return (
      <div className="relative flex min-h-screen items-center justify-center bg-surface-0 text-ink">
        <Ambient />
        <div className="relative z-10">
          <LoadingState label="Checking your session…" />
        </div>
      </div>
    );
  }

  if (!token) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return <Outlet />;
}
