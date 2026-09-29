import { useSearchParams } from 'react-router-dom';

import { getRepositoryMetrics } from '../api/dashboard';
import { RepositoryTestGenerationPanel } from '../components/test-generation/RepositoryTestGenerationPanel';
import { Card, CardBody } from '../components/ui/Card';
import { ErrorState } from '../components/ErrorState';
import { PageContainer } from '../components/PageContainer';
import { PageHeader } from '../components/PageHeader';
import { PageSkeleton } from '../components/ui/Skeleton';
import { useAsync } from '../hooks/useAsync';
import type { ScmProvider } from '../types';

/**
 * Proposed tests for the gaps a repository's own suite does not cover.
 *
 * What the page is careful about: the choice of what to test is made by
 * measurement, only the body of each test is written by a model, and nothing
 * here is executed or written back to the repository. The three points are
 * stated on screen because a reader who assumes a proposed file is a passing
 * test has misread the artifact.
 */
export function TestGeneratorPage() {
  const metrics = useAsync(() => getRepositoryMetrics(1, 50), []);
  const [searchParams] = useSearchParams();
  const provider: ScmProvider = searchParams.get('provider') === 'gitlab' ? 'gitlab' : 'github';

  if (metrics.loading) {
    return (
      <PageContainer>
        <PageSkeleton label="Loading test generation" />
      </PageContainer>
    );
  }

  if (metrics.error) {
    return (
      <ErrorState
        title="Could not load the test generation view"
        message={metrics.error ?? undefined}
        retry={metrics.refetch}
      />
    );
  }

  const repos = metrics.data?.repositories ?? [];

  return (
    <PageContainer className="space-y-6">
      <PageHeader
        eyebrow="Quality"
        title="Test generator"
        description="Proposes tests for public symbols no test file references. Targets are chosen by measurement, only each test body is written by a model, and nothing is executed or written back."
      />

      <Card tone="flat">
        <CardBody>
          <dl className="grid grid-cols-1 gap-4 text-[12px] sm:grid-cols-3">
            <div>
              <dt className="text-[11px] uppercase tracking-wide text-ink-subtle">Target selection</dt>
              <dd className="mt-1 leading-relaxed text-ink-faint">
                Deterministic. Public Python, JavaScript and TypeScript symbols are matched
                against the repository&apos;s own test files by name.
              </dd>
            </div>
            <div>
              <dt className="text-[11px] uppercase tracking-wide text-ink-subtle">Test bodies</dt>
              <dd className="mt-1 leading-relaxed text-ink-faint">
                Written by a model, then re-parsed and screened for syntax, forbidden imports
                and calls, and leaked secrets. Nothing generated is ever run.
              </dd>
            </div>
            <div>
              <dt className="text-[11px] uppercase tracking-wide text-ink-subtle">Output</dt>
              <dd className="mt-1 leading-relaxed text-ink-faint">
                A preview held for review. There is no route that commits, pushes or opens a
                pull request, so applying a proposal is a separate, deliberate action.
              </dd>
            </div>
          </dl>
        </CardBody>
      </Card>

      <RepositoryTestGenerationPanel
        options={repos.map((repo) => ({ owner: repo.owner, repository: repo.repository }))}
        provider={provider}
      />
    </PageContainer>
  );
}
