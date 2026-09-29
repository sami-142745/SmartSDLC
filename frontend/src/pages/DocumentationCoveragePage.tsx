import { useSearchParams } from 'react-router-dom';

import { getRepositoryMetrics } from '../api/dashboard';
import { RepositoryDocumentationPanel } from '../components/documentation/RepositoryDocumentationPanel';
import { Card, CardBody } from '../components/ui/Card';
import { ErrorState } from '../components/ErrorState';
import { PageContainer } from '../components/PageContainer';
import { PageHeader } from '../components/PageHeader';
import { PageSkeleton } from '../components/ui/Skeleton';
import { useAsync } from '../hooks/useAsync';
import type { ScmProvider } from '../types';

/**
 * Documentation coverage measured from a repository's own files.
 *
 * This is a different question from `/documents`, which shows documentation this
 * platform generated. Nothing on this page is model-written: the score comes from
 * files that are already in the repository, so it is reproducible and every gap
 * names the observation behind it.
 */
export function DocumentationCoveragePage() {
  const metrics = useAsync(() => getRepositoryMetrics(1, 50), []);
  const [searchParams] = useSearchParams();
  const provider: ScmProvider = searchParams.get('provider') === 'gitlab' ? 'gitlab' : 'github';

  if (metrics.loading) {
    return (
      <PageContainer>
        <PageSkeleton label="Loading documentation coverage" />
      </PageContainer>
    );
  }

  if (metrics.error) {
    return (
      <ErrorState
        title="Could not load the documentation coverage view"
        message={metrics.error ?? undefined}
        retry={metrics.refetch}
      />
    );
  }

  const repos = metrics.data?.repositories ?? [];

  return (
    <PageContainer className="space-y-6">
      <PageHeader
        eyebrow="Coverage"
        title="Documentation coverage"
        description="How completely a repository documents itself, measured from its own files — no model is involved, so every gap can be checked against the file that produced it."
      />

      <Card tone="flat">
        <CardBody>
          <dl className="grid grid-cols-1 gap-4 text-[12px] sm:grid-cols-3">
            <div>
              <dt className="text-[11px] uppercase tracking-wide text-ink-subtle">Canonical files</dt>
              <dd className="mt-1 leading-relaxed text-ink-faint">
                README, LICENSE, CHANGELOG, CONTRIBUTING and SECURITY, detected by path.
              </dd>
            </div>
            <div>
              <dt className="text-[11px] uppercase tracking-wide text-ink-subtle">README structure</dt>
              <dd className="mt-1 leading-relaxed text-ink-faint">
                Headings, code blocks, images and links parsed from the file itself.
              </dd>
            </div>
            <div>
              <dt className="text-[11px] uppercase tracking-wide text-ink-subtle">Docstrings</dt>
              <dd className="mt-1 leading-relaxed text-ink-faint">
                Public Python, JavaScript and TypeScript symbols checked for a preceding
                docstring.
              </dd>
            </div>
          </dl>
        </CardBody>
      </Card>

      <RepositoryDocumentationPanel
        options={repos.map((repo) => ({ owner: repo.owner, repository: repo.repository }))}
        provider={provider}
      />
    </PageContainer>
  );
}
