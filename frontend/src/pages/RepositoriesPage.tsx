import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { getRepositories } from '../api/github';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import { Pagination } from '../components/Pagination';
import { RepositoryCard } from '../components/RepositoryCard';
import { useAsync } from '../hooks/useAsync';

const PER_PAGE = 30;

export function RepositoriesPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const repositories = useAsync(() => getRepositories(page, PER_PAGE), [page]);

  if (repositories.loading) return <LoadingState label="Loading repositories…" />;
  if (repositories.error || !repositories.data) {
    return (
      <ErrorState
        title="Could not load repositories"
        message={repositories.error ?? undefined}
        retry={repositories.refetch}
      />
    );
  }

  const { repositories: repos, has_more } = repositories.data;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Repositories</h1>
        <p className="mt-1 text-sm text-slate-500">
          Repositories you have access to on GitHub.
        </p>
      </div>

      {repos.length === 0 ? (
        <EmptyState
          title="No repositories found"
          description="Make sure your GitHub account has access to repositories."
        />
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {repos.map((repo) => (
              <RepositoryCard
                key={repo.full_name}
                repository={repo}
                onClick={() => navigate(`/repositories/${encodeURIComponent(repo.owner ?? '')}/${encodeURIComponent(repo.name)}`)}
              />
            ))}
          </div>
          <Pagination
            page={page}
            perPage={PER_PAGE}
            hasMore={has_more}
            onPageChange={setPage}
          />
        </>
      )}
    </div>
  );
}