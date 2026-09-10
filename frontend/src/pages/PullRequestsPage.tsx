import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { getPullRequests, getRepositories } from '../api/github';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import { Pagination } from '../components/Pagination';
import { PullRequestCard } from '../components/PullRequestCard';
import { useAsync } from '../hooks/useAsync';

const PER_PAGE = 30;

export function PullRequestsPage() {
  const navigate = useNavigate();
  const [owner, setOwner] = useState('');
  const [repo, setRepo] = useState('');
  const [state, setState] = useState('open');
  const [page, setPage] = useState(1);

  const repositories = useAsync(() => getRepositories(1, 100), []);
  const selected = owner && repo;

  const pullRequests = useAsync(
    () => (selected ? getPullRequests(owner, repo, state, page, PER_PAGE) : Promise.resolve(null)),
    [owner, repo, state, page, selected],
  );

  const handleRepositoryChange = (fullName: string) => {
    const [nextOwner = '', nextRepo = ''] = fullName.split('/');
    setOwner(nextOwner);
    setRepo(nextRepo);
    setPage(1);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Pull Requests</h1>
        <p className="mt-1 text-sm text-slate-500">
          Pick a repository to browse pull requests.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-4">
        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Repository
          </span>
          {repositories.loading ? (
            <span className="text-sm text-slate-400">Loading…</span>
          ) : (
            <select
              value={selected ? `${owner}/${repo}` : ''}
              onChange={(event) => handleRepositoryChange(event.target.value)}
              className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm focus:border-slate-400 focus:outline-none"
            >
              <option value="">Select a repository…</option>
              {(repositories.data?.repositories ?? []).map((repository) => (
                <option key={repository.full_name} value={repository.full_name}>
                  {repository.full_name}
                </option>
              ))}
            </select>
          )}
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">State</span>
          <select
            value={state}
            onChange={(event) => {
              setState(event.target.value);
              setPage(1);
            }}
            className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm focus:border-slate-400 focus:outline-none"
          >
            <option value="open">Open</option>
            <option value="closed">Closed</option>
          </select>
        </label>
      </div>

      {!selected ? (
        <EmptyState
          title="Select a repository"
          description="Choose a repository above to see its pull requests."
        />
      ) : pullRequests.loading ? (
        <LoadingState label="Loading pull requests…" />
      ) : pullRequests.error || !pullRequests.data ? (
        <ErrorState
          title="Could not load pull requests"
          message={pullRequests.error ?? undefined}
          retry={pullRequests.refetch}
        />
      ) : pullRequests.data.pull_requests.length === 0 ? (
        <EmptyState title={`No ${state} pull requests`} description="Nothing to review here." />
      ) : (
        <>
          <div className="space-y-3">
            {pullRequests.data.pull_requests.map((pr) => (
              <PullRequestCard
                key={pr.number}
                pullRequest={pr}
                repoName={`${owner}/${repo}`}
                onClick={() => navigate(`/pull-requests/${owner}/${repo}/${pr.number}`)}
              />
            ))}
          </div>
          <Pagination
            page={page}
            perPage={PER_PAGE}
            hasMore={pullRequests.data.has_more}
            onPageChange={setPage}
          />
        </>
      )}
    </div>
  );
}