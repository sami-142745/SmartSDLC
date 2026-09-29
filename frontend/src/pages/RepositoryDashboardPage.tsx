import { useState } from 'react';

import {
  getRepositoryDashboard,
  invalidateRepositoryCache,
} from '../api/repositoryIntelligence';
import { PageContainer } from '../components/PageContainer';
import { PageHeader } from '../components/PageHeader';
import { ErrorState } from '../components/ErrorState';
import { PageSkeleton } from '../components/ui/Skeleton';
import { Card, CardBody, CardHeader, InlineStat } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { HealthPanel } from '../components/repository/HealthPanel';
import { LanguagePanel } from '../components/repository/LanguagePanel';
import { DependencyTable } from '../components/repository/DependencyTable';
import { ReadmePanel } from '../components/repository/ReadmePanel';
import { RepositorySubnav } from '../components/repository/RepositorySubnav';
import { useRepositoryScope } from '../components/repository/useRepositoryScope';
import { formatBytes } from '../components/repository/languageColor';
import { useAsync } from '../hooks/useAsync';

export function RepositoryDashboardPage() {
  const { owner, repository, provider, resolved } = useRepositoryScope();
  const [refresh, setRefresh] = useState(false);

  const dashboard = useAsync(
    // Guarded so a half-resolved route never issues a request with an empty
    // path segment; the null resolves immediately and is never rendered.
    async () => (resolved ? getRepositoryDashboard(owner, repository, { provider, refresh }) : null),
    [owner, repository, provider, refresh, resolved],
  );

  // `refresh` is a sticky one-way switch: once the user asks for a fresh
  // analysis every later reload also bypasses the cache, which is what they
  // asked for. Flipping it back would issue a second, redundant request.
  const onRefresh = () => setRefresh(true);

  const onInvalidate = async () => {
    await invalidateRepositoryCache(owner, repository).catch(() => undefined);
    dashboard.refetch();
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
        description={
          dashboard.data?.profile.description ??
          'Health, composition, dependency risk and documentation structure in one view.'
        }
        actions={
          <>
            <Button size="sm" variant="secondary" onClick={onRefresh} loading={dashboard.loading}>
              Refresh
            </Button>
            <Button size="sm" variant="ghost" onClick={onInvalidate}>
              Clear cache
            </Button>
          </>
        }
      />

      <RepositorySubnav owner={owner} repository={repository} provider={provider} />

      {!resolved ? (
        <ErrorState
          title="No repository selected"
          message="Open a repository from the intelligence index to analyse it."
        />
      ) : dashboard.loading ? (
        <PageSkeleton label="Loading repository analysis" />
      ) : dashboard.error || !dashboard.data ? (
        <ErrorState
          title="Could not analyse this repository"
          message={dashboard.error ?? undefined}
          retry={dashboard.refetch}
        />
      ) : (
        <div className="space-y-4">
          <Card tone="flat">
            <CardBody>
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
                <InlineStat label="Stars" value={dashboard.data.profile.stars.toLocaleString()} />
                <InlineStat label="Forks" value={dashboard.data.profile.forks.toLocaleString()} />
                <InlineStat
                  label="Open issues"
                  value={dashboard.data.profile.open_issues.toLocaleString()}
                />
                <InlineStat label="Size" value={formatBytes(dashboard.data.profile.size_kb * 1024)} />
                <InlineStat
                  label="Default branch"
                  value={dashboard.data.profile.default_branch ?? '—'}
                />
                <InlineStat label="License" value={dashboard.data.profile.license_name ?? 'None'} />
              </div>

              <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-white/[0.06] pt-4">
                {dashboard.data.profile.archived ? (
                  <Badge tone="warning" dot>
                    Archived
                  </Badge>
                ) : null}
                {dashboard.data.profile.is_fork ? <Badge tone="neutral">Fork</Badge> : null}
                {dashboard.data.profile.private ? <Badge tone="warning">Private</Badge> : null}
                {dashboard.data.profile.primary_language ? (
                  <Badge tone="info">{dashboard.data.profile.primary_language}</Badge>
                ) : null}
                {dashboard.data.profile.topics.slice(0, 8).map((topic) => (
                  <Badge key={topic} tone="neutral">
                    {topic}
                  </Badge>
                ))}
                {dashboard.data.cached ? <Badge tone="neutral">Served from cache</Badge> : null}
              </div>
            </CardBody>
          </Card>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
            <HealthPanel health={dashboard.data.health} />
            <LanguagePanel languages={dashboard.data.languages} />
          </div>

          <ReadmePanel readme={dashboard.data.readme} />

          <DependencyTable report={dashboard.data.dependencies} />
        </div>
      )}
    </PageContainer>
  );
}
