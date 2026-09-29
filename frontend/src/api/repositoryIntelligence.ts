import { http } from './client';
import type {
  CacheInvalidationResult,
  CachedRepositoryRef,
  DependencyReport,
  LanguageBreakdown,
  ReadmeIntelligence,
  RepositoryDashboard,
  RepositoryFileContent,
  RepositoryHealth,
  RepositoryTree,
  ScmProvider,
} from '../types';

const BASE = '/repository-intelligence';

function repoBase(owner: string, repository: string): string {
  return `${BASE}/repositories/${encodeURIComponent(owner)}/${encodeURIComponent(repository)}`;
}

interface RepoParams {
  provider?: ScmProvider;
  refresh?: boolean;
}

/**
 * GitLab is sent only when explicitly selected so the backend keeps defaulting
 * to GitHub, matching the rest of the API surface.
 */
function repoParams({ provider, refresh }: RepoParams): Record<string, string | boolean> {
  const params: Record<string, string | boolean> = {};
  if (provider === 'gitlab') params.provider = 'gitlab';
  if (refresh) params.refresh = true;
  return params;
}

export async function getCachedRepositories(): Promise<CachedRepositoryRef[]> {
  const { data } = await http.get<CachedRepositoryRef[]>(`${BASE}/repositories`);
  return data;
}

export async function getRepositoryDashboard(
  owner: string,
  repository: string,
  options: RepoParams = {},
): Promise<RepositoryDashboard> {
  const { data } = await http.get<RepositoryDashboard>(
    `${repoBase(owner, repository)}/dashboard`,
    { params: repoParams(options) },
  );
  return data;
}

export async function getRepositoryHealth(
  owner: string,
  repository: string,
  options: RepoParams = {},
): Promise<RepositoryHealth> {
  const { data } = await http.get<RepositoryHealth>(`${repoBase(owner, repository)}/health`, {
    params: repoParams(options),
  });
  return data;
}

export async function getRepositoryLanguages(
  owner: string,
  repository: string,
  options: RepoParams = {},
): Promise<LanguageBreakdown> {
  const { data } = await http.get<LanguageBreakdown>(
    `${repoBase(owner, repository)}/languages`,
    { params: repoParams(options) },
  );
  return data;
}

export async function getRepositoryDependencies(
  owner: string,
  repository: string,
  options: RepoParams = {},
): Promise<DependencyReport> {
  const { data } = await http.get<DependencyReport>(
    `${repoBase(owner, repository)}/dependencies`,
    { params: repoParams(options) },
  );
  return data;
}

export async function getRepositoryReadme(
  owner: string,
  repository: string,
  options: RepoParams = {},
): Promise<ReadmeIntelligence> {
  const { data } = await http.get<ReadmeIntelligence>(
    `${repoBase(owner, repository)}/readme`,
    { params: repoParams(options) },
  );
  return data;
}

export async function getRepositoryTree(
  owner: string,
  repository: string,
  options: RepoParams & { ref?: string | null } = {},
): Promise<RepositoryTree> {
  const params = repoParams(options);
  if (options.ref) params.ref = options.ref;
  const { data } = await http.get<RepositoryTree>(`${repoBase(owner, repository)}/tree`, {
    params,
  });
  return data;
}

export async function getRepositoryFile(
  owner: string,
  repository: string,
  path: string,
  options: { provider?: ScmProvider; ref?: string | null } = {},
): Promise<RepositoryFileContent> {
  const params: Record<string, string> = { path };
  if (options.provider === 'gitlab') params.provider = 'gitlab';
  if (options.ref) params.ref = options.ref;
  const { data } = await http.get<RepositoryFileContent>(`${repoBase(owner, repository)}/file`, {
    params,
  });
  return data;
}

export async function invalidateRepositoryCache(
  owner: string,
  repository: string,
): Promise<CacheInvalidationResult> {
  const { data } = await http.delete<CacheInvalidationResult>(
    `${repoBase(owner, repository)}/cache`,
  );
  return data;
}
