import { http } from './client';
import type {
  PullRequestFile,
  PullRequestListResponse,
  PullRequestSummary,
  RepositoryListResponse,
  ScmProvider,
} from '../types';

function providerParam(provider: ScmProvider): Record<string, string> {
  return provider === 'gitlab' ? { provider } : {};
}

export async function getRepositories(
  page = 1,
  perPage = 30,
  provider: ScmProvider = 'github',
): Promise<RepositoryListResponse> {
  const { data } = await http.get<RepositoryListResponse>('/repositories', {
    params: { page, per_page: perPage, ...providerParam(provider) },
  });
  return data;
}

export async function getPullRequests(
  owner: string,
  repo: string,
  state = 'open',
  page = 1,
  perPage = 30,
  provider: ScmProvider = 'github',
): Promise<PullRequestListResponse> {
  const { data } = await http.get<PullRequestListResponse>('/pullrequests', {
    params: { owner, repo, state, page, per_page: perPage, ...providerParam(provider) },
  });
  return data;
}

export async function getPullRequest(
  owner: string,
  repo: string,
  number: number,
  provider: ScmProvider = 'github',
): Promise<PullRequestSummary> {
  const { data } = await http.get<PullRequestSummary>(
    `/pullrequests/${owner}/${repo}/${number}`,
    { params: providerParam(provider) },
  );
  return data;
}

export async function getPullRequestFiles(
  owner: string,
  repo: string,
  number: number,
  provider: ScmProvider = 'github',
): Promise<PullRequestFile[]> {
  const { data } = await http.get<PullRequestFile[]>(
    `/pullrequests/${owner}/${repo}/${number}/files`,
    { params: providerParam(provider) },
  );
  return data;
}

export async function getPullRequestDiff(
  owner: string,
  repo: string,
  number: number,
  provider: ScmProvider = 'github',
): Promise<string> {
  const { data } = await http.get<string>(
    `/pullrequests/${owner}/${repo}/${number}/diff`,
    { params: providerParam(provider), responseType: 'text' },
  );
  return data;
}