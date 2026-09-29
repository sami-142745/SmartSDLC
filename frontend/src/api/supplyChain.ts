import { http } from './client';
import type {
  LicenseCategory,
  LicenseUse,
  ScmProvider,
  SupplyChainDependency,
  SupplyChainIssue,
  SupplyChainReport,
  SupplyChainSeverity,
} from '../types';

const BASE = '/supply-chain';

function repoBase(owner: string, repository: string): string {
  return `${BASE}/repositories/${encodeURIComponent(owner)}/${encodeURIComponent(repository)}`;
}

export interface SupplyChainParams {
  provider?: ScmProvider;
  ref?: string;
  refresh?: boolean;
  maxDependencies?: number;
}

function repoParams({
  provider,
  ref,
  refresh,
  maxDependencies,
}: SupplyChainParams): Record<string, string | number | boolean> {
  const params: Record<string, string | number | boolean> = {};
  // GitLab is sent only when explicitly selected so the backend keeps defaulting to GitHub.
  if (provider === 'gitlab') params.provider = 'gitlab';
  if (ref) params.ref = ref;
  if (refresh) params.refresh = true;
  // The backend query parameter is snake_case, matching the rest of the API.
  if (maxDependencies !== undefined) params.max_dependencies = maxDependencies;
  return params;
}

/**
 * Dependency inventory, licence rollup and supply-chain issues for one repository.
 *
 * The backend caches this, so a second call is cheap unless `refresh` is set.
 */
export async function getSupplyChain(
  owner: string,
  repository: string,
  options: SupplyChainParams = {},
): Promise<SupplyChainReport> {
  const { data } = await http.get<SupplyChainReport>(repoBase(owner, repository), {
    params: repoParams(options),
  });
  return data;
}

/** Issues at or above a severity, in the backend's worst-first order. */
export function issuesAtLeast(
  report: SupplyChainReport,
  severity: SupplyChainSeverity,
): SupplyChainIssue[] {
  const order: SupplyChainSeverity[] = ['critical', 'high', 'medium', 'low', 'info'];
  const cutoff = order.indexOf(severity);
  if (cutoff < 0) return [];
  return report.issues.filter((issue) => order.indexOf(issue.severity) <= cutoff);
}

/** Issues worth acting on, i.e. high and critical. */
export function blockingIssues(report: SupplyChainReport): SupplyChainIssue[] {
  return issuesAtLeast(report, 'high');
}

/** The copyleft, proprietary and undeclared-licence issues, which need counsel. */
export function licenceObligations(report: SupplyChainReport): SupplyChainIssue[] {
  return report.issues.filter(
    (issue) =>
      issue.code === 'strong_copyleft' ||
      issue.code === 'proprietary_license' ||
      issue.code === 'undeclared_license' ||
      issue.code === 'unknown_license',
  );
}

/** The inventory rows that carry a given risk label, e.g. `git_source`. */
export function dependenciesWithRisk(
  dependencies: SupplyChainDependency[],
  risk: string,
): SupplyChainDependency[] {
  return dependencies.filter((dependency) => dependency.risks.includes(risk));
}

/** Inventory rows the project named itself, as opposed to inherited ones. */
export function directDependencies(report: SupplyChainReport): SupplyChainDependency[] {
  return report.dependencies.filter((dependency) => dependency.origin === 'direct');
}

/** Inventory rows that arrived through another package. */
export function transitiveDependencies(report: SupplyChainReport): SupplyChainDependency[] {
  return report.dependencies.filter((dependency) => dependency.origin === 'transitive');
}

/** Licence rollup entries in a given category. */
export function licensesInCategory(
  licenses: LicenseUse[],
  category: LicenseCategory,
): LicenseUse[] {
  return licenses.filter((entry) => entry.category === category);
}

/** Share of the inventory that a category accounts for, 0 when there is none. */
export function licenseShare(report: SupplyChainReport, category: LicenseCategory): number {
  const total = report.summary.total_dependencies;
  if (total === 0) return 0;
  return (report.summary.license_categories[category] ?? 0) / total;
}

/** True when the project cannot reproduce an install from the repository alone. */
export function isReproducible(report: SupplyChainReport): boolean {
  return report.summary.manifest_count > 0 && report.summary.lockfile_count > 0;
}

/** A 0-1 ratio rendered as a whole percentage, guarding against an empty set. */
export function ratioPercent(ratio: number): number {
  if (!Number.isFinite(ratio)) return 0;
  return Math.round(Math.min(1, Math.max(0, ratio)) * 100);
}

/** Human-readable label for a licence category. */
export function licenseCategoryLabel(category: LicenseCategory): string {
  switch (category) {
    case 'public_domain':
      return 'Public domain';
    case 'permissive':
      return 'Permissive';
    case 'weak_copyleft':
      return 'Weak copyleft';
    case 'strong_copyleft':
      return 'Strong copyleft';
    case 'proprietary':
      return 'Proprietary / custom';
    default:
      return 'Unknown';
  }
}
