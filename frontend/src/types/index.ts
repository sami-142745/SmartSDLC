export type Severity = 'critical' | 'high' | 'medium' | 'low' | 'info';
export type ScmProvider = 'github' | 'gitlab';
export type Category =
  | 'security'
  | 'bug'
  | 'performance'
  | 'complexity'
  | 'maintainability'
  | 'style';
export type FindingSource = 'heuristic' | 'gemini' | 'combined';

export interface UserSummary {
  github_id: number;
  login: string;
  name: string | null;
  email: string | null;
  avatar_url: string | null;
}

export interface AuthResponse {
  access_token: string;
  user: UserSummary;
}

export interface Finding {
  id: string;
  title: string;
  description: string;
  severity: Severity;
  category: Category;
  file: string | null;
  line: number | null;
  code: string | null;
  recommendation: string | null;
  confidence: number;
  source: FindingSource;
  heuristic_severity?: string | null;
  heuristic_confidence?: number | null;
}

export interface ReviewResponse {
  status: string;
  repository: string;
  owner: string;
  pull_request_number: number;
  pull_request_title: string | null;
  commit_sha: string | null;
  findings: Finding[];
  heuristic_finding_count: number;
  gemini_finding_count: number;
  total_finding_count: number;
  review_score: number | null;
  review_score_100?: number | null;
  score_breakdown?: Record<string, number> | null;
  score_explanation?: string | null;
  review_severity: string | null;
  duration_ms: number | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface Repository {
  id: number;
  name: string;
  full_name: string;
  private: boolean;
  html_url: string;
  default_branch: string | null;
  owner: string | null;
}

export interface RepositoryListResponse {
  repositories: Repository[];
  page: number;
  per_page: number;
  has_more: boolean;
}

export interface PullRequestSummary {
  number: number;
  title: string;
  state: string;
  user: string | null;
  html_url: string;
  created_at: string | null;
  updated_at: string | null;
  head: string | null;
  head_sha: string | null;
  base: string | null;
}

export interface PullRequestListResponse {
  pull_requests: PullRequestSummary[];
  page: number;
  per_page: number;
  has_more: boolean;
}

export interface PullRequestFile {
  filename: string;
  status: string;
  additions: number;
  deletions: number;
  changes: number;
  patch: string | null;
}

export interface RecentReview {
  owner: string;
  repository: string;
  pull_request_number: number;
  pull_request_title: string | null;
  status: string;
  total_finding_count: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  info_count: number;
  review_score: number | null;
  review_score_100?: number | null;
  review_severity: string | null;
  created_at: string | null;
}

export interface DashboardSummary {
  total_reviews: number;
  total_findings: number;
  critical_findings: number;
  high_findings: number;
  medium_findings: number;
  low_findings: number;
  info_findings: number;
  reviews_today: number;
  reviews_this_week: number;
  reviews_this_month: number;
  average_findings_per_review: number;
  recent_reviews: RecentReview[];
  severity_distribution: Record<string, number>;
  category_distribution: Record<string, number>;
}

export interface HistoryItem {
  owner: string;
  repository: string;
  pull_request_number: number;
  pull_request_title: string | null;
  status: string;
  commit_sha: string | null;
  total_finding_count: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  info_count: number;
  review_score: number | null;
  review_score_100?: number | null;
  review_severity: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface HistoryResponse {
  items: HistoryItem[];
  page: number;
  per_page: number;
  total: number;
  total_pages: number;
}

export interface RepositoryMetric {
  owner: string;
  repository: string;
  review_count: number;
  finding_count: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  info_count: number;
  average_findings_per_review: number;
  last_review_at: string | null;
}

export interface RepoMetricsResponse {
  repositories: RepositoryMetric[];
  page: number;
  per_page: number;
  total: number;
  total_pages: number;
}

export type FeedbackAction = 'accepted' | 'dismissed';

export interface FeedbackItem {
  review_id: string;
  finding_id: string;
  owner: string;
  repository: string;
  pull_request_number: number;
  action: FeedbackAction;
  category: string | null;
  severity: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface FeedbackHistoryResponse {
  items: FeedbackItem[];
  page: number;
  per_page: number;
  total: number;
  total_pages: number;
}

export interface FeedbackActionStats {
  accepted: number;
  dismissed: number;
  total: number;
}

export interface FeedbackSummary {
  total_accepted: number;
  total_dismissed: number;
  total_feedback: number;
  acceptance_rate: number;
  category_feedback: Record<string, FeedbackActionStats>;
  severity_feedback: Record<string, FeedbackActionStats>;
}

export interface LearningProfile {
  owner: string;
  repository: string;
  category: string;
  accepted_count: number;
  dismissed_count: number;
  total_count: number;
  acceptance_rate: number;
  learned_weight: number;
  confidence: number;
  updated_at: string | null;
}

export interface FeedbackLearningResponse {
  profiles: LearningProfile[];
  repositories: string[];
  categories: string[];
  total_feedback: number;
  data_available: boolean;
}

export interface WorkflowHistoryEntry {
  stage: string;
  at: string | null;
  detail: string | null;
}

export interface Workflow {
  workflow_id: string;
  owner: string;
  repository: string;
  pull_request_number: number;
  trigger: string;
  provider: string;
  status: string;
  stage: string;
  error: string | null;
  review_id: string | null;
  duration_ms: number | null;
  history: WorkflowHistoryEntry[];
  created_at: string | null;
  updated_at: string | null;
}

export interface WorkflowListResponse {
  items: Workflow[];
  page: number;
  per_page: number;
  total: number;
  total_pages: number;
}

export interface WebhookEvent {
  id: string;
  event: string;
  action: string;
  repository: string | null;
  pull_number: number | null;
  sender: string | null;
  delivery_id: string | null;
  payload_hash_prefix: string | null;
  received_at: string | null;
}

export interface WebhookEventListResponse {
  items: WebhookEvent[];
  total: number;
}

export interface DocumentationSource {
  repository: string;
  owner: string;
  pull_request: string | null;
  commit: string | null;
  branch: string | null;
}

export interface GeneratedDocumentation {
  id: string;
  title: string;
  summary: string;
  architecture: string;
  modules: string[];
  api: string[];
  changes: string[];
  configuration: string[];
  security: string[];
  setup: string[];
  source: DocumentationSource;
  model: string;
  status: string;
  error: string | null;
  duration_ms: number | null;
  generated_at: string | null;
}

export interface DocumentationListResponse {
  items: GeneratedDocumentation[];
  page: number;
  per_page: number;
  total: number;
  total_pages: number;
}

export interface GenerateDocumentationRequest {
  owner: string;
  repository: string;
  pull_request?: number;
}

export type InsightReportType = 'repository' | 'pull_request';
export type TrendStatus = 'increasing' | 'decreasing' | 'stable' | 'insufficient';

export interface TrendPoint {
  period: string;
  reviews: number;
  findings: number;
}

export interface InsightTrend {
  metric: string;
  status: TrendStatus;
  earlier: number;
  later: number;
  note: string | null;
}

export interface InsightRisk {
  key: string;
  label: string;
  severity: Severity;
  triggered: boolean;
  detail: string;
}

export interface InsightRecommendation {
  priority: 'high' | 'medium' | 'low';
  message: string;
  basis: string;
}

export interface InsightNarrative {
  executive_summary: string | null;
  trend_interpretation: string | null;
  risk_explanation: string | null;
  recommendations: string[];
  model: string | null;
}

export interface InsightMetrics {
  severity_distribution: Record<string, number>;
  category_distribution: Record<string, number>;
  finding_source_distribution: Record<string, number>;
  total_findings: number;
  critical_findings: number;
  high_findings: number;
  medium_findings: number;
  low_findings: number;
  info_findings: number;
  security_findings: number;
  complexity_findings: number;
  average_findings_per_review: number;
  finding_frequency: number;
  recurring_categories: string[];
}

export interface InsightActivity {
  review_count: number;
  pull_request_count: number;
  reviews_this_week: number;
  first_review_at: string | null;
  latest_review_at: string | null;
  average_findings_per_review: number;
  findings_per_active_day: number;
  reviews_over_time: TrendPoint[];
}

export interface InsightFeedback {
  total_accepted: number;
  total_dismissed: number;
  total_feedback: number;
  acceptance_rate: number;
  category_feedback: Record<string, FeedbackActionStats>;
  severity_feedback: Record<string, FeedbackActionStats>;
}

export interface InsightReport {
  id: string;
  report_type: InsightReportType;
  owner: string;
  repository: string;
  pull_request: number | null;
  source_review_ids: string[];
  metrics: InsightMetrics;
  activity: InsightActivity;
  feedback: InsightFeedback;
  trends: InsightTrend[];
  risks: InsightRisk[];
  recommendations: InsightRecommendation[];
  narrative: InsightNarrative | null;
  model: string | null;
  status: string;
  error: string | null;
  duration_ms: number;
  generated_at: string | null;
}

export interface InsightListResponse {
  items: InsightReport[];
  page: number;
  per_page: number;
  total: number;
  total_pages: number;
}

export interface GenerateInsightRequest {
  owner: string;
  repository: string;
  pull_request?: number;
  generate_narrative?: boolean;
}