import { getRepositoryReadme } from '../api/repositoryIntelligence';
import { PageContainer } from '../components/PageContainer';
import { PageHeader } from '../components/PageHeader';
import { ErrorState } from '../components/ErrorState';
import { PageSkeleton } from '../components/ui/Skeleton';
import { ReadmePanel } from '../components/repository/ReadmePanel';
import { RepositorySubnav } from '../components/repository/RepositorySubnav';
import { useRepositoryScope } from '../components/repository/useRepositoryScope';
import { useAsync } from '../hooks/useAsync';

export function RepositoryReadmePage() {
  const { owner, repository, provider, resolved } = useRepositoryScope();

  const readme = useAsync(
    async () => (resolved ? getRepositoryReadme(owner, repository, { provider }) : null),
    [owner, repository, provider, resolved],
  );

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
        description="Structure, coverage and media inventory for the project's README."
      />

      <RepositorySubnav owner={owner} repository={repository} provider={provider} />

      {!resolved ? (
        <ErrorState
          title="No repository selected"
          message="Open a repository from the intelligence index to read its README."
        />
      ) : readme.loading ? (
        <PageSkeleton label="Loading README analysis" />
      ) : readme.error || !readme.data ? (
        <ErrorState
          title="Could not analyse the README"
          message={readme.error ?? undefined}
          retry={readme.refetch}
        />
      ) : (
        <ReadmePanel readme={readme.data} />
      )}
    </PageContainer>
  );
}
