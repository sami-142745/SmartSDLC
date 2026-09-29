import { http } from './client';
import type {
  ArchitectureEdge,
  ArchitectureGraph,
  ArchitectureIssue,
  ArchitectureIssueKind,
  ArchitectureNode,
  ScmProvider,
} from '../types';

const BASE = '/architecture';

function repoBase(owner: string, repository: string): string {
  return `${BASE}/repositories/${encodeURIComponent(owner)}/${encodeURIComponent(repository)}`;
}

export interface ArchitectureParams {
  provider?: ScmProvider;
  ref?: string;
  refresh?: boolean;
  maxFiles?: number;
}

function repoParams({ provider, ref, refresh, maxFiles }: ArchitectureParams): Record<string, string | number | boolean> {
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
 * The dependency graph, module inventory, issues and summary for one repository.
 *
 * The backend caches this, so a second call is cheap unless `refresh` is set.
 */
export async function getArchitecture(
  owner: string,
  repository: string,
  options: ArchitectureParams = {},
): Promise<ArchitectureGraph> {
  const { data } = await http.get<ArchitectureGraph>(repoBase(owner, repository), {
    params: repoParams(options),
  });
  return data;
}

/** Groups issues by kind, preserving the backend's deterministic ordering. */
export function issuesByKind(issues: ArchitectureIssue[]): Record<ArchitectureIssueKind, ArchitectureIssue[]> {
  const grouped = {} as Record<ArchitectureIssueKind, ArchitectureIssue[]>;
  for (const issue of issues) {
    (grouped[issue.kind] ??= []).push(issue);
  }
  return grouped;
}

/** Modules only, dropping the external-package nodes from the graph. */
export function internalNodes(graph: ArchitectureGraph): ArchitectureNode[] {
  return graph.nodes.filter((node) => node.kind !== 'external');
}

/** External-package nodes, which the graph renders separately from source. */
export function externalNodes(graph: ArchitectureGraph): ArchitectureNode[] {
  return graph.nodes.filter((node) => node.kind === 'external');
}

/**
 * Edges restricted to real modules.
 *
 * External edges point at synthetic `external:<package>` ids that are not in
 * `modules`, so a caller building a module-only adjacency map must drop them.
 */
export function internalEdges(graph: ArchitectureGraph): ArchitectureEdge[] {
  const known = new Set(graph.modules.map((module) => module.id));
  return graph.edges.filter((edge) => edge.kind === 'internal' && known.has(edge.source) && known.has(edge.target));
}
