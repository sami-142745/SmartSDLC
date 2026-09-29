import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { getPullRequests, getRepositories } from '../api/github';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import { PageContainer } from '../components/PageContainer';
import { PageHeader } from '../components/PageHeader';
import { Pagination } from '../components/Pagination';
import { ProviderToggle } from '../components/ProviderToggle';
import { PullRequestCard } from '../components/PullRequestCard';
import { Card, CardBody, CardHeader } from '../components/ui/Card';
import { useAsync } from '../hooks/useAsync';
import type { ScmProvider } from '../types';

const PER_PAGE = 30;

const FLOW_STAGES = [
  'Code',
  'Commit',
  'Change request',
  'AI analysis',
  'Security',
  'Merge',
] as const;

const CURRENT_STAGE = 'Change request';

function Readout({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="eyebrow">{label}</span>
      <span className="font-mono text-[13px] capitalize tabular-nums text-ink">{value}</span>
    </div>
  );
}

export function PullRequestsPage() {
  const navigate = useNavigate();
  const [provider, setProvider] = useState<ScmProvider>('github');
  const [owner, setOwner] = useState('');
  const [repo, setRepo] = useState('');
  const [state, setState] = useState('open');
  const [page, setPage] = useState(1);

  const host = provider === 'gitlab' ? 'GitLab' : 'GitHub';
  const changeTerm = provider === 'gitlab' ? 'merge request' : 'pull request';
  const changeTermPlural = provider === 'gitlab' ? 'merge requests' : 'pull requests';

  const repositories = useAsync(() => getRepositories(1, 100, provider), [provider]);
  const selected = owner && repo;

  const pullRequests = useAsync(
    () =>
      selected ? getPullRequests(owner, repo, state, page, PER_PAGE, provider) : Promise.resolve(null),
    [owner, repo, state, page, selected, provider],
  );

  const handleRepositoryChange = (fullName: string) => {
    const [nextOwner = '', nextRepo = ''] = fullName.split('/');
    setOwner(nextOwner);
    setRepo(nextRepo);
    setPage(1);
  };

  const handleProviderChange = (next: ScmProvider) => {
    setProvider(next);
    setOwner('');
    setRepo('');
    setPage(1);
  };

  return (
    <PageContainer className="space-y-6">
      <PageHeader
        eyebrow={
          <>
            <span aria-hidden className="h-px w-8 bg-indigo-400/60" />
            Forwarded change pipeline &middot; {host}
          </>
        }
        title={
          provider === 'gitlab' ? (
            <>
              <span className="block">MERGE</span>
              <span className="text-brand-gradient block">REQUESTS</span>
            </>
          ) : (
            <>
              <span className="block">PULL</span>
              <span className="text-brand-gradient block">REQUESTS</span>
            </>
          )
        }
        description={`Changes move through the security pipeline — every ${changeTerm} is a live route waiting for AI analysis.`}
      />

      <Card tone="flat">
        <CardHeader title="Change pipeline" />
        <CardBody>
          <ol className="flex flex-wrap items-center gap-x-2 gap-y-2">
            {FLOW_STAGES.map((stage, index) => {
              const current = stage === CURRENT_STAGE;
              return (
                <li key={stage} className="flex items-center gap-2">
                  <span
                    aria-current={current ? 'step' : undefined}
                    className={
                      current
                        ? 'rounded-full border border-accent-indigo/35 bg-accent-indigo/[0.08] px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.14em] text-ink'
                        : 'rounded-full border border-white/[0.06] bg-white/[0.02] px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.14em] text-ink-faint'
                    }
                  >
                    {stage}
                  </span>
                  {index < FLOW_STAGES.length - 1 ? (
                    <span aria-hidden className="h-px w-3 bg-white/[0.08]" />
                  ) : null}
                </li>
              );
            })}
          </ol>
        </CardBody>
      </Card>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[17rem_minmax(0,1fr)]">
        <Card tone="flat" className="self-start">
          <CardHeader title="Route filters" />
          <CardBody>
            <label className="flex flex-col gap-1.5">
              <span className="eyebrow">Source provider</span>
              <ProviderToggle value={provider} onChange={handleProviderChange} />
            </label>

            <label className="mt-4 flex flex-col gap-1.5">
              <span className="eyebrow">Repository</span>
              {repositories.loading ? (
                <span className="text-sm text-ink-subtle">Loading…</span>
              ) : (
                <select
                  value={selected ? `${owner}/${repo}` : ''}
                  onChange={(event) => handleRepositoryChange(event.target.value)}
                  className="field min-w-[14rem]"
                >
                  <option value="" className="bg-surface-1 text-ink">
                    Select a repository…
                  </option>
                  {(repositories.data?.repositories ?? []).map((repository) => (
                    <option
                      key={repository.full_name}
                      value={repository.full_name}
                      className="bg-surface-1 text-ink"
                    >
                      {repository.full_name}
                    </option>
                  ))}
                </select>
              )}
            </label>

            <label className="mt-4 flex flex-col gap-1.5">
              <span className="eyebrow">State</span>
              <select
                value={state}
                onChange={(event) => {
                  setState(event.target.value);
                  setPage(1);
                }}
                className="field min-w-[10rem]"
              >
                <option value="open" className="bg-surface-1 text-ink">
                  Open
                </option>
                <option value="closed" className="bg-surface-1 text-ink">
                  Closed
                </option>
              </select>
            </label>

            <div className="mt-4 space-y-2.5 border-t border-white/[0.06] pt-4">
              <Readout label="State" value={state} />
              <Readout label="Per page" value={PER_PAGE} />
            </div>
          </CardBody>
        </Card>

        <div className="min-w-0">
          {!selected ? (
            <EmptyState
              title="Select a repository"
              description={`Choose a repository to see its ${changeTermPlural}.`}
            />
          ) : pullRequests.loading ? (
            <LoadingState label={`Loading ${changeTermPlural}…`} />
          ) : pullRequests.error || !pullRequests.data ? (
            <ErrorState
              title={`Could not load ${changeTermPlural}`}
              message={pullRequests.error ?? undefined}
              retry={pullRequests.refetch}
            />
          ) : pullRequests.data.pull_requests.length === 0 ? (
            <EmptyState title={`No ${state} ${changeTermPlural}`} description="Nothing to review here." />
          ) : (
            <>
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
              <Pagination
                page={page}
                perPage={PER_PAGE}
                hasMore={pullRequests.data.has_more}
                onPageChange={setPage}
              />
            </>
          )}
        </div>
      </div>
    </PageContainer>
  );
}
