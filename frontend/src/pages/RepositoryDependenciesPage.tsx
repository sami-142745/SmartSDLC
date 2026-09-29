import { getRepositoryDependencies } from '../api/repositoryIntelligence';
import { PageContainer } from '../components/PageContainer';
import { PageHeader } from '../components/PageHeader';
import { ErrorState } from '../components/ErrorState';
import { PageSkeleton } from '../components/ui/Skeleton';
import { Card, CardBody } from '../components/ui/Card';
import { InlineStat } from '../components/ui/Card';
import { DependencyTable } from '../components/repository/DependencyTable';
import { RepositorySubnav } from '../components/repository/RepositorySubnav';
import { useRepositoryScope } from '../components/repository/useRepositoryScope';
import { useAsync } from '../hooks/useAsync';

export function RepositoryDependenciesPage() {
  const { owner, repository, provider, resolved } = useRepositoryScope();

  const report = useAsync(
    async () => (resolved ? getRepositoryDependencies(owner, repository, { provider }) : null),
    [owner, repository, provider, resolved],
  );

  const floating = report.data
    ? report.data.dependencies.filter((dependency) => !dependency.pinned).length
    : 0;

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
        description="Every declared dependency across the supported manifests, with pin status and reproducibility risks."
      />

      <RepositorySubnav owner={owner} repository={repository} provider={provider} />

      {!resolved ? (
        <ErrorState
          title="No repository selected"
          message="Open a repository from the intelligence index to inspect its dependencies."
        />
      ) : report.loading ? (
        <PageSkeleton label="Loading dependencies" />
      ) : report.error || !report.data ? (
        <ErrorState
          title="Could not load dependencies"
          message={report.error ?? undefined}
          retry={report.refetch}
        />
      ) : (
        <div className="space-y-4">
          <Card tone="flat">
            <CardBody>
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                <InlineStat label="Declared" value={report.data.total} />
                <InlineStat label="Direct" value={report.data.direct_count} />
                <InlineStat
                  label="Flagged"
                  value={report.data.flagged_count}
                  tone={report.data.flagged_count > 0 ? 'warning' : 'positive'}
                />
                <InlineStat
                  label="Not pinned"
                  value={floating}
                  tone={floating > 0 ? 'warning' : 'positive'}
                />
              </div>
            </CardBody>
          </Card>

          <DependencyTable report={report.data} />
        </div>
      )}
    </PageContainer>
  );
}
