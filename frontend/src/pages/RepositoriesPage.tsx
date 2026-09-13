import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { getRepositories } from '../api/github';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import { PageContainer } from '../components/PageContainer';
import { Pagination } from '../components/Pagination';
import { ProviderToggle } from '../components/ProviderToggle';
import { RepositoryCard } from '../components/RepositoryCard';
import { useAsync } from '../hooks/useAsync';
import type { ScmProvider } from '../types';

const PER_PAGE = 30;

const PROVIDER_LABEL: Record<ScmProvider, string> = {
  github: 'GitHub · live feed',
  gitlab: 'GitLab · live feed',
};

export function RepositoriesPage() {
  const navigate = useNavigate();
  const [provider, setProvider] = useState<ScmProvider>('github');
  const [page, setPage] = useState(1);
  const repositories = useAsync(() => getRepositories(page, PER_PAGE, provider), [page, provider]);

  const handleProviderChange = (next: ScmProvider) => {
    setProvider(next);
    setPage(1);
  };

  return (
    <PageContainer className="space-y-10">
      {/* 3D network hero over the repository galaxy scene */}
      <section className="flex flex-col justify-center py-8 lg:py-12">
        <p className="hud-tag hud-tag-accent flex items-center gap-3">
          <span aria-hidden className="h-px w-10 bg-indigo-400/60" />
          {PROVIDER_LABEL[provider]}
        </p>
        <h1 className="hero-display mt-4 text-slate-50">
          <span className="block">REPOSITORY</span>
          <span className="h-grad block">NETWORK</span>
        </h1>
        <div className="mt-6 flex flex-wrap items-center gap-x-8 gap-y-3">
          <div>
            <p className="font-mono text-2xl font-semibold tabular-nums text-slate-50">
              {repositories.data ? repositories.data.repositories.length : '\u2014'}
            </p>
            <p className="hud-tag mt-1">Repositories wired</p>
          </div>
          <div>
            <p className="font-mono text-2xl font-semibold tabular-nums text-slate-50">
              {repositories.data && repositories.data.has_more ? 'more' : '\u2014'}
            </p>
            <p className="hud-tag mt-1">Further pages</p>
          </div>
          <ProviderToggle value={provider} onChange={handleProviderChange} />
          <p className="max-w-xs text-sm leading-relaxed text-slate-400">
            Connected {provider === 'github' ? 'GitHub' : 'GitLab'} repositories, each positioned
            as a node in the review network and scanned by the AI security layer.
          </p>
        </div>
      </section>

      {repositories.loading ? (
        <LoadingState label="Loading repositories\u2026" />
      ) : repositories.error || !repositories.data ? (
        <ErrorState
          title="Could not load repositories"
          message={repositories.error ?? undefined}
          retry={repositories.refetch}
        />
      ) : repositories.data.repositories.length === 0 ? (
        <EmptyState
          title="No repositories found"
          description={`Make sure your ${provider === 'github' ? 'GitHub' : 'GitLab'} account has access to repositories.`}
        />
      ) : (
        <section className="relative">
          <div className="mb-4 flex items-center justify-between border-b border-white/[0.06] pb-3">
            <span className="eyebrow">Connected repositories</span>
            <span className="font-mono text-xs tabular-nums text-slate-500">
              page {page} · {repositories.data.repositories.length} on screen
            </span>
          </div>

          <div className="relative">
            {/* vertical network rail */}
            <span
              aria-hidden
              className="absolute bottom-5 left-[15px] top-5 w-px bg-gradient-to-b from-indigo-500/50 via-cyan-400/25 to-transparent md:left-1/2 md:top-10"
            />
            <div className="space-y-3">
              {repositories.data.repositories.map((repo, index) => (
                <div
                  key={repo.full_name}
                  className={`relative md:flex md:items-center ${
                    index % 2 === 1 ? 'md:justify-end' : ''
                  }`}
                >
                  {/* node */}
                  <span
                    aria-hidden
                    className={`absolute left-[9px] top-8 z-10 hidden h-3.5 w-3.5 rounded-full border-2 border-[#0a0d1c] bg-indigo-400 shadow-[0_0_12px_rgba(129,140,248,0.9)] md:block ${
                      index % 2 === 1 ? 'md:left-auto md:right-[calc(50%-9px)]' : 'md:left-[calc(50%-9px)]'
                    }`}
                  />
                  <span className="absolute right-[calc(50%-9px)] top-8 z-10 hidden h-3.5 w-3.5 rounded-full border-2 border-[#0a0d1c] bg-cyan-400 shadow-[0_0_12px_rgba(34,211,238,0.9)] md:hidden" />
                  <div
                    className={`relative ${index % 2 === 1 ? 'md:w-[calc(50%-2.5rem)]' : ''} ${
                      index % 2 === 0 ? 'md:mr-auto md:w-[calc(50%-2.5rem)]' : ''
                    }`}
                  >
                    <span className="glass-edge relative ml-10 block md:ml-0">
                      <RepositoryCard
                        repository={repo}
                        onClick={() =>
                          navigate(
                            `/repositories/${encodeURIComponent(repo.owner ?? '')}/${encodeURIComponent(repo.name)}${provider === 'gitlab' ? '?provider=gitlab' : ''}`,
                          )
                        }
                      />
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-8">
            <Pagination
              page={page}
              perPage={PER_PAGE}
              hasMore={repositories.data.has_more}
              onPageChange={setPage}
            />
          </div>
        </section>
      )}
    </PageContainer>
  );
}