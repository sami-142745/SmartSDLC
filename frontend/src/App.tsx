import { lazy, Suspense } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';

import { AuthProvider } from './auth/AuthContext';
import { ProtectedRoute } from './auth/ProtectedRoute';
import { Layout } from './components/Layout/Layout';
import { PageSkeleton } from './components/ui/Skeleton';
import { LoginCallbackPage } from './pages/LoginCallbackPage';
import { LoginPage } from './pages/LoginPage';
import { NotFoundPage } from './pages/NotFoundPage';

/**
 * Every authenticated page is code-split. The login screens stay eager because
 * they are the first paint for an unauthenticated visitor, and the fallback
 * mirrors each page's real shape so hydration does not shift the layout.
 */
const AiReviewPage = lazy(() => import('./pages/AiReviewPage').then((m) => ({ default: m.AiReviewPage })));
const ArchitecturePage = lazy(() => import('./pages/ArchitecturePage').then((m) => ({ default: m.ArchitecturePage })));
const ChatPage = lazy(() => import('./pages/ChatPage').then((m) => ({ default: m.ChatPage })));
const DashboardPage = lazy(() => import('./pages/DashboardPage').then((m) => ({ default: m.DashboardPage })));
const DocumentsPage = lazy(() => import('./pages/DocumentsPage').then((m) => ({ default: m.DocumentsPage })));
const DocumentationCoveragePage = lazy(() =>
  import('./pages/DocumentationCoveragePage').then((m) => ({ default: m.DocumentationCoveragePage })),
);
const FeedbackPage = lazy(() => import('./pages/FeedbackPage').then((m) => ({ default: m.FeedbackPage })));
const HistoryPage = lazy(() => import('./pages/HistoryPage').then((m) => ({ default: m.HistoryPage })));
const InsightsPage = lazy(() => import('./pages/InsightsPage').then((m) => ({ default: m.InsightsPage })));
const PullRequestDetailPage = lazy(() => import('./pages/PullRequestDetailPage').then((m) => ({ default: m.PullRequestDetailPage })));
const PullRequestsPage = lazy(() => import('./pages/PullRequestsPage').then((m) => ({ default: m.PullRequestsPage })));
const RepoPage = lazy(() => import('./pages/RepoPage').then((m) => ({ default: m.RepoPage })));
const RepositoriesPage = lazy(() => import('./pages/RepositoriesPage').then((m) => ({ default: m.RepositoriesPage })));
const ReviewPage = lazy(() => import('./pages/ReviewPage').then((m) => ({ default: m.ReviewPage })));
const SecurityPage = lazy(() => import('./pages/SecurityPage').then((m) => ({ default: m.SecurityPage })));
const SettingsPage = lazy(() => import('./pages/SettingsPage').then((m) => ({ default: m.SettingsPage })));
const TestGeneratorPage = lazy(() => import('./pages/TestGeneratorPage').then((m) => ({ default: m.TestGeneratorPage })));
const SupplyChainPage = lazy(() => import('./pages/SupplyChainPage').then((m) => ({ default: m.SupplyChainPage })));
const WorkflowDetailPage = lazy(() => import('./pages/WorkflowDetailPage').then((m) => ({ default: m.WorkflowDetailPage })));
const WorkflowsPage = lazy(() => import('./pages/WorkflowsPage').then((m) => ({ default: m.WorkflowsPage })));

const RepositoryIntelligencePage = lazy(() =>
  import('./pages/RepositoryIntelligencePage').then((m) => ({ default: m.RepositoryIntelligencePage })),
);
const RepositoryDashboardPage = lazy(() =>
  import('./pages/RepositoryDashboardPage').then((m) => ({ default: m.RepositoryDashboardPage })),
);
const RepositoryExplorerPage = lazy(() =>
  import('./pages/RepositoryExplorerPage').then((m) => ({ default: m.RepositoryExplorerPage })),
);
const RepositoryDependenciesPage = lazy(() =>
  import('./pages/RepositoryDependenciesPage').then((m) => ({ default: m.RepositoryDependenciesPage })),
);
const RepositoryReadmePage = lazy(() =>
  import('./pages/RepositoryReadmePage').then((m) => ({ default: m.RepositoryReadmePage })),
);

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Suspense fallback={<PageSkeleton label="Loading page" />}>
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
          {/* Sprint 3 AI review surface. Kept on its own prefix so it cannot
              shadow the legacy `/reviews/:owner/:repo/:number` route. */}
          <Route path="/ai-reviews/:reviewId" element={<AiReviewPage />} />
                <Route path="/history" element={<HistoryPage />} />
                <Route path="/documents" element={<DocumentsPage />} />
                <Route path="/documentation-coverage" element={<DocumentationCoveragePage />} />
                <Route path="/insights" element={<InsightsPage />} />
                <Route path="/feedback" element={<FeedbackPage />} />
                <Route path="/workflows" element={<WorkflowsPage />} />
                <Route path="/workflows/:workflowId" element={<WorkflowDetailPage />} />
                <Route path="/security" element={<SecurityPage />} />
                <Route path="/architecture" element={<ArchitecturePage />} />
<Route path="/test-generator" element={<TestGeneratorPage />} />
<Route path="/supply-chain" element={<SupplyChainPage />} />
<Route path="/chat" element={<ChatPage />} />
                <Route path="/settings" element={<SettingsPage />} />

                <Route path="/repository-intelligence" element={<RepositoryIntelligencePage />} />
                <Route
                  path="/repository-intelligence/:owner/:repo"
                  element={<RepositoryDashboardPage />}
                />
                <Route
                  path="/repository-intelligence/:owner/:repo/explorer"
                  element={<RepositoryExplorerPage />}
                />
                <Route
                  path="/repository-intelligence/:owner/:repo/dependencies"
                  element={<RepositoryDependenciesPage />}
                />
                <Route
                  path="/repository-intelligence/:owner/:repo/readme"
                  element={<RepositoryReadmePage />}
                />
              </Route>
            </Route>

            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </Suspense>
      </BrowserRouter>
    </AuthProvider>
  );
}
