import { Navigate, Outlet, useLocation } from 'react-router-dom';

import { useAuth } from './AuthContext';
import { AppBackground } from '../components/Background';
import { LoadingState } from '../components/LoadingState';

export function ProtectedRoute() {
  const { token, initialized } = useAuth();
  const location = useLocation();

  if (!initialized) {
    return (
      <div className="relative flex min-h-screen items-center justify-center bg-surface-0 text-slate-200">
        <AppBackground />
        <div className="relative z-10">
          <LoadingState label="Checking your session\u2026" />
        </div>
      </div>
    );
  }

  if (!token) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return <Outlet />;
}
