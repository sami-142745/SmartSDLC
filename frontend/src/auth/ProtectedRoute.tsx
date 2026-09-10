import { Navigate, Outlet, useLocation } from 'react-router-dom';

import { useAuth } from './AuthContext';
import { LoadingState } from '../components/LoadingState';

/**
 * Guards protected routes. While authentication state is being restored on
 * startup a spinner is shown; unauthenticated users are redirected to /login.
 */
export function ProtectedRoute() {
  const { token, initialized } = useAuth();
  const location = useLocation();

  if (!initialized) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <LoadingState label="Checking your session…" />
      </div>
    );
  }

  if (!token) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return <Outlet />;
}