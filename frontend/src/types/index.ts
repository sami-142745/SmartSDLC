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

/* -------------------------------------------------------------------------
 * Repository intelligence
 *
 * These mirror `backend/app/schemas/repository_intelligence.py` exactly. Any
 * signal the provider does not report is `null` rather than 0, so the UI can
 * say "not measured" instead of implying a measured zero.
 * ---------------------------------------------------------------------- */

export interface RepositoryProfile {
  owner: string;
  repository: string;
  name: string;
  full_name: string;
  private: boolean;
  description: string | null;
  html_url: string | null;
  default_branch: string | null;
  primary_language: string | null;
  stars: number;
  forks: number;
  watchers: number;
  open_issues: number;
  size_kb: number;
  license_key: string | null;
  license_name: string | null;
  topics: string[];
  created_at: string | null;
  updated_at: string | null;
  pushed_at: string | null;
  archived: boolean;
  is_fork: boolean;
}

export interface HealthComponent {
  key: string;
  label: string;
  /** null when the signal is not observable for this repository. */
  score: number | null;
  weight: number;
  detail: string;
}

export interface RepositoryHealth {
  owner: string;
  repository: string;
  score: number;
  grade: string;
  components: HealthComponent[];
  unavailable_signals: string[];
  measured_weight: number;
  method: string;
  generated_at: string | null;
  cached: boolean;
}

export interface LanguageSlice {
  name: string;
  bytes: number;
  percent: number;
}

export interface LanguageBreakdown {
  owner: string;
  repository: string;
  total_bytes: number;
  languages: LanguageSlice[];
  other_bytes: number;
  truncated: boolean;
  cached: boolean;
}

export type DependencyRisk =
  | 'unpinned'
  | 'floating_version'
  | 'git_source'
  | 'local_path'
  | 'known_risk'
  | 'missing_version';

export interface Dependency {
  name: string;
  version: string | null;
  ecosystem: string;
  manifest: string;
  scope: string;
  risks: DependencyRisk[];
  pinned: boolean;
}

export interface DependencyManifest {
  path: string;
  ecosystem: string;
  found: boolean;
  reason: string | null;
}

export interface DependencyReport {
  owner: string;
  repository: string;
  manifests: DependencyManifest[];
  dependencies: Dependency[];
  total: number;
  direct_count: number;
  flagged_count: number;
  ecosystems: string[];
  cached: boolean;
}

export interface ReadmeSection {
  heading: string;
  level: number;
  line: number;
  preview: string;
}

export interface ReadmeCodeSample {
  language: string | null;
  lines: number;
}

export interface ReadmeIntelligence {
  owner: string;
  repository: string;
  path: string | null;
  available: boolean;
  reason: string | null;
  raw: string | null;
  size_bytes: number;
  line_count: number;
  word_count: number;
  sections: ReadmeSection[];
  has_badges: boolean;
  badge_count: number;
  has_toc: boolean;
  has_install_section: boolean;
  has_usage_section: boolean;
  has_license_section: boolean;
  code_blocks: number;
  languages_used: string[];
  images: number;
  links: number;
  cached: boolean;
}

export type RepositoryTreeEntryType = 'file' | 'directory' | 'submodule' | 'commit';

export interface RepositoryTreeEntry {
  path: string;
  name: string;
  type: RepositoryTreeEntryType;
  size: number;
  depth: number;
}

export interface RepositoryTree {
  owner: string;
  repository: string;
  ref: string | null;
  truncated: boolean;
  total_files: number;
  total_directories: number;
  total_bytes: number;
  entries: RepositoryTreeEntry[];
  cached: boolean;
}

export interface RepositoryFileContent {
  path: string;
  content: string;
  size: number;
  truncated: boolean;
  language: string | null;
  binary: boolean;
}

export interface RepositoryDashboard {
  owner: string;
  repository: string;
  profile: RepositoryProfile;
  health: RepositoryHealth;
  languages: LanguageBreakdown;
  dependencies: DependencyReport;
  readme: ReadmeIntelligence;
  generated_at: string;
  cached: boolean;
}

/** Entry returned by the cached-repository listing. */
export interface CachedRepositoryRef {
  owner: string;
  repository: string;
  full_name: string;
  cached_at: string | null;
}

export interface CacheInvalidationResult {
  owner: string;
  repository: string;
  invalidated: number;
}

