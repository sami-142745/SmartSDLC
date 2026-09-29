import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { getRepositories } from '../api/github';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import { PageContainer } from '../components/PageContainer';
import { PageHeader } from '../components/PageHeader';
import { Pagination } from '../components/Pagination';
import { ProviderToggle } from '../components/ProviderToggle';
import { RepositoryCard } from '../components/RepositoryCard';
import { useAsync } from '../hooks/useAsync';
import type { ScmProvider } from '../types';

const PER_PAGE = 30;

const PROVIDER_LABEL: Record<ScmProvider, string> = {
  github: 'GitHub \u00b7 live feed',
  gitlab: 'GitLab \u00b7 live feed',
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

  const list = repositories.data;
  const count = list?.repositories.length ?? 0;

  return (
    <PageContainer className="space-y-6">
      <PageHeader
        eyebrow={
          <>
            <span aria-hidden className="h-px w-8 bg-indigo-400/60" />
            {PROVIDER_LABEL[provider]}
          </>
        }
        title="Repositories"
        description={`Connected ${provider === 'github' ? 'GitHub' : 'GitLab'} repositories available for AI review.`}
        actions={<ProviderToggle value={provider} onChange={handleProviderChange} />}
      />

      {repositories.loading ? (
        <LoadingState label="Loading repositories…" />
      ) : repositories.error || !list ? (
        <ErrorState
          title="Could not load repositories"
          message={repositories.error ?? undefined}
          retry={repositories.refetch}
        />
      ) : list.repositories.length === 0 ? (
        <EmptyState
          title="No repositories found"
          description={`Make sure your ${provider === 'github' ? 'GitHub' : 'GitLab'} account has access to repositories.`}
        />
      ) : (
        <>
          <div className="flex items-center justify-between gap-3 border-b border-white/[0.06] pb-3">
            <span className="eyebrow">Connected repositories</span>
            <span className="font-mono text-[11.5px] tabular-nums text-ink-faint">
              page {page} \u00b7 {count} on screen
            </span>
          </div>

          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
            {list.repositories.map((repo) => (
              <RepositoryCard
                key={repo.full_name}
                repository={repo}
                onClick={() =>
                  navigate(
                    `/repositories/${encodeURIComponent(repo.owner ?? '')}/${encodeURIComponent(repo.name)}${provider === 'gitlab' ? '?provider=gitlab' : ''}`,
                  )
                }
              />
            ))}
          </div>

          <Pagination
            page={page}
            perPage={PER_PAGE}
            hasMore={list.has_more}
            onPageChange={setPage}
          />
        </>
      )}
    </PageContainer>
  );
}
