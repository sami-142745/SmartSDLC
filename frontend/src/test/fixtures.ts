import type {
  DashboardSummary,
  DocumentationListResponse,
  GeneratedDocumentation,
  FeedbackHistoryResponse,
  FeedbackLearningResponse,
  FeedbackSummary,
  Finding,
  HistoryResponse,
  InsightListResponse,
  InsightReport,
  LearningProfile,
  PullRequestFile,
  PullRequestSummary,
  RepoMetricsResponse,
  Repository,
  ReviewResponse,
  WebhookEvent,
  WebhookEventListResponse,
  Workflow,
  WorkflowListResponse,
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

export const learningProfiles: LearningProfile[] = [
  {
    owner: 'acme',
    repository: 'webapp',
    category: 'security',
    accepted_count: 12,
    dismissed_count: 3,
    total_count: 15,
    acceptance_rate: 0.8,
    learned_weight: 1.09,
    confidence: 1,
    updated_at: '2026-09-12T10:00:00Z',
  },
  {
    owner: 'acme',
    repository: 'webapp',
    category: 'bug',
    accepted_count: 1,
    dismissed_count: 6,
    total_count: 7,
    acceptance_rate: 0.14,
    learned_weight: 0.89,
    confidence: 1,
    updated_at: '2026-09-11T10:00:00Z',
  },
];

export const learningResponse: FeedbackLearningResponse = {
  profiles: learningProfiles,
  repositories: ['webapp'],
  categories: ['bug', 'security'],
  total_feedback: 22,
  data_available: true,
};

export const emptyLearningResponse: FeedbackLearningResponse = {
  profiles: [],
  repositories: [],
  categories: [],
  total_feedback: 0,
  data_available: false,
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

export const documentationResponse: GeneratedDocumentation = {
  id: '666666666666666666666666',
  title: 'acme/webapp guide',
  summary: 'Summarizes the web application.',
  architecture: 'Client-server.',
  modules: ['frontend', 'backend'],
  api: ['GET /health (health check)'],
  changes: ['Added authentication'],
  configuration: ['PORT (server port)'],
  security: ['Secrets are redacted before analysis'],
  setup: ['npm install'],
  source: {
    repository: 'acme/webapp',
    owner: 'acme',
    pull_request: '#12',
    commit: 'abc123',
    branch: 'main',
  },
  model: 'gemini-2.5-flash',
  status: 'complete',
  error: null,
  duration_ms: 1200,
  generated_at: '2026-09-12T09:00:00Z',
};

export const documentationHistory: DocumentationListResponse = {
  items: [documentationResponse],
  page: 1,
  per_page: 50,
  total: 1,
  total_pages: 1,
};

export const insightResponse: InsightReport = {
  id: '777777777777777777777777',
  report_type: 'repository',
  owner: 'acme',
  repository: 'webapp',
  pull_request: null,
  source_review_ids: ['r1', 'r2', 'r3'],
  metrics: {
    severity_distribution: { critical: 1, high: 4, medium: 4, low: 2, info: 1 },
    category_distribution: { security: 5, bug: 4, performance: 3 },
    finding_source_distribution: { combined: 0, gemini: 12 },
    total_findings: 12,
    critical_findings: 1,
    high_findings: 4,
    medium_findings: 4,
    low_findings: 2,
    info_findings: 1,
    security_findings: 5,
    complexity_findings: 0,
    average_findings_per_review: 4,
    finding_frequency: 3,
    recurring_categories: ['security'],
  },
  activity: {
    review_count: 3,
    pull_request_count: 2,
    reviews_this_week: 1,
    first_review_at: '2026-06-01T10:00:00Z',
    latest_review_at: '2026-09-08T10:00:00Z',
    average_findings_per_review: 4,
    findings_per_active_day: 3,
    reviews_over_time: [
      { period: '2026-06', reviews: 1, findings: 3 },
      { period: '2026-08', reviews: 1, findings: 4 },
      { period: '2026-09', reviews: 1, findings: 5 },
    ],
  },
  feedback: {
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
  },
  trends: [
    { metric: 'findings_per_review', status: 'increasing', earlier: 3, later: 5, note: null },
    { metric: 'critical_findings', status: 'stable', earlier: 1, later: 1, note: null },
    { metric: 'review_cadence', status: 'insufficient', earlier: 1, later: 1, note: 'Too few buckets' },
  ],
  risks: [
    {
      key: 'critical_recurrence',
      label: 'Critical issues recurring',
      severity: 'critical',
      triggered: true,
      detail: 'Critical findings appeared across multiple reviews.',
    },
    { key: 'security_concentration', label: 'Security concentration', severity: 'high', triggered: false, detail: '—' },
  ],
  recommendations: [
    {
      priority: 'high',
      message: 'Triage the recurring critical finding cluster.',
      basis: 'Critical recurrence across reviews.',
    },
    {
      priority: 'medium',
      message: 'Focus on the security category cluster.',
      basis: 'Security is the most frequent category.',
    },
  ],
  narrative: null,
  model: null,
  status: 'complete',
  error: null,
  duration_ms: 900,
  generated_at: '2026-09-12T09:00:00Z',
};

export const insightHistory: InsightListResponse = {
  items: [insightResponse],
  page: 1,
  per_page: 50,
  total: 1,
  total_pages: 1,
};

export const emptyInsightHistory: InsightListResponse = {
  items: [],
  page: 1,
  per_page: 50,
  total: 0,
  total_pages: 0,
};

export const workflow: Workflow = {
  workflow_id: 'wf_123abc',
  owner: 'acme',
  repository: 'webapp',
  pull_request_number: 101,
  trigger: 'manual',
  provider: 'github',
  status: 'completed',
  stage: 'COMPLETED',
  error: null,
  review_id: 'review_xyz',
  duration_ms: 2400,
  history: [
    { stage: 'RECEIVED', at: '2026-09-12T09:00:00Z', detail: null },
    { stage: 'VALIDATED', at: '2026-09-12T09:00:00Z', detail: null },
    { stage: 'FETCHING', at: '2026-09-12T09:00:01Z', detail: null },
    { stage: 'ANALYZING', at: '2026-09-12T09:00:01Z', detail: null },
    { stage: 'GENERATING_REVIEW', at: '2026-09-12T09:00:02Z', detail: null },
    { stage: 'PERSISTING', at: '2026-09-12T09:00:02Z', detail: null },
    { stage: 'COMPLETED', at: '2026-09-12T09:00:02Z', detail: null },
  ],
  created_at: '2026-09-12T09:00:00Z',
  updated_at: '2026-09-12T09:00:02Z',
};

export const failedWorkflow: Workflow = {
  ...workflow,
  workflow_id: 'wf_fail',
  status: 'failed',
  stage: 'FAILED',
  review_id: null,
  error: 'Not Found',
  duration_ms: 800,
};

export const workflowsResponse: WorkflowListResponse = {
  items: [workflow, failedWorkflow],
  page: 1,
  per_page: 100,
  total: 2,
  total_pages: 1,
};

export const emptyWorkflowsResponse: WorkflowListResponse = {
  items: [],
  page: 1,
  per_page: 100,
  total: 0,
  total_pages: 0,
};

export const webhookEvent: WebhookEvent = {
  id: 'evt_1',
  event: 'pull_request',
  action: 'opened',
  repository: 'octocat/Hello-World',
  pull_number: 101,
  sender: 'octocat',
  delivery_id: 'deliv-abcd1234efgh5678ijkl',
  payload_hash_prefix: 'a1b2c3d4e5f60718\u2026',
  received_at: '2026-09-12T09:00:00Z',
};

export const webhookEventsResponse: WebhookEventListResponse = {
  items: [webhookEvent],
  total: 1,
};

export const emptyWebhookEvents: WebhookEventListResponse = {
  items: [],
  total: 0,
};