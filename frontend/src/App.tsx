import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { MotionConfig } from 'framer-motion';

import { AuthProvider } from './auth/AuthContext';
import { SmoothScroll } from './components/SmoothScroll';
import { CursorSpotlight } from './components/ui/CursorSpotlight';
import { ProtectedRoute } from './auth/ProtectedRoute';
import { Layout } from './components/Layout/Layout';
import { DashboardPage } from './pages/DashboardPage';
import { DocumentsPage } from './pages/DocumentsPage';
import { FeedbackPage } from './pages/FeedbackPage';
import { HistoryPage } from './pages/HistoryPage';
import { InsightsPage } from './pages/InsightsPage';
import { LoginCallbackPage } from './pages/LoginCallbackPage';
import { LoginPage } from './pages/LoginPage';
import { NotFoundPage } from './pages/NotFoundPage';
import { PullRequestDetailPage } from './pages/PullRequestDetailPage';
import { PullRequestsPage } from './pages/PullRequestsPage';
import { RepoPage } from './pages/RepoPage';
import { RepositoriesPage } from './pages/RepositoriesPage';
import { ReviewPage } from './pages/ReviewPage';
import { SettingsPage } from './pages/SettingsPage';
import { WorkflowDetailPage } from './pages/WorkflowDetailPage';
import { WorkflowsPage } from './pages/WorkflowsPage';

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <MotionConfig reducedMotion="user">
          <CursorSpotlight />
          <SmoothScroll />
          <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/login/callback" element={<LoginCallbackPage />} />

          <Route element={<ProtectedRoute />}>
            <Route element={<Layout />}>
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/repositories" element={<RepositoriesPage />} />
              <Route path="/repositories/:owner/:repo" element={<RepoPage />} />
              <Route path="/pull-requests" element={<PullRequestsPage />} />
              <Route
                path="/pull-requests/:owner/:repo/:number"
                element={<PullRequestDetailPage />}
              />
              <Route path="/reviews/:owner/:repo/:number" element={<ReviewPage />} />
              <Route path="/history" element={<HistoryPage />} />
              <Route path="/documents" element={<DocumentsPage />} />
              <Route path="/insights" element={<InsightsPage />} />
              <Route path="/feedback" element={<FeedbackPage />} />
              <Route path="/workflows" element={<WorkflowsPage />} />
              <Route path="/workflows/:workflowId" element={<WorkflowDetailPage />} />
              <Route path="/settings" element={<SettingsPage />} />
            </Route>
          </Route>

          <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </MotionConfig>
      </BrowserRouter>
    </AuthProvider>
  );
}