// ---------------------------------------------------------------------------
// Sprint 3: AI pull request review (backend schema v2)
//
// Kept separate from the Phase 1-4 `Finding` / `ReviewResponse` above, which
// remain in use by the legacy review route, the dashboard and insights. See
// backend/app/schemas/ai_review.py for the rationale.
// ---------------------------------------------------------------------------

export type AiReviewSeverity = Severity;
export type AiReviewCategory =
  | 'bugs'
  | 'security'
  | 'performance'
  | 'code_quality'
  | 'maintainability'
  | 'testing';
export type AiReviewFileStatus = 'added' | 'modified' | 'deleted' | 'renamed' | 'binary';
export type AiReviewStatus = 'queued' | 'in_progress' | 'complete' | 'partial' | 'failed';
export type AiReviewAiStatus = 'complete' | 'unavailable' | 'malformed' | 'skipped';
export type AiReviewSource = 'ai' | 'heuristic' | 'combined';

/** Sentinels and vocabulary shared with the backend. */
export const AI_REVIEW_CATEGORIES: AiReviewCategory[] = [
  'bugs',
  'security',
  'performance',
  'code_quality',
  'maintainability',
  'testing',
];

export const AI_REVIEW_SEVERITIES: AiReviewSeverity[] = ['critical', 'high', 'medium', 'low', 'info'];

/** A finding that applies to a whole file rather than a specific line. */
export const AI_REVIEW_FILE_LEVEL_LINE = 0;

export interface AiReviewSuggestion {
  suggestion_id: string;
  finding_id: string | null;
  file: string | null;
  title: string;
  description: string;
  original_code: string | null;
  suggested_code: string | null;
  rationale: string | null;
}

export interface AiReviewFinding {
  finding_id: string;
  file: string;
  /** `0` means file-level: there is no single line to navigate to. */
  line: number;
  severity: AiReviewSeverity;
  category: AiReviewCategory;
  confidence: number;
  title: string;
  description: string;
  suggestion: string;
  original_code: string | null;
  suggested_code: string | null;
  source: AiReviewSource;
  rule_id: string | null;
}

export interface AiReviewFile {
  path: string;
  previous_path: string | null;
  status: AiReviewFileStatus;
  language: string | null;
  additions: number;
  deletions: number;
  changes: number;
  is_binary: boolean;
  patch: string | null;
  finding_ids: string[];
}

export interface AiAssessmentMetric {
  dimension: string;
  label: string;
  score: number;
  finding_count: number;
}

export interface AiReviewSummary {
  assessment_label: string;
  assessment_disclaimer: string;
  assessment_score: number;
  assessment_severity: AiReviewSeverity;
  metrics: AiAssessmentMetric[];
  total_findings: number;
  severity_counts: Record<string, number>;
  category_counts: Record<string, number>;
  files_reviewed: number;
  lines_added: number;
  lines_deleted: number;
  highest_severity: AiReviewSeverity | null;
}

