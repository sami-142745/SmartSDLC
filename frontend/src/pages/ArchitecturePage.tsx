import { useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

import { getRepositoryMetrics } from '../api/dashboard';
import { getDocumentations } from '../api/documents';
import { getInsights } from '../api/insights';
import { Card, CardBody, CardHeader } from '../components/ui/Card';
import { RepositoryArchitecturePanel } from '../components/architecture/RepositoryArchitecturePanel';
import { MetricCard, MetricGrid } from '../components/MetricCard';
import { ErrorState } from '../components/ErrorState';
import { EmptyState } from '../components/EmptyState';
import { PageContainer } from '../components/PageContainer';
import { PageHeader } from '../components/PageHeader';
import { CategoryBarChart } from '../components/Charts/CategoryBarChart';
import { BarList } from '../components/ui/Charts';
import { PageSkeleton } from '../components/ui/Skeleton';
import { AvatarStack } from '../components/ui/Avatar';
import { Tabs } from '../components/ui/Tabs';
import { useAsync } from '../hooks/useAsync';
import { categoryLabel } from '../utils/severity';
import { formatShortDate } from '../utils/format';
import { cn } from '../lib/cn';
import type { DocumentationListResponse, InsightListResponse, RepoMetricsResponse, ScmProvider } from '../types';

/**
 * The original three views describe the platform's view of the estate. `graph`
 * is the code-level analysis of a single repository's source tree, which is a
 * different question and a different data source.
 */
type Scope = 'inventory' | 'modules' | 'signals' | 'graph';

/**
 * Deterministic radial layout for the topology graph. Position is derived from
 * the index rather than randomised so the graph does not reshuffle on render.
 */
function polarPosition(index: number, total: number, radius: number) {
  const angle = (index / Math.max(total, 1)) * Math.PI * 2 - Math.PI / 2;
  return { x: 160 + Math.cos(angle) * radius, y: 150 + Math.sin(angle) * radius };
}

function TopologyGraph({ metrics }: { metrics: RepoMetricsResponse['repositories'] }) {
  const nodes = useMemo(
    () =>
      metrics.map((repo, index) => ({
        id: `${repo.owner}/${repo.repository}`,
        ...polarPosition(index, metrics.length, 108),
        weight: repo.finding_count,
        critical: repo.critical_count,
        lastSeen: repo.last_review_at,
      })),
    [metrics],
  );

  if (nodes.length === 0) return null;

  const maxWeight = Math.max(...nodes.map((node) => node.weight), 1);

  return (
    <div className="relative">
      <svg
        viewBox="0 0 320 300"
        className="mx-auto h-auto w-full max-w-[420px]"
        role="img"
        aria-label={`Service topology for ${nodes.length} repositories`}
      >
        <defs>
          <radialGradient id="topo-core">
            <stop offset="0%" stopColor="#8B5CF6" stopOpacity="0.85" />
            <stop offset="100%" stopColor="#22D3EE" stopOpacity="0.6" />
          </radialGradient>
        </defs>

        {/* Edges from the hub to each service. */}
        {nodes.map((node) => (
          <line
            key={`edge-${node.id}`}
            x1={160}
            y1={150}
            x2={node.x}
            y2={node.y}
            stroke={node.critical > 0 ? 'rgba(251,113,133,0.35)' : 'rgba(139,92,246,0.22)'}
            strokeWidth={node.critical > 0 ? 1.25 : 1}
            strokeDasharray={node.lastSeen ? undefined : '3 4'}
          />
        ))}

        {/* Hub */}
        <circle cx={160} cy={150} r={26} fill="url(#topo-core)" />
        <text
          x={160}
          y={154}
          textAnchor="middle"
          className="fill-white font-mono text-[10px] font-semibold"
        >
          {nodes.length} svc
        </text>

        {nodes.map((node) => {
          const r = 7 + (node.weight / maxWeight) * 12;
          return (
            <g key={node.id}>
              <circle
                cx={node.x}
                cy={node.y}
                r={r}
                fill={node.critical > 0 ? 'rgba(251,113,133,0.22)' : 'rgba(34,211,238,0.18)'}
                stroke={node.critical > 0 ? '#FB7185' : '#22D3EE'}
                strokeWidth="1.25"
              />
              <title>{`${node.id} — ${node.weight} findings`}</title>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

export function ArchitecturePage() {
  const metrics = useAsync(() => getRepositoryMetrics(1, 50), []);
  const docs = useAsync<DocumentationListResponse>(
    () => getDocumentations({ page: 1, perPage: 25 }),
    [],
  );
  const insights = useAsync<InsightListResponse>(() => getInsights({ page: 1, perPage: 10 }), []);

  const [scope, setScope] = useState<Scope>('inventory');
  const [searchParams] = useSearchParams();
  const provider: ScmProvider = searchParams.get('provider') === 'gitlab' ? 'gitlab' : 'github';

  if (metrics.loading) {
    return (
      <PageContainer>
        <PageSkeleton label="Loading architecture" />
      </PageContainer>
    );
  }

  if (metrics.error) {
    return (
      <ErrorState
        title="Could not load the architecture view"
        message={metrics.error ?? undefined}
        retry={metrics.refetch}
      />
    );
  }

  const repos = metrics.data?.repositories ?? [];
  const totalFindings = repos.reduce((sum, repo) => sum + repo.finding_count, 0);
  const totalReviews = repos.reduce((sum, repo) => sum + repo.review_count, 0);
  const documented = docs.data?.items.filter((doc) => doc.status === 'complete').length ?? 0;

  const byVolume = [...repos]
    .filter((repo) => repo.review_count > 0)
    .map((repo) => ({
      key: `${repo.owner}/${repo.repository}`,
      label: `${repo.owner}/${repo.repository}`,
      value: Number(repo.average_findings_per_review.toFixed(1)),
      color: repo.critical_count > 0 ? '#FB7185' : '#22D3EE',
    }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 10);

  const moduleInventory = (docs.data?.items ?? [])
    .filter((doc) => doc.modules.length > 0)
    .slice(0, 12)
    .map((doc) => ({
      id: doc.id,
      repository: `${doc.source.owner}/${doc.source.repository}`,
      title: doc.title,
      modules: doc.modules,
      architecture: doc.architecture,
      generated: doc.generated_at,
    }));

  const latestInsight = insights.data?.items?.[0] ?? null;
  const categorySignals = latestInsight?.metrics.category_distribution ?? {};

  return (
    <PageContainer className="space-y-6">
      <PageHeader
        eyebrow="Structure"
        title="Architecture"
        description="Service topology, module inventory and the structural signals that predict where defects concentrate."
        actions={
          <Tabs
            aria-label="Architecture scope"
            value={scope}
            onChange={setScope}
            items={[
              { value: 'inventory', label: 'Topology' },
              { value: 'modules', label: 'Modules', count: moduleInventory.length },
              { value: 'signals', label: 'Signals' },
              { value: 'graph', label: 'Code graph' },
            ]}
            size="sm"
          />
        }
      />

      <MetricGrid>
        <MetricCard label="Services" value={repos.length} hint="Reviewed repositories" />
        <MetricCard label="Reviews mapped" value={totalReviews} hint="Across all services" />
        <MetricCard label="Findings mapped" value={totalFindings} hint="Attributed to a service" />
        <MetricCard
          label="Documented"
          value={documented}
          tone={documented > 0 ? 'success' : 'default'}
          hint="Modules extracted"
        />
      </MetricGrid>

      {scope === 'graph' ? (
        <RepositoryArchitecturePanel
          options={repos.map((repo) => ({ owner: repo.owner, repository: repo.repository }))}
          provider={provider}
        />
      ) : null}

      {scope === 'inventory' ? (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader
              title="Service topology"
              description="Node size scales with finding volume; red rings carry critical findings"
            />
            <CardBody>
              {repos.length > 0 ? (
                <TopologyGraph metrics={repos} />
              ) : (
                <EmptyState
                  title="No services mapped yet"
                  description="Review a pull request to build the topology graph."
                />
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="Defect density"
              description="Average findings per review, highest first"
            />
            <CardBody>
              {byVolume.length > 0 ? (
                <BarList data={byVolume} />
              ) : (
                <EmptyState title="No reviewed services yet" />
              )}
            </CardBody>
          </Card>
        </div>
      ) : null}

      {scope === 'modules' ? (
        <Card>
          <CardHeader
            title="Module inventory"
            description="Extracted from generated documentation"
            icon={
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4 w-4" aria-hidden="true">
                <path d="M4 4h6v6H4V4Zm10 0h6v6h-6V4ZM4 14h6v6H4v-6Zm10 0h6v6h-6v-6Z" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            }
          />
          <CardBody>
            {moduleInventory.length === 0 ? (
              <EmptyState
                title="No module inventory yet"
                description="Generate documentation for a repository to extract its module structure."
              />
            ) : (
              <ul className="space-y-2.5">
                {moduleInventory.map((entry) => (
                  <li key={entry.id} className="glass-subtle px-4 py-3.5">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="min-w-0">
                        <p className="truncate text-[13.5px] font-medium text-ink">{entry.title}</p>
                        <p className="mt-0.5 truncate font-mono text-[11px] text-ink-faint">
                          {entry.repository}
                          {entry.generated ? ` \u00b7 ${formatShortDate(entry.generated)}` : ''}
                        </p>
                      </div>
                      <span className="chip shrink-0 border-white/[0.08] bg-white/[0.04] text-ink-subtle">
                        {entry.modules.length} modules
                      </span>
                    </div>
                    <div className="mt-2.5 flex flex-wrap gap-1.5">
                      {entry.modules.slice(0, 12).map((module) => (
                        <span
                          key={module}
                          className="rounded border border-white/[0.06] bg-white/[0.03] px-1.5 py-0.5 font-mono text-[10.5px] text-ink-muted"
                        >
                          {module}
                        </span>
                      ))}
                      {entry.modules.length > 12 ? (
                        <span className="rounded px-1.5 py-0.5 font-mono text-[10.5px] text-ink-faint">
                          +{entry.modules.length - 12} more
                        </span>
                      ) : null}
                    </div>
                    {entry.architecture ? (
                      <p className="mt-2.5 line-clamp-3 text-[12.5px] leading-relaxed text-ink-subtle">
                        {entry.architecture}
                      </p>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>
      ) : null}

      {scope === 'signals' ? (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader
              title="Structural defect signals"
              description={
                latestInsight
                  ? `From the latest insight for ${latestInsight.owner}/${latestInsight.repository}`
                  : 'Requires a generated insight report'
              }
            />
            <CardBody>
              {Object.keys(categorySignals).length > 0 ? (
                <CategoryBarChart data={categorySignals} />
              ) : (
                <EmptyState
                  title="No signals yet"
                  description="Generate an insight report to compute structural defect signals."
                />
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Service registry" description="Review cadence per service" />
            <CardBody>
              {repos.length === 0 ? (
                <EmptyState title="No services registered" />
              ) : (
                <ul className="space-y-1.5">
                  {repos.map((repo) => (
                    <li
                      key={`${repo.owner}/${repo.repository}`}
                      className="flex items-center gap-3 rounded-lg px-2 py-1.5 transition-colors hover:bg-white/[0.03]"
                    >
                      <span
                        aria-hidden
                        className={cn(
                          'h-1.5 w-1.5 shrink-0 rounded-full',
                          repo.critical_count > 0 ? 'bg-rose-400' : 'bg-accent-cyan',
                        )}
                      />
                      <span className="min-w-0 flex-1 truncate font-mono text-[12px] text-ink-muted">
                        {repo.owner}/{repo.repository}
                      </span>
                      <span className="shrink-0 font-mono text-[11px] tabular-nums text-ink-faint">
                        {repo.review_count} reviews
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </CardBody>
          </Card>
        </div>
      ) : null}
    </PageContainer>
  );
}
