import type {
  DashboardSummary,
  FeedbackHistoryResponse,
  FeedbackSummary,
  Finding,
  HistoryResponse,
  PullRequestFile,
  PullRequestSummary,
  RepoMetricsResponse,
  Repository,
  ReviewResponse,
} from '../types';

export const TEST_TOKEN = `a.${btoa(JSON.stringify({ sub: '42', login: 'octocat' }))}.c`;

export function makeFinding(id: string, overrides: Partial<Finding> = {}): Finding {
  return {
    id,
    title: `Finding ${id}`,
    description: `Description for ${id}`,
    severity: 'high',
    category: 'security',
    file: 'src/app.ts',
    line: 12,
    code: 'const secret = "x";',
    recommendation: 'Rotate the value.',
    confidence: 0.9,
    source: 'heuristic',
    ...overrides,
  };
}

export const dashboardSummary: DashboardSummary = {
  total_reviews: 5,
  total_findings: 23,
  critical_findings: 2,
  high_findings: 7,
  medium_findings: 8,
  low_findings: 4,
  info_findings: 2,
  reviews_today: 1,
  reviews_this_week: 3,
  reviews_this_month: 5,
  average_findings_per_review: 4.6,
  recent_reviews: [
    {
      owner: 'acme',
      repository: 'webapp',
      pull_request_number: 101,
      pull_request_title: 'Add auth flow',
      status: 'complete',
      total_finding_count: 4,
      critical_count: 0,
      high_count: 2,
      medium_count: 1,
      low_count: 1,
      info_count: 0,
      review_score: 78,
      review_severity: 'high',
      created_at: '2026-09-08T10:00:00Z',
    },
  ],
  severity_distribution: { critical: 2, high: 7, medium: 8, low: 4, info: 2 },
  category_distribution: { security: 9, bug: 5, performance: 4, complexity: 3, maintainability: 2, style: 0 },
};

export const feedbackSummary: FeedbackSummary = {
  total_accepted: 6,
  total_dismissed: 4,
  total_feedback: 10,
  acceptance_rate: 0.6,
  category_feedback: {
    security: { accepted: 4, dismissed: 1, total: 5 },
    bug: { accepted: 2, dismissed: 3, total: 5 },
  },
  severity_feedback: {
    high: { accepted: 3, dismissed: 1, total: 4 },
    medium: { accepted: 3, dismissed: 3, total: 6 },
  },
};

export const repositories: Repository[] = [
  {
    id: 1,
    name: 'webapp',
    full_name: 'acme/webapp',
    private: false,
    html_url: 'https://github.com/acme/webapp',
    default_branch: 'main',
    owner: 'acme',
  },
  {
    id: 2,
    name: 'api',
    full_name: 'acme/api',
    private: true,
    html_url: 'https://github.com/acme/api',
    default_branch: 'main',
    owner: 'acme',
  },
];

export const pullRequests: PullRequestSummary[] = [
  {
    number: 101,
    title: 'Add auth flow',
    state: 'open',
    user: 'octocat',
    html_url: 'https://github.com/acme/webapp/pull/101',
    created_at: '2026-09-01T10:00:00Z',
    updated_at: '2026-09-08T10:00:00Z',
    head: 'feature/auth',
    head_sha: 'abc123',
    base: 'main',
  },
  {
    number: 100,
    title: 'Fix rate limiting',
    state: 'closed',
    user: 'mona',
    html_url: 'https://github.com/acme/webapp/pull/100',
    created_at: '2026-08-20T10:00:00Z',
    updated_at: '2026-08-22T10:00:00Z',
    head: 'fix/ratelimit',
    head_sha: 'def456',
    base: 'main',
  },
];

export const pullRequestFiles: PullRequestFile[] = [
  { filename: 'src/auth.ts', status: 'modified', additions: 12, deletions: 2, changes: 14, patch: '@@ -1,5 +1,15 @@' },
];

export const pullRequestDiff = `diff --git a/src/auth.ts b/src/auth.ts
index abc..def 100644
--- a/src/auth.ts
+++ b/src/auth.ts
@@ -1,5 +1,15 @@
+const token = process.env.TOKEN;
 export function login() {
-  return legacyLogin();
+  return secureLogin();
 }
`;

export const findings: Finding[] = [
  makeFinding('f1', { severity: 'critical', source: 'heuristic', category: 'security' }),
  makeFinding('f2', { severity: 'info', source: 'gemini', category: 'style', confidence: 0.4 }),
];

export function makeReview(overrides: Partial<ReviewResponse> = {}): ReviewResponse {
  return {
    status: 'complete',
    repository: 'webapp',
    owner: 'acme',
    pull_request_number: 101,
    pull_request_title: 'Add auth flow',
    commit_sha: 'abc123',
    findings,
    heuristic_finding_count: 1,
    gemini_finding_count: 1,
    total_finding_count: 2,
    review_score: 76,
    review_severity: 'high',
    duration_ms: 1500,
    created_at: '2026-09-08T10:00:00Z',
    updated_at: '2026-09-08T10:00:00Z',
    ...overrides,
  };
}

export const history: HistoryResponse = {
  items: [
    {
      owner: 'acme',
      repository: 'webapp',
      pull_request_number: 101,
      pull_request_title: 'Add auth flow',
      status: 'complete',
      commit_sha: 'abc123',
      total_finding_count: 2,
      critical_count: 1,
      high_count: 0,
      medium_count: 0,
      low_count: 0,
      info_count: 1,
      review_score: 76,
      review_severity: 'high',
      created_at: '2026-09-08T10:00:00Z',
      updated_at: '2026-09-08T10:00:00Z',
    },
  ],
  page: 1,
  per_page: 20,
  total: 1,
  total_pages: 1,
};

export const emptyFeedbackHistory: FeedbackHistoryResponse = {
  items: [],
  page: 1,
  per_page: 20,
  total: 0,
  total_pages: 1,
};

export const repoMetrics: RepoMetricsResponse = {
  repositories: [
    {
      owner: 'acme',
      repository: 'webapp',
      review_count: 3,
      finding_count: 12,
      critical_count: 1,
      high_count: 4,
      medium_count: 4,
      low_count: 2,
      info_count: 1,
      average_findings_per_review: 4,
      last_review_at: '2026-09-08T10:00:00Z',
    },
  ],
  page: 1,
  per_page: 20,
  total: 1,
  total_pages: 1,
};