import { useParams, useSearchParams } from 'react-router-dom';

import type { ScmProvider } from '../../types';

export interface RepositoryScope {
  owner: string;
  repository: string;
  provider: ScmProvider;
  /** True once the route actually carried an owner/repo pair. */
  resolved: boolean;
}

/**
 * Reads the owner/repo pair and provider for every repository intelligence page.
 *
 * `useParams` returns empty strings before the route matches, so `resolved` lets
 * a page distinguish "still routing" from "a repository was requested but is
 * blank" and avoid firing requests with empty path segments.
 */
export function useRepositoryScope(): RepositoryScope {
  const { owner = '', repo = '' } = useParams<{ owner: string; repo: string }>();
  const [searchParams] = useSearchParams();

  return {
    owner,
    repository: repo,
    provider: searchParams.get('provider') === 'gitlab' ? 'gitlab' : 'github',
    resolved: Boolean(owner && repo),
  };
}
