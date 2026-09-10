import { http } from './client';
import type {
  PullRequestFile,
  PullRequestListResponse,
  PullRequestSummary,
  RepositoryListResponse,
} from '../types';

export async function getRepositories(
  page = 1,
  perPage = 30,
): Promise<RepositoryListResponse> {
  const { data } = await http.get<RepositoryListResponse>('/repositories', {
    params: { page, per_page: perPage },
  });
  return data;
}

export async function getPullRequests(
  owner: string,
  repo: string,
  state = 'open',
  page = 1,
  perPage = 30,
): Promise<PullRequestListResponse> {
  const { data } = await http.get<PullRequestListResponse>('/pullrequests', {
    params: { owner, repo, state, page, per_page: perPage },
  });
  return data;
}

export async function getPullRequest(
  owner: string,
  repo: string,
  number: number,
): Promise<PullRequestSummary> {
  const { data } = await http.get<PullRequestSummary>(
    `/pullrequests/${owner}/${repo}/${number}`,
  );
  return data;
}

export async function getPullRequestFiles(
  owner: string,
  repo: string,
  number: number,
): Promise<PullRequestFile[]> {
  const { data } = await http.get<PullRequestFile[]>(
    `/pullrequests/${owner}/${repo}/${number}/files`,
  );
  return data;
}

export async function getPullRequestDiff(
  owner: string,
  repo: string,
  number: number,
): Promise<string> {
  const { data } = await http.get<string>(
    `/pullrequests/${owner}/${repo}/${number}/diff`,
    { responseType: 'text' },
  );
  return data;
}