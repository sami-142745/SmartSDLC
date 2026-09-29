import { useState } from 'react';

import { getRepositoryFile, getRepositoryTree } from '../api/repositoryIntelligence';
import { PageContainer } from '../components/PageContainer';
import { PageHeader } from '../components/PageHeader';
import { ErrorState } from '../components/ErrorState';
import { PageSkeleton } from '../components/ui/Skeleton';
import { RepositorySubnav } from '../components/repository/RepositorySubnav';
import { RepositoryTreeView } from '../components/repository/RepositoryTreeView';
import { SourceFileViewer } from '../components/repository/SourceFileViewer';
import { useRepositoryScope } from '../components/repository/useRepositoryScope';
import { useAsync } from '../hooks/useAsync';
import type { RepositoryFileContent } from '../types';

export function RepositoryExplorerPage() {
  const { owner, repository, provider, resolved } = useRepositoryScope();
  const [selected, setSelected] = useState<RepositoryFileContent | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [loadingPath, setLoadingPath] = useState<string | null>(null);

  const tree = useAsync(
    async () => (resolved ? getRepositoryTree(owner, repository, { provider }) : null),
    [owner, repository, provider, resolved],
  );

  const onSelect = async (path: string) => {
    setLoadingPath(path);
    setFileError(null);
    try {
      setSelected(await getRepositoryFile(owner, repository, path, { provider }));
    } catch (error) {
      setSelected(null);
      setFileError(
        (error as { message?: string }).message ?? 'Could not load this file from the provider.',
      );
    } finally {
      setLoadingPath(null);
    }
  };

  return (
    <PageContainer className="space-y-6">
      <PageHeader
        eyebrow={
          <>
            <span aria-hidden className="h-px w-8 bg-indigo-400/60" />
            Repository intelligence
          </>
        }
        title={
          <span className="font-mono">
            {owner}/{repository}
          </span>
        }
        description="Browse the repository tree and open any file in a syntax-highlighted viewer."
      />

      <RepositorySubnav owner={owner} repository={repository} provider={provider} />

      {!resolved ? (
        <ErrorState
          title="No repository selected"
          message="Open a repository from the intelligence index to explore it."
        />
      ) : tree.loading ? (
        <PageSkeleton label="Loading repository tree" />
      ) : tree.error || !tree.data ? (
        <ErrorState
          title="Could not load the repository tree"
          message={tree.error ?? undefined}
          retry={tree.refetch}
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
          <RepositoryTreeView
            tree={tree.data}
            selectedPath={selected?.path ?? loadingPath}
            onSelect={(entry) => onSelect(entry.path)}
          />

          {fileError ? (
            <ErrorState title="Could not open this file" message={fileError} />
          ) : selected ? (
            <SourceFileViewer file={selected} onClose={() => setSelected(null)} />
          ) : (
            <div className="flex min-h-[18rem] items-center justify-center rounded-xl border border-dashed border-white/[0.09] bg-surface-1/40 px-6 text-center">
              <p className="max-w-sm text-[13px] leading-relaxed text-ink-subtle">
                Select a file from the tree to read its source. Binary files are reported by size
                rather than rendered.
              </p>
            </div>
          )}
        </div>
      )}
    </PageContainer>
  );
}
