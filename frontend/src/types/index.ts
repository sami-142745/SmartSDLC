export type Severity = 'critical' | 'high' | 'medium' | 'low' | 'info';
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