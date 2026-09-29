import type {
  AiReview,
  AiReviewFile,
  AiReviewFinding,
  ArchitectureGraph,
  ArchitectureIssue,
  ArchitectureModule,
  ArchitectureNode,
  DashboardSummary,
  DocumentationAsset,
  DocumentationCoverage,
  DocumentationGap,
  DocumentationIntelligence,
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
  RepositoryDashboard,
  RepositoryFileContent,
  RepositoryHealth,
  RepositoryProfile,
  RepositoryTree,
  ReviewResponse,
  WebhookEvent,
  WebhookEventListResponse,
  Workflow,
  WorkflowListResponse,
  DependencyReport,
  LanguageBreakdown,
  ReadmeIntelligence,
  SecurityExplanation,
  SecurityFinding,
  SecurityFindingsResponse,
  SecurityPosture,
  SecurityRiskSummary,
  SecurityScan,
  SecurityScannerCatalogue,
  GeneratedTestFile,
  TestGeneration,
  TestTarget,
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
/* -------------------------------------------------------------------------
 * Repository intelligence fixtures
 * ---------------------------------------------------------------------- */

export const repositoryProfile: RepositoryProfile = {
  owner: 'acme',
  repository: 'webapp',
  name: 'webapp',
  full_name: 'acme/webapp',
  private: false,
  description: 'The Acme storefront.',
  html_url: 'https://github.com/acme/webapp',
  default_branch: 'main',
  primary_language: 'TypeScript',
  stars: 1_240,
  forks: 86,
  watchers: 42,
  open_issues: 17,
  size_kb: 4_096,
  license_key: 'mit',
  license_name: 'MIT License',
  topics: ['react', 'typescript'],
  created_at: '2021-03-01T00:00:00Z',
  updated_at: '2026-02-01T00:00:00Z',
  pushed_at: '2026-02-20T09:30:00Z',
  archived: false,
  is_fork: false,
};

export const repositoryHealth: RepositoryHealth = {
  owner: 'acme',
  repository: 'webapp',
  score: 82.4,
  grade: 'B',
  components: [
    { key: 'activity', label: 'Recent activity', score: 90, weight: 0.25, detail: 'Pushed 3 days ago.' },
    { key: 'documentation', label: 'Documentation', score: 70, weight: 0.2, detail: 'README present.' },
    { key: 'community', label: 'Community', score: 60, weight: 0.2, detail: '17 open issues.' },
    { key: 'licensing', label: 'Licensing', score: 100, weight: 0.15, detail: 'MIT detected.' },
    { key: 'description', label: 'Description', score: null, weight: 0.1, detail: 'Not measurable.' },
  ],
  unavailable_signals: ['description'],
  measured_weight: 0.8,
  method: 'Weighted mean of observable signals',
  generated_at: '2026-02-21T10:00:00Z',
  cached: false,
};

export const languageBreakdown: LanguageBreakdown = {
  owner: 'acme',
  repository: 'webapp',
  total_bytes: 100_000,
  languages: [
    { name: 'TypeScript', bytes: 70_000, percent: 0.7 },
    { name: 'CSS', bytes: 20_000, percent: 0.2 },
  ],
  other_bytes: 10_000,
  truncated: false,
  cached: false,
};

export const dependencyReport: DependencyReport = {
  owner: 'acme',
  repository: 'webapp',
  manifests: [
    { path: 'package.json', ecosystem: 'npm', found: true, reason: null },
    { path: 'requirements.txt', ecosystem: 'pypi', found: false, reason: 'not found' },
  ],
  dependencies: [
    {
      name: 'react',
      version: '18.3.1',
      ecosystem: 'npm',
      manifest: 'package.json',
      scope: 'runtime',
      risks: [],
      pinned: true,
    },
    {
      name: 'lodash',
      version: '^4.17.21',
      ecosystem: 'npm',
      manifest: 'package.json',
      scope: 'runtime',
      risks: ['floating_version'],
      pinned: false,
    },
  ],
  total: 2,
  direct_count: 2,
  flagged_count: 1,
  ecosystems: ['npm'],
  cached: false,
};

export const readmeIntelligence: ReadmeIntelligence = {
  owner: 'acme',
  repository: 'webapp',
  path: 'README.md',
  available: true,
  reason: null,
  raw: '# Webapp\n\n## Install\n\nRun it.\n',
  size_bytes: 2_048,
  line_count: 42,
  word_count: 310,
  sections: [
    { heading: 'Webapp', level: 1, line: 1, preview: 'The Acme storefront.' },
    { heading: 'Install', level: 2, line: 3, preview: 'Run it.' },
  ],
  has_badges: true,
  badge_count: 2,
  has_toc: true,
  has_install_section: true,
  has_usage_section: false,
  has_license_section: true,
  code_blocks: 3,
  languages_used: ['bash'],
  images: 1,
  links: 7,
  cached: false,
};

export const repositoryTree: RepositoryTree = {
  owner: 'acme',
  repository: 'webapp',
  ref: 'main',
  truncated: false,
  total_files: 2,
  total_directories: 1,
  total_bytes: 1_024,
  entries: [
    { path: 'src', name: 'src', type: 'directory', size: 0, depth: 0 },
    { path: 'src/index.ts', name: 'index.ts', type: 'file', size: 512, depth: 1 },
    { path: 'README.md', name: 'README.md', type: 'file', size: 512, depth: 0 },
  ],
  cached: false,
};

export const repositoryDashboard: RepositoryDashboard = {
  owner: 'acme',
  repository: 'webapp',
  profile: repositoryProfile,
  health: repositoryHealth,
  languages: languageBreakdown,
  dependencies: dependencyReport,
  readme: readmeIntelligence,
  generated_at: '2026-02-21T10:00:00Z',
  cached: false,
};

export const repositoryFile: RepositoryFileContent = {
  path: 'src/index.ts',
  content: 'export const main = () => 1;',
  size: 28,
  truncated: false,
  language: 'typescript',
  binary: false,
};

// ---------------------------------------------------------------------------
// Sprint 3 AI review fixtures (backend schema v2)
// ---------------------------------------------------------------------------

export function makeAiReviewFinding(
  overrides: Partial<AiReviewFinding> = {},
): AiReviewFinding {
  return {
    finding_id: 'f-1',
    file: 'src/api/users.py',
    line: 42,
    severity: 'high',
    category: 'security',
    confidence: 0.9,
    title: 'Unvalidated redirect target',
    description: 'The redirect target comes straight from the query string.',
    suggestion: 'Resolve the target against an allow-list of known paths.',
    original_code: 'return redirect(request.args["next"])',
    suggested_code: 'return redirect(allowed(request.args.get("next")))',
    source: 'ai',
    rule_id: null,
    ...overrides,
  };
}

export function makeAiReviewFile(overrides: Partial<AiReviewFile> = {}): AiReviewFile {
  return {
    path: 'src/api/users.py',
    previous_path: null,
    status: 'modified',
    language: 'python',
    additions: 6,
    deletions: 2,
    changes: 8,
    is_binary: false,
    patch: [
      '--- a/src/api/users.py',
      '+++ b/src/api/users.py',
      '@@ -40,3 +40,6 @@ def login():',
      '     user = find_user(name)',
      '-    return redirect(request.args["next"])',
      '+    target = request.args["next"]',
      '+    session["next"] = target',
      '+    return redirect(target)',
      '',
    ].join('\n'),
    finding_ids: ['f-1'],
    ...overrides,
  };
}

export function makeAiReview(overrides: Partial<AiReview> = {}): AiReview {
  const finding = makeAiReviewFinding();
  const file = makeAiReviewFile();
  return {
    review_id: 'r-1',
    schema_version: 2,
    status: 'complete',
    ai_status: 'complete',
    owner: 'acme',
    repository: 'webapp',
    pull_request_number: 101,
    pull_request_title: 'Harden the login redirect',
    commit_sha: 'abc1234',
    provider: 'github',
    summary: {
      assessment_label: 'AI review assessment',
      assessment_disclaimer:
        'Scores reflect the changes in this pull request only. They are not a measure of overall repository quality.',
      assessment_score: 62,
      assessment_severity: 'high',
      metrics: [
        { dimension: 'bugs', label: 'Bugs', score: 70, finding_count: 0 },
        { dimension: 'security', label: 'Security', score: 40, finding_count: 1 },
        { dimension: 'performance', label: 'Performance', score: 100, finding_count: 0 },
        { dimension: 'code_quality', label: 'Quality', score: 100, finding_count: 0 },
        { dimension: 'maintainability', label: 'Maintainability', score: 100, finding_count: 0 },
        { dimension: 'testing', label: 'Testing', score: 100, finding_count: 0 },
      ],
      total_findings: 1,
      severity_counts: { high: 1 },
      category_counts: { security: 1 },
      files_reviewed: 1,
      lines_added: 6,
      lines_deleted: 2,
      highest_severity: 'high',
    },
    files: [file],
    findings: [finding],
    suggestions: [],
    error: null,
    duration_ms: 4210,
    created_at: '2026-02-21T10:00:00Z',
    updated_at: '2026-02-21T10:00:04Z',
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Security Intelligence Engine (Sprint 4)
// ---------------------------------------------------------------------------

export function securitySeverityCounts(
  overrides: Partial<SecurityRiskSummary['severity_counts']> = {},
): SecurityRiskSummary['severity_counts'] {
  return { critical: 0, high: 0, medium: 0, low: 0, info: 0, ...overrides };
}

export function securitySummary(
  overrides: Partial<SecurityRiskSummary> = {},
): SecurityRiskSummary {
  return {
    total_findings: 2,
    severity_counts: securitySeverityCounts({ critical: 1, high: 1 }),
    weighted_risk: 11,
    posture_score: 94,
    category_distribution: { secrets: 1, injection: 1 },
    scanner_distribution: { secret: 1, code: 1 },
    files_scanned: 12,
    files_skipped: 3,
    findings_by_file: { 'app/config.py': 1, 'app/db.py': 1 },
    dependencies_analyzed: 4,
    ...overrides,
  };
}

export function securityFinding(overrides: Partial<SecurityFinding> = {}): SecurityFinding {
  return {
    finding_id: 'f-1',
    repository_id: 'octocat/hello-world',
    file: 'app/config.py',
    line: 4,
    column: null,
    category: 'secrets',
    severity: 'critical',
    confidence: 0.95,
    title: 'Exposed AWS access key',
    description: 'A credential-shaped value is committed to the repository.',
    remediation: 'Revoke the key and load it from the environment.',
    scanner: 'secret',
    fingerprint: 'fp-1',
    created_at: '2026-03-01T09:00:00Z',
    ...overrides,
  };
}

export const securityFindings: SecurityFinding[] = [
  securityFinding(),
  securityFinding({
    finding_id: 'f-2',
    fingerprint: 'fp-2',
    file: 'app/db.py',
    line: 22,
    category: 'injection',
    severity: 'high',
    title: 'SQL query built by concatenation',
    description: 'User input is concatenated into a SQL statement.',
    scanner: 'code',
  }),
];

export function securityScan(overrides: Partial<SecurityScan> = {}): SecurityScan {
  const findings = overrides.findings ?? securityFindings;
  return {
    scan_id: 'scan-1',
    schema_version: 1,
    status: 'complete',
    repository_id: 'octocat/hello-world',
    owner: 'octocat',
    repository: 'Hello-World',
    full_name: 'octocat/Hello-World',
    provider: 'github',
    ref: 'main',
    commit_sha: 'commit123',
    summary: securitySummary({ total_findings: findings.length }),
    findings,
    errors: [],
    duration_ms: 1200,
    scanned_at: '2026-03-01T09:00:00Z',
    vulnerability_source: 'none',
    ...overrides,
  };
}

export function securityPosture(overrides: Partial<SecurityPosture> = {}): SecurityPosture {
  return {
    repository_id: 'octocat/hello-world',
    owner: 'octocat',
    repository: 'Hello-World',
    full_name: 'octocat/Hello-World',
    has_scan: true,
    scan_id: 'scan-1',
    scanned_at: '2026-03-01T09:00:00Z',
    summary: securitySummary(),
    methodology: 'Deterministic rule and pattern analysis.',
    ...overrides,
  };
}

export function securityFindingsResponse(
  overrides: Partial<SecurityFindingsResponse> = {},
): SecurityFindingsResponse {
  const findings = overrides.findings ?? securityFindings;
  return { scan_id: 'scan-1', total: findings.length, findings, ...overrides };
}

export function securityExplanation(
  overrides: Partial<SecurityExplanation> = {},
): SecurityExplanation {
  return {
    finding_id: 'f-1',
    explanation: 'A credential is committed to source control and is readable by anyone with repository access.',
    impact: 'The key can be used to access the associated cloud account.',
    remediation: 'Revoke the key, then load it from the environment.',
    model: 'gemini-flash-lite-latest',
    unavailable_reason: null,
    ...overrides,
  };
}

export const securityScannerCatalogue: SecurityScannerCatalogue = {
  secret: [
    {
      rule_id: 'secret.aws_access_key_id',
      title: 'AWS access key id',
      severity: 'critical',
      category: 'secrets',
    },
  ],
  code: [{ rule_id: 'code.eval', title: 'Dynamic evaluation', severity: 'high', category: 'code_execution' }],
  dependency: [
    {
      rule_id: 'dependency.unpinned',
      title: 'Unpinned dependency',
      severity: 'low',
      category: 'dependencies',
    },
  ],
  severities: ['critical', 'high', 'medium', 'low', 'info'],
  categories: [
    'secrets',
    'injection',
    'code_execution',
    'crypto',
    'path_traversal',
    'deserialization',
    'authentication',
    'dependencies',
    'misconfiguration',
  ],
  scanners: ['secret', 'code', 'dependency'],
};

// ---------------------------------------------------------------------------
// Architecture Intelligence (Sprint 5)
// ---------------------------------------------------------------------------

export function architectureNode(
  overrides: Partial<ArchitectureNode> = {},
): ArchitectureNode {
  return {
    id: 'app.services.auth',
    name: 'auth',
    path: 'app/services/auth.py',
    language: 'python',
    kind: 'service',
    evidence: 'defines a service module under the services package',
    line_count: 180,
    fan_out: 2,
    fan_in: 1,
    parsed: true,
    ...overrides,
  };
}

export function architectureModule(
  overrides: Partial<ArchitectureModule> = {},
): ArchitectureModule {
  return {
    id: 'app.services.auth',
    name: 'auth',
    path: 'app/services/auth.py',
    language: 'python',
    kind: 'service',
    line_count: 180,
    fan_in: 1,
    fan_out: 2,
    dependencies: ['fastapi'],
    ...overrides,
  };
}

export function architectureIssue(
  overrides: Partial<ArchitectureIssue> = {},
): ArchitectureIssue {
  return {
    kind: 'circular_dependency',
    severity: 'warning',
    title: 'Circular dependency',
    detail: 'app.services.auth, app.services.users form an import cycle.',
    nodes: ['app.services.auth', 'app.services.users'],
    ...overrides,
  };
}

export function architectureGraph(
  overrides: Partial<ArchitectureGraph> = {},
): ArchitectureGraph {
  const modules = overrides.modules ?? [
    architectureModule(),
    architectureModule({
      id: 'app.routers.auth',
      name: 'auth',
      path: 'app/routers/auth.py',
      kind: 'route',
      fan_in: 0,
      fan_out: 1,
      dependencies: [],
    }),
    architectureModule({
      id: 'app.db.session',
      name: 'session',
      path: 'app/db/session.py',
      kind: 'database',
      fan_in: 2,
      fan_out: 0,
      dependencies: ['sqlalchemy'],
    }),
  ];
  const nodes = overrides.nodes ?? modules.map((module) => architectureNode(module));
  return {
    repository_id: 'acme/webapp',
    owner: 'acme',
    repository: 'webapp',
    full_name: 'acme/webapp',
    provider: 'github',
    ref: 'main',
    commit_sha: 'abc123',
    analyzed_at: '2026-03-02T10:00:00Z',
    duration_ms: 800,
    nodes,
    edges: [
      {
        source: 'app.routers.auth',
        target: 'app.services.auth',
        kind: 'internal',
        reference: 'app.services.auth',
        resolved: true,
      },
      {
        source: 'app.services.auth',
        target: 'app.db.session',
        kind: 'internal',
        reference: '../db/session',
        resolved: true,
      },
    ],
    modules,
    issues: [],
    summary: {
      total_modules: modules.length,
      total_edges: 2,
      internal_edges: 2,
      external_edges: 0,
      language_distribution: { python: modules.length },
      kind_distribution: { service: 1, route: 1, database: 1 },
      external_packages: 0,
      unresolved_imports: 0,
      cycles: 0,
      cycle_groups: 0,
      most_depended_on: ['app.db.session'],
      most_dependent: ['app.routers.auth'],
      total_lines: modules.reduce((sum, module) => sum + (module.line_count ?? 0), 0),
      methodology: 'No model is used. Structure is derived from imports and file size.',
    },
    errors: [],
    truncated: false,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Documentation Intelligence
// ---------------------------------------------------------------------------

export function documentationAsset(overrides: Partial<DocumentationAsset> = {}): DocumentationAsset {
  return {
    path: 'README.md',
    kind: 'readme',
    language: 'markdown',
    size_bytes: 5120,
    line_count: 120,
    word_count: 900,
    headings: [
      { level: 1, text: 'Project', line: 1 },
      { level: 2, text: 'Installation', line: 12 },
      { level: 2, text: 'Usage', line: 30 },
    ],
    has_toc: true,
    has_install: true,
    has_usage: true,
    has_examples: false,
    has_license: false,
    has_contributing: false,
    code_blocks: 3,
    images: 1,
    badges: 1,
    links: [
      { text: 'guide', target: './docs/guide.md', internal: true, resolved: true },
      { text: 'site', target: 'https://example.com', internal: false, resolved: null },
    ],
    ...overrides,
  };
}

export function documentationCoverage(
  overrides: Partial<DocumentationCoverage> = {},
): DocumentationCoverage {
  return {
    path: 'app/services/auth.py',
    language: 'python',
    public_symbols: 4,
    documented_symbols: 2,
    coverage: 0.5,
    undocumented: ['verify_token', 'rotate_key'],
    ...overrides,
  };
}

export function documentationGap(overrides: Partial<DocumentationGap> = {}): DocumentationGap {
  return {
    kind: 'missing_license',
    severity: 'warning',
    title: 'No license file',
    detail: 'Without a license the terms under which the code may be used are undefined.',
    evidence: 'No LICENSE/COPYING file was found in the repository tree.',
    paths: [],
    ...overrides,
  };
}

export function documentationIntelligence(
  overrides: Partial<DocumentationIntelligence> = {},
): DocumentationIntelligence {
  const assets = overrides.assets ?? [
    documentationAsset(),
    documentationAsset({
      path: 'docs/guide.md',
      kind: 'guide',
      word_count: 420,
      headings: [{ level: 1, text: 'Guide', line: 1 }],
      has_toc: false,
      has_install: false,
      has_usage: false,
      code_blocks: 0,
      images: 0,
      badges: 0,
      links: [{ text: 'gone', target: './missing.md', internal: true, resolved: false }],
    }),
  ];
  const coverage = overrides.coverage ?? [
    documentationCoverage(),
    documentationCoverage({
      path: 'app/db/session.py',
      public_symbols: 2,
      documented_symbols: 2,
      coverage: 1,
      undocumented: [],
    }),
  ];
  return {
    repository_id: 'acme/webapp',
    owner: 'acme',
    repository: 'webapp',
    full_name: 'acme/webapp',
    provider: 'github',
    ref: 'main',
    commit_sha: 'abc123',
    analyzed_at: '2026-03-02T10:00:00Z',
    duration_ms: 640,
    assets,
    coverage,
    gaps: [documentationGap()],
    summary: {
      total_assets: assets.length,
      documentation_files: assets.length,
      source_files: 12,
      documentation_ratio: 0.2,
      readme_present: true,
      readme_word_count: 900,
      readme_sections: 3,
      missing_canonical: ['license'],
      total_links: 3,
      broken_links: 1,
      public_symbols: 6,
      documented_symbols: 4,
      docstring_coverage: 0.6667,
      coverage_score: 62,
      gap_count: 1,
      methodology: 'No model is used. Documentation coverage is measured from the repository itself.',
    },
    errors: [],
    truncated: false,
    ...overrides,
  };
}
export function testTarget(overrides: Partial<TestTarget> = {}): TestTarget {
  return {
    name: 'normalise_path',
    qualified_name: 'normalise_path',
    kind: 'function',
    file: 'app/services/scm.py',
    line: 12,
    signature: 'normalise_path(path: str) -> str',
    reason: 'no_test_reference',
    evidence: '3 test file(s) in the repository reference none of `normalise_path`.',
    priority: 60,
    test_names: ['test_normalise_path_behaviour', 'test_normalise_path_invalid'],
    ...overrides,
  };
}

export function generatedTestFile(
  overrides: Partial<GeneratedTestFile> = {},
): GeneratedTestFile {
  return {
    path: 'tests/test_scm.py',
    language: 'python',
    framework: 'pytest',
    content: [
      '"""Tests proposed by SmartSDLC Test Generation."""',
      '',
      'from app.services.scm import normalise_path',
      '',
      'import pytest',
      '',
      '',
      'def test_normalise_path_behaviour() -> None:',
      '    assert normalise_path("a") == "a"',
      '',
    ].join('\n'),
    source: 'gemini',
    model: 'gemini-2.5-flash',
    test_names: ['test_normalise_path_behaviour'],
    covers: ['normalise_path'],
    usable: true,
    validation: [],
    ...overrides,
  };
}

export function testGeneration(overrides: Partial<TestGeneration> = {}): TestGeneration {
  const targets = overrides.targets ?? [
    testTarget(),
    testTarget({
      name: 'authorise_request',
      qualified_name: 'ScmProvider.authorise_request',
      kind: 'method',
      file: 'app/services/gate.py',
      line: 40,
      signature: 'authorise_request(self, token: str) -> bool',
      evidence: 'The repository has no recognisable test file, so no symbol is referenced by a test.',
      priority: 90,
      test_names: ['test_authorise_request_behaviour'],
    }),
  ];
  const files = overrides.files ?? [
    generatedTestFile(),
    generatedTestFile({
      path: 'tests/test_scm_scaffold.py',
      content: '"""Scaffold."""\n\nimport pytest\n',
      source: 'deterministic',
      model: null,
      test_names: ['test_normalise_path_behaviour'],
      covers: ['normalise_path'],
      usable: false,
      validation: [
        {
          code: 'placeholder',
          detail: 'No language model was available, so these tests assert nothing.',
          line: null,
        },
      ],
    }),
  ];
  return {
    repository_id: 'acme/webapp',
    owner: 'acme',
    repository: 'webapp',
    full_name: 'acme/webapp',
    provider: 'github',
    ref: 'main',
    commit_sha: 'abc123',
    generated_at: '2026-03-02T10:00:00Z',
    duration_ms: 820,
    framework: 'pytest',
    test_directories: ['tests'],
    existing_test_files: ['tests/test_auth.py'],
    targets,
    files,
    summary: {
      framework: 'pytest',
      source_files_scanned: 12,
      public_symbols: 40,
      existing_test_files: 1,
      untested_symbols: targets.length,
      targets: targets.length,
      generated_files: files.length,
      generated_tests: files.reduce((sum, file) => sum + file.test_names.length, 0),
      rejected_files: files.filter((file) => !file.usable).length,
      methodology:
        'Targets are selected deterministically. A model is used only to write the body of a proposed test, and every proposed file is re-parsed and screened before it is shown.',
    },
    model: 'gemini-2.5-flash',
    unavailable_reason: null,
    errors: [],
    truncated: false,
    ...overrides,
  };
}
