import { http } from './client';
import type {
  DocumentationAsset,
  DocumentationAssetKind,
  DocumentationGap,
  DocumentationGapKind,
  DocumentationIntelligence,
  ScmProvider,
} from '../types';

const BASE = '/documentation-intelligence';

function repoBase(owner: string, repository: string): string {
  return `${BASE}/repositories/${encodeURIComponent(owner)}/${encodeURIComponent(repository)}`;
}

export interface DocumentationParams {
  provider?: ScmProvider;
  ref?: string;
  refresh?: boolean;
  maxFiles?: number;
}

function repoParams({ provider, ref, refresh, maxFiles }: DocumentationParams): Record<string, string | number | boolean> {
  const params: Record<string, string | number | boolean> = {};
  // GitLab is sent only when explicitly selected so the backend keeps defaulting to GitHub.
  if (provider === 'gitlab') params.provider = 'gitlab';
  if (ref) params.ref = ref;
  if (refresh) params.refresh = true;
  // The backend query parameter is snake_case, matching the rest of the API.
  if (maxFiles !== undefined) params.max_files = maxFiles;
  return params;
}

/**
 * Documentation assets, docstring coverage, gaps and summary for one repository.
 *
 * The backend caches this, so a second call is cheap unless `refresh` is set.
 */
export async function getDocumentationIntelligence(
  owner: string,
  repository: string,
  options: DocumentationParams = {},
): Promise<DocumentationIntelligence> {
  const { data } = await http.get<DocumentationIntelligence>(repoBase(owner, repository), {
    params: repoParams(options),
  });
  return data;
}

/** Groups gaps by kind, preserving the backend's deterministic ordering. */
export function gapsByKind(gaps: DocumentationGap[]): Record<DocumentationGapKind, DocumentationGap[]> {
  const grouped = {} as Record<DocumentationGapKind, DocumentationGap[]>;
  for (const gap of gaps) {
    (grouped[gap.kind] ??= []).push(gap);
  }
  return grouped;
}

/** Gaps worth acting on, i.e. everything the backend marked `warning`. */
export function actionableGaps(report: DocumentationIntelligence): DocumentationGap[] {
  return report.gaps.filter((gap) => gap.severity === 'warning');
}

/**
 * Internal links that do not resolve to a file in the tree.
 *
 * External links carry `resolved === null` because they are never fetched, so
 * they can never be reported broken.
 */
export function brokenLinks(assets: DocumentationAsset[]): { path: string; target: string }[] {
  const broken: { path: string; target: string }[] = [];
  for (const asset of assets) {
    for (const link of asset.links) {
      if (link.internal && link.resolved === false) broken.push({ path: asset.path, target: link.target });
    }
  }
  return broken;
}

/** Documentation assets of one kind, in the backend's sorted order. */
export function assetsByKind(assets: DocumentationAsset[], kind: DocumentationAssetKind): DocumentationAsset[] {
  return assets.filter((asset) => asset.kind === kind);
}

/** Assets with the most missing docstring coverage, worst first. */
export function leastDocumented(report: DocumentationIntelligence, limit = 10) {
  return [...report.coverage]
    .filter((row) => row.public_symbols > 0)
    .sort((left, right) => left.coverage - right.coverage || left.path.localeCompare(right.path))
    .slice(0, limit);
}

/** A 0–100 coverage score rendered as one of four bands. */
export function coverageBand(score: number): 'strong' | 'partial' | 'weak' | 'none' {
  if (score >= 80) return 'strong';
  if (score >= 50) return 'partial';
  if (score >= 20) return 'weak';
  return 'none';
}
