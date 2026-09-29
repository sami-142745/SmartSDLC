import { http } from './client';
import type {
  CreateSecurityScanRequest,
  SecurityExplanation,
  SecurityFindingsQuery,
  SecurityFindingsResponse,
  SecurityPosture,
  SecurityScan,
  SecurityScannerCatalogue,
  ScmProvider,
} from '../types';

const BASE = '/security';

function repoPostureBase(owner: string, repository: string): string {
  return `${BASE}/repositories/${encodeURIComponent(owner)}/${encodeURIComponent(repository)}/posture`;
}

function findingsParams(query: SecurityFindingsQuery): Record<string, string | number> {
  const params: Record<string, string | number> = {};
  if (query.severity) params.severity = query.severity;
  if (query.category) params.category = query.category;
  if (query.scanner) params.scanner = query.scanner;
  if (query.file) params.file = query.file;
  if (query.limit != null) params.limit = query.limit;
  if (query.offset != null) params.offset = query.offset;
  return params;
}

/**
 * The rule catalogues the engine actually runs. Fetched so the UI can state its
 * coverage without duplicating a rule list on the frontend.
 */
export async function getSecurityScanners(): Promise<SecurityScannerCatalogue> {
  const { data } = await http.get<SecurityScannerCatalogue>(`${BASE}/scanners`);
  return data;
}

/**
 * Run a repository scan. Synchronous on the server: the response is the
 * completed scan, with its findings and deterministic risk summary.
 */
export async function createSecurityScan(
  payload: CreateSecurityScanRequest,
  options: { provider?: ScmProvider } = {},
): Promise<SecurityScan> {
  const body: CreateSecurityScanRequest = {
    ...payload,
    provider: options.provider ?? payload.provider ?? 'github',
  };
  const { data } = await http.post<SecurityScan>(`${BASE}/scans`, body);
  return data;
}

/** Recent scans for the signed-in user, newest first, without findings. */
export async function getSecurityScans(
  limit = 20,
  offset = 0,
): Promise<SecurityScan[]> {
  const { data } = await http.get<SecurityScan[]>(`${BASE}/scans`, {
    params: { limit, offset },
  });
  return data;
}

/**
 * Read one scan. Findings are included by default; pass `includeFindings: false`
 * for an overview read that does not need them.
 */
export async function getSecurityScan(
  scanId: string,
  options: { includeFindings?: boolean } = {},
): Promise<SecurityScan> {
  const { data } = await http.get<SecurityScan>(`${BASE}/scans/${encodeURIComponent(scanId)}`, {
    params: { include_findings: options.includeFindings ?? true },
  });
  return data;
}

/**
 * Read a filtered page of findings. An unknown filter value is a 422 rather than
 * an empty list, so a misspelt query cannot read as a clean repository.
 */
export async function getSecurityFindings(
  scanId: string,
  query: SecurityFindingsQuery = {},
): Promise<SecurityFindingsResponse> {
  const { data } = await http.get<SecurityFindingsResponse>(
    `${BASE}/scans/${encodeURIComponent(scanId)}/findings`,
    { params: findingsParams(query) },
  );
  return data;
}

/**
 * Posture for one repository. A repository that has never been scanned resolves
 * with `has_scan: false` rather than a 404 — "not scanned yet" is a state the
 * page renders, not an error.
 */
export async function getRepositoryPosture(
  owner: string,
  repository: string,
): Promise<SecurityPosture> {
  const { data } = await http.get<SecurityPosture>(repoPostureBase(owner, repository));
  return data;
}

/**
 * Optional model prose for one finding. Degrades to an empty explanation with
 * the scanner's own remediation rather than failing, so the endpoint is safe to
 * call on demand.
 */
export async function getSecurityFindingExplanation(
  findingId: string,
): Promise<SecurityExplanation> {
  const { data } = await http.get<SecurityExplanation>(
    `${BASE}/findings/${encodeURIComponent(findingId)}/explanation`,
  );
  return data;
}
