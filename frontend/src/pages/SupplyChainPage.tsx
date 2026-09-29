import { useSearchParams } from 'react-router-dom';

import { getRepositoryMetrics } from '../api/dashboard';
import { RepositorySupplyChainPanel } from '../components/supply-chain/RepositorySupplyChainPanel';
import { Card, CardBody } from '../components/ui/Card';
import { ErrorState } from '../components/ErrorState';
import { PageContainer } from '../components/PageContainer';
import { PageHeader } from '../components/PageHeader';
import { PageSkeleton } from '../components/ui/Skeleton';
import { useAsync } from '../hooks/useAsync';
import type { ScmProvider } from '../types';

/**
 * Dependency inventory, licence posture and reproducibility measured from a
 * repository's own manifests and lockfiles.
 *
 * This is a different question from the dependency inspector, which lists what
 * the project declares. Supply Chain reads both manifests and lockfiles, so it
 * can tell you which dependencies arrived transitively, whether the build is
 * reproducible, and what licences are actually declared. No registry or advisory
 * feed is consulted, so nothing here accounts for a known vulnerability or for
 * how old a version is — that is the security scan's job.
 */
export function SupplyChainPage() {
  const metrics = useAsync(() => getRepositoryMetrics(1, 50), []);
  const [searchParams] = useSearchParams();
  const provider: ScmProvider = searchParams.get('provider') === 'gitlab' ? 'gitlab' : 'github';

  if (metrics.loading) {
    return (
      <PageContainer>
        <PageSkeleton label="Loading supply chain view" />
      </PageContainer>
    );
  }

  if (metrics.error) {
    return (
      <ErrorState
        title="Could not load the supply chain view"
        message={metrics.error ?? undefined}
        retry={metrics.refetch}
      />
    );
  }

  const repos = metrics.data?.repositories ?? [];

  return (
    <PageContainer className="space-y-6">
      <PageHeader
        eyebrow="Supply Chain"
        title="Dependency & supply chain"
        description="What a repository actually depends on, measured from its own manifests and lockfiles. Direct and transitive packages are separated, pinning and licences are read from the files, and a hygiene score is presented with every deduction itemised — no registry or advisory feed is consulted."
      />

      <Card tone="flat">
        <CardBody>
          <dl className="grid grid-cols-1 gap-4 text-[12px] sm:grid-cols-3">
            <div>
              <dt className="text-[11px] uppercase tracking-wide text-ink-subtle">Manifests & lockfiles</dt>
              <dd className="mt-1 leading-relaxed text-ink-faint">
                package.json, package-lock.json, requirements.txt, pyproject.toml, go.mod,
                go.sum, pom.xml, Cargo.lock, yarn.lock, poetry.lock, uv.lock and more —
                read directly from the repository tree.
              </dd>
            </div>
            <div>
              <dt className="text-[11px] uppercase tracking-wide text-ink-subtle">Transitive split</dt>
              <dd className="mt-1 leading-relaxed text-ink-faint">
                Packages that appear only in a lockfile are marked transitive; packages
                declared in a manifest are direct. Without a lockfile the distinction
                cannot be made from the repository.
              </dd>
            </div>
            <div>
              <dt className="text-[11px] uppercase tracking-wide text-ink-subtle">Hygiene score</dt>
              <dd className="mt-1 leading-relaxed text-ink-faint">
                0&ndash;100, auditable. Deductions for unpinned ranges, VCS sources,
                missing licences, missing lockfiles and strong copyleft. No CVE data
                is factored in — see the security scan for that.
              </dd>
            </div>
          </dl>
        </CardBody>
      </Card>

      <RepositorySupplyChainPanel
        options={repos.map((repo) => ({ owner: repo.owner, repository: repo.repository }))}
        provider={provider}
      />
    </PageContainer>
  );
}