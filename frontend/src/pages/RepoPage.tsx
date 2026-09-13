import { useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';

import { getPullRequests } from '../api/github';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import { PageContainer } from '../components/PageContainer';
import { Pagination } from '../components/Pagination';
import { PullRequestCard } from '../components/PullRequestCard';
import { useAsync } from '../hooks/useAsync';
import type { ScmProvider } from '../types';

const PER_PAGE = 30;

const STATE_TABS = [
  { value: 'open', label: 'Open' },
  { value: 'closed', label: 'Closed' },
];

export function RepoPage() {
  const { owner, repo } = useParams<{ owner: string; repo: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [state, setState] = useState('open');
  const [page, setPage] = useState(1);

  const provider: ScmProvider = searchParams.get('provider') === 'gitlab' ? 'gitlab' : 'github';
  const changeTerm = provider === 'gitlab' ? 'merge request' : 'pull request';
  const changeTermPlural = provider === 'gitlab' ? 'merge requests' : 'pull requests';

  const pullRequests = useAsync(
    () => getPullRequests(owner ?? '', repo ?? '', state, page, PER_PAGE, provider),
    [owner, repo, state, page, provider],
  );

  return (
    <PageContainer className="space-y-10">
      {/* Security map title block */}
      <section className="flex flex-wrap items-end justify-between gap-6 py-6 lg:py-9">
        <div className="min-w-0">
          <p className="hud-tag hud-tag-accent flex items-center gap-3">
            <span aria-hidden className="h-px w-10 bg-indigo-400/60" />
            Repository security map · {provider === 'gitlab' ? 'GitLab' : 'GitHub'}
          </p>
          <h1 className="mt-3 truncate text-[clamp(2.2rem,6vw,5.5rem)] font-semibold leading-[0.95] tracking-[-0.04em] text-slate-50">
            {owner}/{repo}
          </h1>
          <p className="mt-4 max-w-md text-sm leading-relaxed text-slate-400">
            Every {changeTerm} in this repository routes through the AI
            security pipeline — code, commit, analysis, verdict.
          </p>
        </div>
        <a
          href={`https://${provider === 'gitlab' ? 'gitlab.com' : 'github.com'}/${owner}/${repo}`}
          target="_blank"
          rel="noopener noreferrer"
          className="btn-secondary"
        >
          Open on {provider === 'gitlab' ? 'GitLab' : 'GitHub'} &#x2197;
        </a>
      </section>

      {/* Map body */}
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-[1fr_300px]">
        {/* Scan pipeline ledger */}
        <section className="min-w-0">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex w-fit border border-white/[0.06] bg-surface-1 p-0.5">
              {STATE_TABS.map((tab) => (
                <button
                  key={tab.value}
                  type="button"
                  onClick={() => {
                    setState(tab.value);
                    setPage(1);
                  }}
                  aria-selected={state === tab.value}
                  className={`px-4 py-1.5 text-sm font-medium transition-colors duration-150 ${
                    state === tab.value
                      ? 'bg-white/[0.06] text-accent-indigo'
                      : 'text-slate-400 hover:text-white'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
            <span className="font-mono text-xs uppercase tracking-[0.16em] text-slate-500">
              {pullRequests.data ? `${state} · ${pullRequests.data.pull_requests.length} routes` : '\u2014'}
            </span>
          </div>

          <div className="rail-vertical mt-5 pl-8">
            {pullRequests.loading ? (
              <LoadingState label={`Loading ${changeTermPlural}\u2026`} />
            ) : pullRequests.error || !pullRequests.data ? (
              <div className="pl-2">
                <ErrorState
                  title={`Could not load ${changeTermPlural}`}
                  message={pullRequests.error ?? undefined}
                  retry={pullRequests.refetch}
                />
              </div>
            ) : pullRequests.data.pull_requests.length === 0 ? (
              <div className="pl-2">
                <EmptyState
                  title={`No ${state} ${changeTermPlural}`}
                  description="Nothing to review in this repository right now."
                />
              </div>
            ) : (
              <div className="space-y-3">
                {pullRequests.data.pull_requests.map((pr) => (
                  <div key={pr.number} className="relative">
                    <span
                      aria-hidden
                      className="rail-vertical-dot absolute -left-[22px] top-4"
                    />
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
            )}
          </div>

          {pullRequests.data &&
            pullRequests.data.pull_requests.length > 0 &&
            !pullRequests.loading && (
              <div className="mt-8">
                <Pagination
                  page={page}
                  perPage={PER_PAGE}
                  hasMore={pullRequests.data.has_more}
                  onPageChange={setPage}
                />
              </div>
            )}
        </section>

        {/* Floating coverage overlay */}
        <aside className="hidden lg:block" aria-hidden="true">
          <div className="holo-panel sticky top-24 p-6">
            <p className="hud-tag hud-tag-accent">Coverage overlay</p>

            <div className="relative mx-auto mt-6 h-44 w-44">
              <div className="absolute inset-0 rounded-full border border-dashed border-indigo-400/25" />
              <div className="absolute inset-8 rounded-full border border-cyan-400/25" />
              <div className="absolute inset-14 rounded-full border border-violet-400/25" />
              <span className="absolute left-1/2 top-1/2 h-20 w-20 -translate-x-1/2 -translate-y-1/2 rounded-full bg-indigo-500/[0.1] blur-2xl" />
              <span className="absolute left-1/2 top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full bg-indigo-400 shadow-[0_0_16px_rgba(129,140,248,0.9)]" />
              <span className="railing-dot absolute right-2 top-6 h-1.5 w-1.5 rounded-full bg-cyan-400 shadow-[0_0_10px_rgba(34,211,238,0.9)]" />
              <span className="railing-dot absolute bottom-8 left-4 h-1.5 w-1.5 rounded-full bg-violet-400 shadow-[0_0_10px_rgba(139,92,246,0.9)]" />
            </div>

            <div className="mt-6 space-y-2.5 border-t border-white/[0.06] pt-4">
              <div className="flex items-center justify-between">
                <span className="hud-tag">Route state</span>
                <span className="font-mono text-sm capitalize text-slate-200">{state}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="hud-tag">On page</span>
                <span className="font-mono text-sm tabular-nums text-slate-200">
                  {pullRequests.data ? pullRequests.data.pull_requests.length : '\u2014'}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="hud-tag">Per page</span>
                <span className="font-mono text-sm tabular-nums text-slate-200">{PER_PAGE}</span>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </PageContainer>
  );
}