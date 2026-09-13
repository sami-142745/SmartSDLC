import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { getPullRequests, getRepositories } from '../api/github';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import { PageContainer } from '../components/PageContainer';
import { Pagination } from '../components/Pagination';
import { ProviderToggle } from '../components/ProviderToggle';
import { PullRequestCard } from '../components/PullRequestCard';
import { useAsync } from '../hooks/useAsync';
import type { ScmProvider } from '../types';

const PER_PAGE = 30;

const FLOW_STAGES = [
  'CODE',
  'COMMIT',
  'PULL REQUEST',
  'AI ANALYSIS',
  'SECURITY',
  'MERGE',
] as const;
const CURRENT_STAGE = 'PULL REQUEST';

export function PullRequestsPage() {
  const navigate = useNavigate();
  const [provider, setProvider] = useState<ScmProvider>('github');
  const [owner, setOwner] = useState('');
  const [repo, setRepo] = useState('');
  const [state, setState] = useState('open');
  const [page, setPage] = useState(1);

  const changeTerm = provider === 'gitlab' ? 'merge request' : 'pull request';
  const changeTermPlural = provider === 'gitlab' ? 'merge requests' : 'pull requests';

  const repositories = useAsync(() => getRepositories(1, 100, provider), [provider]);
  const selected = owner && repo;

  const pullRequests = useAsync(
    () =>
      selected
        ? getPullRequests(owner, repo, state, page, PER_PAGE, provider)
        : Promise.resolve(null),
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
    <PageContainer className="space-y-10">
      {/* Header over the pipeline scene */}
      <section className="py-6 lg:py-9">
        <p className="hud-tag hud-tag-accent flex items-center gap-3">
          <span aria-hidden className="h-px w-10 bg-indigo-400/60" />
          Forwarded change pipeline · {provider === 'gitlab' ? 'GitLab' : 'GitHub'}
        </p>
        <h1 className="hero-display mt-4 text-slate-50">
          {provider === 'gitlab' ? (
            <>
              <span className="block">MERGE</span>
              <span className="h-grad block">REQUESTS</span>
            </>
          ) : (
            <>
              <span className="block">PULL</span>
              <span className="h-grad block">REQUESTS</span>
            </>
          )}
        </h1>
        <p className="mt-5 max-w-md text-sm leading-relaxed text-slate-400">
          Changes move left to right through the security pipeline — every{' '}
          {changeTerm} is a live route waiting for AI analysis.
        </p>
      </section>

      {/* Horizontal code-flow track */}
      <section className="flow-track grid grid-cols-3 gap-6 md:grid-cols-6" aria-hidden="true">
        {FLOW_STAGES.map((stage) => (
          <div
            key={stage}
            className={`flow-node text-center ${
              stage === CURRENT_STAGE ? 'opacity-100' : 'opacity-55'
            }`}
          >
            <p
              className={`mt-3 font-mono text-[9px] font-semibold uppercase tracking-[0.2em] ${
                stage === CURRENT_STAGE ? 'hud-tag-accent' : 'text-slate-500'
              }`}
            >
              {stage}
            </p>
          </div>
        ))}
      </section>

      {/* Filters + ledger */}
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-[280px_1fr]">
        <aside>
          <div className="holo-panel lg:sticky lg:top-24 p-5">
            <p className="hud-tag hud-tag-accent mb-4">Route filters</p>
            <label className="flex flex-col gap-1.5">
              <span className="section-title">Source provider</span>
              <ProviderToggle value={provider} onChange={handleProviderChange} />
            </label>

            <label className="mt-5 flex flex-col gap-1.5">
              <span className="section-title">Repository</span>
              {repositories.loading ? (
                <span className="text-sm text-slate-400">Loading\u2026</span>
              ) : (
                <select
                  value={selected ? `${owner}/${repo}` : ''}
                  onChange={(event) => handleRepositoryChange(event.target.value)}
                  className="field min-w-[16rem]"
                >
                  <option value="" className="bg-surface-1 text-slate-100">
                    Select a repository\u2026
                  </option>
                  {(repositories.data?.repositories ?? []).map((repository) => (
                    <option key={repository.full_name} value={repository.full_name} className="bg-surface-1 text-slate-100">
                      {repository.full_name}
                    </option>
                  ))}
                </select>
              )}
            </label>

            <label className="mt-5 flex flex-col gap-1.5">
              <span className="section-title">State</span>
              <select
                value={state}
                onChange={(event) => {
                  setState(event.target.value);
                  setPage(1);
                }}
                className="field min-w-[10rem]"
              >
                <option value="open" className="bg-surface-1 text-slate-100">Open</option>
                <option value="closed" className="bg-surface-1 text-slate-100">Closed</option>
              </select>
            </label>

            <div className="mt-5 space-y-2 border-t border-white/[0.06] pt-4">
              <div className="flex items-center justify-between">
                <span className="hud-tag">State</span>
                <span className="font-mono text-sm capitalize text-slate-200">{state}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="hud-tag">Per page</span>
                <span className="font-mono text-sm tabular-nums text-slate-200">{PER_PAGE}</span>
              </div>
            </div>
          </div>
        </aside>

        <section className="min-w-0">
          {!selected ? (
            <EmptyState
              title={`Select a repository`}
              description={`Choose a repository above to see its ${changeTermPlural}.`}
            />
          ) : pullRequests.loading ? (
            <LoadingState label={`Loading ${changeTermPlural}\u2026`} />
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
              <div className="rail-vertical space-y-3 pl-8">
                {pullRequests.data.pull_requests.map((pr) => (
                  <div key={pr.number} className="relative">
                    <span aria-hidden className="rail-vertical-dot absolute -left-[22px] top-4" />
                    <PullRequestCard
                      pullRequest={pr}
                      repoName={`${owner}/${repo}`}
                      onClick={() =>
                        navigate(
                          `/pull-requests/${owner}/${repo}/${pr.number}${provider === 'gitlab' ? '?provider=gitlab' : ''}`,
                        )
                      }
                    />
                  </div>
                ))}
              </div>
              <div className="mt-8">
                <Pagination
                  page={page}
                  perPage={PER_PAGE}
                  hasMore={pullRequests.data.has_more}
                  onPageChange={setPage}
                />
              </div>
            </>
          )}
        </section>
      </div>
    </PageContainer>
  );
}