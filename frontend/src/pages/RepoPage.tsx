import { useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';

import { getPullRequests } from '../api/github';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import { PageContainer } from '../components/PageContainer';
import { PageHeader } from '../components/PageHeader';
import { Pagination } from '../components/Pagination';
import { PullRequestCard } from '../components/PullRequestCard';
import { Card, CardBody, CardHeader } from '../components/ui/Card';
import { cn } from '../lib/cn';
import { useAsync } from '../hooks/useAsync';
import type { ScmProvider } from '../types';

const PER_PAGE = 30;

const STATE_TABS = [
  { value: 'open', label: 'Open' },
  { value: 'closed', label: 'Closed' },
];

function Readout({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="eyebrow">{label}</span>
      <span className="font-mono text-[13px] capitalize tabular-nums text-ink">{value}</span>
    </div>
  );
}

export function RepoPage() {
  const { owner, repo } = useParams<{ owner: string; repo: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [state, setState] = useState('open');
  const [page, setPage] = useState(1);

  const provider: ScmProvider = searchParams.get('provider') === 'gitlab' ? 'gitlab' : 'github';
  const host = provider === 'gitlab' ? 'GitLab' : 'GitHub';
  const changeTerm = provider === 'gitlab' ? 'merge request' : 'pull request';
  const changeTermPlural = provider === 'gitlab' ? 'merge requests' : 'pull requests';

  const pullRequests = useAsync(
    () => getPullRequests(owner ?? '', repo ?? '', state, page, PER_PAGE, provider),
    [owner, repo, state, page, provider],
  );

  const onPage = pullRequests.data?.pull_requests.length;

  return (
    <PageContainer className="space-y-6">
      <PageHeader
        eyebrow={
          <>
            <span aria-hidden className="h-px w-8 bg-indigo-400/60" />
            Repository security map &middot; {host}
          </>
        }
        title={
          <span className="font-mono">
            {owner}/{repo}
          </span>
        }
        description={`Every ${changeTerm} in this repository routes through the AI security pipeline — code, commit, analysis, verdict.`}
        actions={
          <a
            href={`https://${provider === 'gitlab' ? 'gitlab.com' : 'github.com'}/${owner}/${repo}`}
            target="_blank"
            rel="noopener noreferrer"
            className="btn-secondary"
          >
            Open on {host} &#x2197;
          </a>
        }
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_18rem]">
        <Card>
          <CardHeader
            title="Review routes"
            actions={
              <div
                className="flex w-fit items-center rounded-lg border border-white/[0.06] bg-surface-1 p-0.5"
                role="group"
                aria-label="Filter by state"
              >
                {STATE_TABS.map((tab) => (
                  <button
                    key={tab.value}
                    type="button"
                    aria-pressed={state === tab.value}
                    onClick={() => {
                      setState(tab.value);
                      setPage(1);
                    }}
                    className={cn(
                      'rounded-md px-3.5 py-1.5 text-[13px] font-medium transition-colors duration-150',
                      state === tab.value
                        ? 'bg-white/[0.07] text-ink'
                        : 'text-ink-subtle hover:text-ink-muted',
                    )}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
            }
          />
          <CardBody>
            {pullRequests.loading ? (
              <LoadingState label={`Loading ${changeTermPlural}…`} />
            ) : pullRequests.error || !pullRequests.data ? (
              <ErrorState
                title={`Could not load ${changeTermPlural}`}
                message={pullRequests.error ?? undefined}
                retry={pullRequests.refetch}
              />
            ) : pullRequests.data.pull_requests.length === 0 ? (
              <EmptyState
                title={`No ${state} ${changeTermPlural}`}
                description="Nothing to review in this repository right now."
              />
            ) : (
              <div className="space-y-3">
                {pullRequests.data.pull_requests.map((pr) => (
                  <PullRequestCard
                    key={pr.number}
                    pullRequest={pr}
                    repoName={`${owner}/${repo}`}
                    onClick={() =>
                      navigate(
                        `/pull-requests/${owner}/${repo}/${pr.number}${provider === 'gitlab' ? '?provider=gitlab' : ''}`,
                      )
                    }
                  />
                ))}
              </div>
            )}

            {pullRequests.data && pullRequests.data.pull_requests.length > 0 && !pullRequests.loading ? (
              <Pagination
                page={page}
                perPage={PER_PAGE}
                hasMore={pullRequests.data.has_more}
                onPageChange={setPage}
              />
            ) : null}
          </CardBody>
        </Card>

        <Card tone="flat" className="self-start">
          <CardHeader title="Route state" />
          <CardBody>
            <div className="space-y-2.5">
              <Readout label="State" value={state} />
              <Readout label="On page" value={onPage ?? '—'} />
              <Readout label="Per page" value={PER_PAGE} />
              <Readout label="Source" value={host} />
            </div>
          </CardBody>
        </Card>
      </div>
    </PageContainer>
  );
}