export interface AiReview {
  review_id: string;
  schema_version: number;
  status: AiReviewStatus;
  /** Outcome of the model leg specifically, independent of `status`. */
  ai_status: AiReviewAiStatus;
  owner: string;
  repository: string;
  pull_request_number: number;
  pull_request_title: string | null;
  commit_sha: string | null;
  provider: ScmProvider;
  summary: AiReviewSummary;
  files: AiReviewFile[];
  findings: AiReviewFinding[];
  suggestions: AiReviewSuggestion[];
  error: string | null;
  duration_ms: number | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface CreateAiReviewRequest {
  owner: string;
  repository: string;
  pull_request_number: number;
  provider?: ScmProvider;
}

export interface AiReviewFindingsResponse {
  review_id: string;
  total: number;
  findings: AiReviewFinding[];
}

export interface AiReviewFindingsQuery {
  severity?: AiReviewSeverity;
  category?: AiReviewCategory;
  file?: string;
  sort?: 'severity' | 'confidence' | 'category' | 'file' | 'line';
}
// ---------------------------------------------------------------------------
// Security Intelligence Engine (Sprint 4)
//
// Mirrors app/schemas/security.py. The severities are shared with the review
// contract; the categories and scanners are security-specific, and they are
// separate unions rather than a widened `Category` so a security finding can
// never be assigned a review category.
// ---------------------------------------------------------------------------

export type SecuritySeverity = Severity;

export type SecurityCategory =
  | 'secrets'
  | 'injection'
  | 'code_execution'
  | 'crypto'
  | 'path_traversal'
  | 'deserialization'
  | 'authentication'
  | 'dependencies'
  | 'misconfiguration';

export type SecurityScanner = 'secret' | 'code' | 'dependency';

export type SecurityScanStatus = 'pending' | 'running' | 'complete' | 'failed';

/** Line 0 is the whole-file sentinel, matching the review contract. */
export const SECURITY_FILE_LEVEL_LINE = 0;

export const SECURITY_SEVERITIES: SecuritySeverity[] = [
  'critical',
  'high',
  'medium',
  'low',
  'info',
];

export const SECURITY_CATEGORIES: SecurityCategory[] = [
  'secrets',
  'injection',
  'code_execution',
  'crypto',
  'path_traversal',
  'deserialization',
  'authentication',
  'dependencies',
  'misconfiguration',
];

export const SECURITY_SCANNERS: SecurityScanner[] = ['secret', 'code', 'dependency'];

export interface SecurityFinding {
  finding_id: string;
  repository_id: string;
  file: string;
  line: number;
  column: number | null;
  category: SecurityCategory;
  severity: SecuritySeverity;
  confidence: number;
  title: string;
  description: string;
  remediation: string;
  scanner: SecurityScanner;
  fingerprint: string;
  created_at: string;
}

export interface SecuritySeverityCounts {
  critical: number;
  high: number;
  medium: number;
  low: number;
  info: number;
}

export interface SecurityRiskSummary {
  total_findings: number;
  severity_counts: SecuritySeverityCounts;
  /** Deterministic penalty: critical 8, high 3, medium 1. */
  weighted_risk: number;
  /** 0-100, derived from the finding set alone. Never model-produced. */
  posture_score: number;
  category_distribution: Record<string, number>;
  scanner_distribution: Record<string, number>;
  files_scanned: number;
  files_skipped: number;
  findings_by_file: Record<string, number>;
  dependencies_analyzed: number;
}

export interface SecurityScan {
  scan_id: string;
  schema_version: number;
  status: SecurityScanStatus;
  repository_id: string;
  owner: string;
  repository: string;
  full_name: string;
  provider: ScmProvider;
  ref: string | null;
  commit_sha: string | null;
  summary: SecurityRiskSummary;
  findings: SecurityFinding[];
  /** Per-file degradation notes; a scanner that could not read a file. */
  errors: string[];
  duration_ms: number | null;
  scanned_at: string | null;
  /** Which advisory source contributed known-CVE findings; "none" means none. */
  vulnerability_source: string;
}

export interface SecurityPosture {
  repository_id: string;
  owner: string;
  repository: string;
  full_name: string;
  has_scan: boolean;
  scan_id: string | null;
  scanned_at: string | null;
  summary: SecurityRiskSummary;
  methodology: string;
}

export interface SecurityFindingsResponse {
  scan_id: string;
  total: number;
  findings: SecurityFinding[];
}

export interface SecurityFindingsQuery {
  severity?: SecuritySeverity;
  category?: SecurityCategory;
  scanner?: SecurityScanner;
  file?: string;
  limit?: number;
  offset?: number;
}

export interface CreateSecurityScanRequest {
  owner: string;
  repository: string;
  provider?: ScmProvider;
  ref?: string | null;
  max_files?: number;
}

/**
 * Optional model prose for one finding. Display-only: the model cannot set a
 * severity, a score, or whether the finding exists.
 */
export interface SecurityExplanation {
  finding_id: string;
  explanation: string;
  impact: string;
  remediation: string;
  model: string | null;
  /** Set when no prose is attached, so the UI can say why. */
  unavailable_reason: string | null;
}

export interface SecurityScannerRule {
  rule_id: string;
  title: string;
  severity: SecuritySeverity;
  category: SecurityCategory;
}

export interface SecurityScannerCatalogue {
  secret: SecurityScannerRule[];
  code: SecurityScannerRule[];
  dependency: SecurityScannerRule[];
  severities: SecuritySeverity[];
  categories: SecurityCategory[];
  scanners: SecurityScanner[];
}

/**
 * Architecture Intelligence
 *
 * Mirrors the backend contract. `evidence` is always present on a classified
 * node so the UI can show *why* a module was labelled, rather than asking the
 * reviewer to trust the label.
 */

export type ArchitectureLanguage = 'python' | 'javascript' | 'typescript';

/**
 * `module` is the fallback for a source file that matched no stronger rule â€” a
 * real observation ("no detected role"), not a placeholder.
 */
export type ArchitectureNodeKind = 'module' | 'service' | 'route' | 'controller' | 'database' | 'external';

export type ArchitectureEdgeKind = 'internal' | 'external';

/**
 * Structural defects measured from imports and file size. Each is a
 * deterministic measurement, not a judgement.
 */
export type ArchitectureIssueKind =
  | 'circular_dependency'
  | 'high_coupling'
  | 'god_module'
  | 'oversized_module'
  | 'orphan_module'
  | 'external_hotspot';

/**
 * Deliberately only `info`/`warning`. These are measurements, and putting them on
 * the same scale as security findings would imply a precision the analysis does
 * not have.
 */
export type ArchitectureIssueSeverity = 'info' | 'warning';

export interface ArchitectureNode {
  id: string;
  name: string;
  /** Repository-relative path. Empty for external packages. */
  path: string;
  language?: ArchitectureLanguage | null;
  kind: ArchitectureNodeKind;
  /** Why this node was classified as it was. Empty when `kind` is `module`. */
  evidence: string;
  /** `null` when the file could not be read, which differs from a read of zero lines. */
  line_count?: number | null;
  fan_out: number;
  fan_in: number;
  /** False when the file failed to parse. The node is still listed. */
  parsed: boolean;
}

export interface ArchitectureEdge {
  source: string;
  target: string;
  kind: ArchitectureEdgeKind;
  /** The import statement as written, for display only. */
  reference: string;
  resolved: boolean;
}

export interface ArchitectureModule {
  id: string;
  name: string;
  path: string;
  language?: ArchitectureLanguage | null;
  kind: ArchitectureNodeKind;
  line_count?: number | null;
  fan_in: number;
  fan_out: number;
  /** External packages this module imports. */
  dependencies: string[];
}

export interface ArchitectureIssue {
  kind: ArchitectureIssueKind;
  severity: ArchitectureIssueSeverity;
  title: string;
  /** The numbers behind the claim, so it can be checked. */
  detail: string;
  nodes: string[];
}

export interface ArchitectureSummary {
  total_modules: number;
  total_edges: number;
  internal_edges: number;
  external_edges: number;
  language_distribution: Record<string, number>;
  kind_distribution: Record<string, number>;
  external_packages: number;
  /** Imports that did not resolve, so a partial analysis cannot read as complete. */
  unresolved_imports: number;
  /** `null` when detection did not run to complete, which differs from zero found. */
  cycles?: number | null;
  cycle_groups?: number | null;
  most_depended_on: string[];
  most_dependent: string[];
  total_lines: number;
  /** States exactly what was and was not analysed. */
  methodology: string;
}

export interface ArchitectureGraph {
  repository_id: string;
  owner: string;
  repository: string;
  full_name: string;
  provider: string;
  ref?: string | null;
  commit_sha?: string | null;
  analyzed_at: string;
  duration_ms: number;
  nodes: ArchitectureNode[];
  edges: ArchitectureEdge[];
  modules: ArchitectureModule[];
  issues: ArchitectureIssue[];
  summary: ArchitectureSummary;
  errors: string[];
  /** True when file selection hit its cap and the graph is partial. */
  truncated: boolean;
}

/**
 * Documentation Intelligence
 *
 * Mirrors the backend contract. Everything here is measured from the
 * repository's own files: no model is involved, so every gap carries the
 * `evidence` that produced it and the reviewer can check it.
 */

export type DocumentationAssetKind =
  | 'readme'
  | 'changelog'
  | 'contributing'
  | 'license'
  | 'security_policy'
  | 'code_of_conduct'
  | 'api_reference'
  | 'adr'
  | 'guide'
  | 'documentation'
  | 'other';

export type DocumentationGapKind =
  | 'missing_readme'
  | 'missing_install_section'
  | 'missing_usage_section'
  | 'missing_license'
  | 'missing_changelog'
  | 'missing_contributing'
  | 'missing_security_policy'
  | 'thin_readme'
  | 'no_docs_directory'
  | 'broken_relative_link'
  | 'low_docstring_coverage'
  | 'undocumented_public_api';

export type DocumentationLanguage = 'markdown' | 'rst' | 'asciidoc' | 'text' | 'python' | 'javascript' | 'typescript';

export type DocumentationSourceLanguage = 'python' | 'javascript' | 'typescript';

/**
 * Only `info`/`warning`. Absent documentation does not break a build, so it is
 * never placed on the severity scale used by security findings.
 */
export type DocumentationGapSeverity = 'info' | 'warning';

export interface DocumentationHeading {
  level: number;
  text: string;
  /** 1-based line in the source file. */
  line: number;
}

export interface DocumentationLink {
  text: string;
  target: string;
  /** True for a repository-relative target. */
  internal: boolean;
  /** `null` for an external link: never fetched, so never judged. */
  resolved: boolean | null;
}

export interface DocumentationAsset {
  path: string;
  kind: DocumentationAssetKind;
  language?: DocumentationLanguage | null;
  size_bytes: number;
  line_count: number;
  /** Prose words outside fenced code blocks. */
  word_count: number;
  headings: DocumentationHeading[];
  has_toc: boolean;
  has_install: boolean;
  has_usage: boolean;
  has_examples: boolean;
  has_license: boolean;
  has_contributing: boolean;
  code_blocks: number;
  images: number;
  badges: number;
  links: DocumentationLink[];
}

export interface DocumentationCoverage {
  path: string;
  language: DocumentationSourceLanguage;
  public_symbols: number;
  documented_symbols: number;
  /** Ratio of public symbols carrying a docstring. */
  coverage: number;
  /** Names of undocumented public symbols, for display only. */
  undocumented: string[];
}

export interface DocumentationGap {
  kind: DocumentationGapKind;
  severity: DocumentationGapSeverity;
  title: string;
  detail: string;
  /** The observation that produced this gap, so it can be checked. */
  evidence: string;
  paths: string[];
}

export interface DocumentationSummary {
  total_assets: number;
  documentation_files: number;
  source_files: number;
  /** Documentation files as a share of documentation + source files. */
  documentation_ratio: number;
  readme_present: boolean;
  readme_word_count: number;
  readme_sections: number;
  /** Canonical files not found, in canonical order. */
  missing_canonical: string[];
  total_links: number;
  broken_links: number;
  public_symbols: number;
  documented_symbols: number;
  docstring_coverage: number;
  /** 0â€“100, built from published fixed deductions. Not a model judgement. */
  coverage_score: number;
  gap_count: number;
  methodology: string;
}

export interface DocumentationIntelligence {
  repository_id: string;
  owner: string;
  repository: string;
  full_name: string;
  provider: string;
  ref?: string | null;
  commit_sha?: string | null;
  analyzed_at: string;
  duration_ms: number;
  assets: DocumentationAsset[];
  coverage: DocumentationCoverage[];
  gaps: DocumentationGap[];
  summary: DocumentationSummary;
  errors: string[];
  /** True when file selection hit its cap and the report is partial. */
  truncated: boolean;
}

/*
 * Test generation (Phase 4).
 *
 * Mirrors `backend/app/schemas/test_generation.py`. `deterministic` content is
 * generated locally and holds no model output; `gemini` content is a preview
 * that has never been executed.
 */

export type TestFramework = 'pytest' | 'unittest' | 'jest' | 'vitest' | 'unknown';

export type TestLanguage = 'python' | 'javascript' | 'typescript';

export type SymbolKind = 'function' | 'method' | 'class';

/** Why a symbol was selected. Each is an observation about test files. */
export type TargetReason =
  | 'no_test_reference'
  | 'reference_outside_test_paths'
  | 'no_test_suite'
  | 'tested_only_by_name_match';

export type GenerationSource = 'gemini' | 'deterministic';

export type ValidationCode =
  | 'syntax_error'
  | 'forbidden_import'
  | 'forbidden_call'
  | 'secret_redacted'
  | 'empty'
  | 'too_long'
  | 'too_many_tests'
  | 'placeholder'
  | 'no_test_detected';

export interface TestTarget {
  name: string;
  qualified_name: string;
  kind: SymbolKind;
  file: string;
  line: number;
  signature: string;
  reason: TargetReason;
  /** The observation behind the selection, so a reader can check it. */
  evidence: string;
  priority: number;
  test_names: string[];
}

export interface ValidationIssue {
  /** Stable, because the frontend switches on it. */
  code: ValidationCode;
  detail: string;
  line?: number | null;
}

export interface GeneratedTestFile {
  /** The path this file would take. Nothing is ever written here. */
  path: string;
  language: TestLanguage;
  framework: TestFramework;
  content: string;
  source: GenerationSource;
  model?: string | null;
  test_names: string[];
  covers: string[];
  /** False when screening flagged something a reviewer must see first. */
  usable: boolean;
  validation: ValidationIssue[];
}

export interface TestGenerationSummary {
  framework: TestFramework;
  source_files_scanned: number;
  public_symbols: number;
  existing_test_files: number;
  untested_symbols: number;
  targets: number;
  generated_files: number;
  generated_tests: number;
  rejected_files: number;
  methodology: string;
}

export interface TestGeneration {
  repository_id: string;
  owner: string;
  repository: string;
  full_name: string;
  provider: string;
  ref?: string | null;
  commit_sha?: string | null;
  generated_at: string;
  duration_ms: number;
  framework: TestFramework;
  test_directories: string[];
  existing_test_files: string[];
  targets: TestTarget[];
  files: GeneratedTestFile[];
  summary: TestGenerationSummary;
  model?: string | null;
  /** Set when no model was reachable, so the UI can say the files are scaffolds. */
  unavailable_reason?: string | null;
  errors: string[];
  /** True when a cap was hit, so the report is a preview of part of the tree. */
  truncated: boolean;
}
// ---------------------------------------------------------------------------
// Dependency & supply chain intelligence
// ---------------------------------------------------------------------------

/** How a file participates in dependency resolution. */
export type ManifestRole = 'manifest' | 'lockfile';

/** Where a dependency came from in the dependency graph. */
export type DependencyOrigin = 'direct' | 'transitive' | 'unknown';

/**
 * Coarse licence posture, mirroring the backend's classification.
 *
 * A classification of the declared expression only, never legal advice.
 * `unknown` means the expression could not be mapped to a known set - it does
 * not mean "probably permissive".
 */
export type LicenseCategory =
  | 'public_domain'
  | 'permissive'
  | 'weak_copyleft'
  | 'strong_copyleft'
  | 'proprietary'
  | 'unknown';

export const LICENSE_CATEGORIES: LicenseCategory[] = [
  'public_domain',
  'permissive',
  'weak_copyleft',
  'strong_copyleft',
  'proprietary',
  'unknown',
];

export type SupplyChainSeverity = 'critical' | 'high' | 'medium' | 'low' | 'info';

/** Score bands, worst first, matching the backend thresholds. */
export type SupplyChainScoreBand = 'critical' | 'weak' | 'fair' | 'strong';

export interface SupplyChainManifest {
  path: string;
  ecosystem: string;
  role: ManifestRole;
  found: boolean;
  dependency_count: number;
  direct_count: number;
  transitive_count: number;
  parse_failed: boolean;
  note?: string | null;
}

export interface SupplyChainDependency {
  name: string;
  version?: string | null;
  ecosystem: string;
  manifest: string;
  scope: string;
  origin: DependencyOrigin;
  pinned: boolean;
  risks: string[];
  license_expression?: string | null;
  license_category: LicenseCategory;
  line: number;
}

export interface LicenseUse {
  expression: string;
  category: LicenseCategory;
  dependency_count: number;
  direct_dependency_count: number;
  ecosystems: string[];
  dependencies: string[];
}

export interface SupplyChainIssue {
  code: string;
  severity: SupplyChainSeverity;
  title: string;
  detail: string;
  remediation: string;
  evidence: string[];
  affected_count: number;
}

export interface SupplyChainSummary {
  manifest_count: number;
  lockfile_count: number;
  total_dependencies: number;
  direct_dependencies: number;
  transitive_dependencies: number;
  unknown_origin_dependencies: number;
  pinned_dependencies: number;
  unpinned_dependencies: number;
  pinned_ratio: number;
  licensed_dependencies: number;
  unknown_license_dependencies: number;
  declared_license_dependencies: number;
  license_coverage_ratio: number;
  declared_license?: string | null;
  license_categories: Record<string, number>;
  ecosystems: string[];
  manifests_with_transitives: string[];
  hygiene_score: number;
  score_band: SupplyChainScoreBand;
  /** Every deduction applied to the score, so a reader can audit it. */
  score_notes: string[];
  issue_count: number;
  issues_by_severity: Record<string, number>;
  issues_by_code: Record<string, number>;
}

export interface SupplyChainReport {
  repository_id: string;
  owner: string;
  repository: string;
  full_name: string;
  provider: string;
  ref?: string | null;
  commit_sha?: string | null;
  analyzed_at: string;
  duration_ms: number;
  manifests: SupplyChainManifest[];
  dependencies: SupplyChainDependency[];
  licenses: LicenseUse[];
  issues: SupplyChainIssue[];
  summary: SupplyChainSummary;
  errors: string[];
  truncated: boolean;
  cached: boolean;
}

// ---------------------------------------------------------------------------
// AI Developer Assistant
// ---------------------------------------------------------------------------

export type AssistantMode =
  | 'explain_code'
  | 'explain_finding'
  | 'explain_architecture'
  | 'explain_repository'
  | 'explain_ai_review'
  | 'explain_security'
  | 'explain_dependency'
  | 'debug_error'
  | 'refactor_code'
  | 'generate_tests'
  | 'explain_documentation'
  | 'explain_workflow';

export type AssistantContextType =
  | 'repository'
  | 'file'
  | 'code'
  | 'architecture_node'
  | 'security_finding'
  | 'ai_review_finding'
  | 'dependency'
  | 'workflow_event'
  | 'documentation'
  | 'test_result';

export type AssistantCodeActionType = 'explain' | 'refactor' | 'generate_tests' | 'suggest_fix';

export interface AssistantContext {
  context_type: AssistantContextType;
  repository_id: string;
  owner: string;
  repository: string;
  ref?: string | null;
  commit_sha?: string | null;
  file_path?: string | null;
  file_content?: string | null;
  file_language?: string | null;
  code_snippet?: string | null;
  code_start_line?: number | null;
  code_end_line?: number | null;
  finding_id?: string | null;
  finding_title?: string | null;
  finding_description?: string | null;
  finding_severity?: string | null;
  finding_category?: string | null;
  finding_file?: string | null;
  finding_line?: number | null;
  finding_code?: string | null;
  finding_recommendation?: string | null;
  architecture_node_id?: string | null;
  architecture_node_name?: string | null;
  architecture_node_kind?: string | null;
  architecture_node_path?: string | null;
  architecture_evidence?: string | null;
  dependency_name?: string | null;
  dependency_version?: string | null;
  dependency_ecosystem?: string | null;
  dependency_risks?: string[];
  dependency_license?: string | null;
  workflow_event_id?: string | null;
  workflow_event_type?: string | null;
  workflow_event_status?: string | null;
  workflow_event_error?: string | null;
  documentation_type?: string | null;
  documentation_title?: string | null;
  documentation_content?: string | null;
  test_file_path?: string | null;
  test_content?: string | null;
  test_validation_status?: string | null;
  test_execution_status?: string | null;
  metadata?: Record<string, unknown>;
}

export interface AssistantMessage {
  message_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  created_at: string;
  mode?: AssistantMode | null;
  context_type?: AssistantContextType | null;
  cached: boolean;
  model?: string | null;
  warnings?: string[];
}

export interface AssistantChatRequest {
  message: string;
  mode: AssistantMode;
  context?: AssistantContext | null;
  conversation_id?: string | null;
  refresh?: boolean;
}

export interface AssistantChatResponse {
  message: AssistantMessage;
  conversation_id: string;
  cached: boolean;
  model?: string | null;
  warnings?: string[];
}

export interface AssistantCodeActionRequest {
  action_type: AssistantCodeActionType;
  context: AssistantContext;
  instruction?: string | null;
  conversation_id?: string | null;
}

export interface AssistantCodeActionResponse {
  action_type: AssistantCodeActionType;
  original_code: string;
  generated_code: string;
  explanation: string;
  diff: string;
  model?: string | null;
  warnings?: string[];
}

export interface AssistantConversation {
  conversation_id: string;
  owner: string;
  repository: string;
  messages: AssistantMessage[];
  context?: AssistantContext | null;
  created_at: string;
  updated_at: string;
}

export const ASSISTANT_MODE_LABELS: Record<AssistantMode, string> = {
  explain_code: 'Explain Code',
  explain_finding: 'Explain Finding',
  explain_architecture: 'Explain Architecture',
  explain_repository: 'Explain Repository',
  explain_ai_review: 'Explain AI Review',
  explain_security: 'Explain Security Issue',
  explain_dependency: 'Explain Dependency Risk',
  debug_error: 'Debug Error',
  refactor_code: 'Refactor Code',
  generate_tests: 'Generate Tests',
  explain_documentation: 'Explain Documentation',
  explain_workflow: 'Explain Workflow Failure',
};