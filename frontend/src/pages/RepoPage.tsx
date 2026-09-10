import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import { getPullRequests } from '../api/github';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import { Pagination } from '../components/Pagination';
import { PullRequestCard } from '../components/PullRequestCard';
import { useAsync } from '../hooks/useAsync';

const PER_PAGE = 30;

const STATE_TABS = [
  { value: 'open', label: 'Open' },
  { value: 'closed', label: 'Closed' },
];

export function RepoPage() {
  const { owner, repo } = useParams<{ owner: string; repo: string }>();
  const navigate = useNavigate();
  const [state, setState] = useState('open');
  const [page, setPage] = useState(1);

  const pullRequests = useAsync(
    () => getPullRequests(owner ?? '', repo ?? '', state, page, PER_PAGE),
    [owner, repo, state, page],
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">
            {owner}/{repo}
          </h1>
          <p className="mt-1 text-sm text-slate-500">Pull requests in this repository.</p>
        </div>
        <a
          href={`https://github.com/${owner}/${repo}`}
          target="_blank"
          rel="noopener noreferrer"
          className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50"
        >
          Open on GitHub ↗
        </a>
      </div>

      <div className="flex w-fit rounded-lg border border-slate-200 bg-white p-1 shadow-sm">
        {STATE_TABS.map((tab) => (
          <button
            key={tab.value}
            type="button"
            onClick={() => {
              setState(tab.value);
              setPage(1);
            }}
            className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
              state === tab.value ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-50'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {pullRequests.loading ? (
        <LoadingState label="Loading pull requests…" />
      ) : pullRequests.error || !pullRequests.data ? (
        <ErrorState
          title="Could not load pull requests"
          message={pullRequests.error ?? undefined}
          retry={pullRequests.refetch}
        />
      ) : pullRequests.data.pull_requests.length === 0 ? (
        <EmptyState
          title={`No ${state} pull requests`}
          description="Nothing to review in this repository right now."
        />
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