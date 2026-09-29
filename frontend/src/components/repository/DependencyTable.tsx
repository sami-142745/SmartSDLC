import { useMemo, useState } from 'react';

import { Card, CardBody, CardHeader } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { EmptyState } from '../EmptyState';
import { cn } from '../../lib/cn';
import type { Dependency, DependencyReport, DependencyRisk } from '../../types';

/** Plain-language explanations for each risk the backend can report. */
const RISK_COPY: Record<DependencyRisk, { label: string; tone: 'danger' | 'warning' | 'info' | 'neutral'; hint: string }> = {
  unpinned: {
    label: 'Unpinned',
    tone: 'warning',
    hint: 'No version constraint, so the resolved version can change without a commit.',
  },
  floating_version: {
    label: 'Floating range',
    tone: 'warning',
    hint: 'A range such as ^ or >= allows versions other than the one installed today.',
  },
  git_source: {
    label: 'Git source',
    tone: 'info',
    hint: 'Installed from a repository rather than a published package.',
  },
  local_path: {
    label: 'Local path',
    tone: 'neutral',
    hint: 'Resolved from the filesystem, so it only builds inside this repository.',
  },
  known_risk: {
    label: 'Known risk',
    tone: 'danger',
    hint: 'Matches a curated list of packages with published advisories.',
  },
  missing_version: {
    label: 'No version',
    tone: 'warning',
    hint: 'Declared without any resolvable version.',
  },
};

type Filter = 'all' | 'flagged' | 'pinned' | 'floating';

const FILTERS: { key: Filter; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'flagged', label: 'Flagged' },
  { key: 'floating', label: 'Not pinned' },
  { key: 'pinned', label: 'Pinned' },
];

function matches(dependency: Dependency, filter: Filter): boolean {
  if (filter === 'all') return true;
  if (filter === 'flagged') return dependency.risks.length > 0;
  if (filter === 'pinned') return dependency.pinned;
  return !dependency.pinned;
}

export function DependencyTable({
  report,
  className,
}: {
  report: DependencyReport;
  className?: string;
}) {
  const [filter, setFilter] = useState<Filter>('all');
  const [ecosystem, setEcosystem] = useState<string>('all');

  const visible = useMemo(
    () =>
      report.dependencies.filter(
        (dependency) =>
          matches(dependency, filter) &&
          (ecosystem === 'all' || dependency.ecosystem === ecosystem),
      ),
    [report.dependencies, filter, ecosystem],
  );

  return (
    <Card className={className}>
      <CardHeader
        title="Dependencies"
        description={`${report.total} declared · ${report.flagged_count} flagged`}
        actions={
          <div
            className="flex w-fit items-center rounded-lg border border-white/[0.06] bg-surface-1 p-0.5"
            role="group"
            aria-label="Filter dependencies"
          >
            {FILTERS.map((option) => (
              <button
                key={option.key}
                type="button"
                aria-pressed={filter === option.key}
                onClick={() => setFilter(option.key)}
                className={cn(
                  'rounded-md px-3 py-1.5 text-[12px] font-medium transition-colors duration-150',
                  filter === option.key
                    ? 'bg-white/[0.07] text-ink'
                    : 'text-ink-subtle hover:text-ink-muted',
                )}
              >
                {option.label}
              </button>
            ))}
          </div>
        }
      />
      <CardBody>
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <Badge tone="neutral" dot>
            {report.ecosystems.length > 0 ? report.ecosystems.join(' · ') : 'No ecosystem detected'}
          </Badge>
          {report.ecosystems.length > 1 ? (
            <div className="flex items-center gap-1.5">
              <Button
                size="sm"
                variant={ecosystem === 'all' ? 'primary' : 'ghost'}
                onClick={() => setEcosystem('all')}
              >
                All
              </Button>
              {report.ecosystems.map((name) => (
                <Button
                  key={name}
                  size="sm"
                  variant={ecosystem === name ? 'primary' : 'ghost'}
                  onClick={() => setEcosystem(name)}
                >
                  {name}
                </Button>
              ))}
            </div>
          ) : null}
        </div>

        {visible.length === 0 ? (
          <EmptyState
            title="No dependencies match this filter"
            description={
              report.total === 0
                ? 'No supported manifest was found in this repository.'
                : 'Try a different filter to see the remaining declarations.'
            }
          />
        ) : (
          <div className="t-table-wrap">
            <table className="t-table">
              <thead>
                <tr className="t-table-head">
                  <th className="t-table-th">Package</th>
                  <th className="t-table-th">Version</th>
                  <th className="t-table-th">Scope</th>
                  <th className="t-table-th">Manifest</th>
                  <th className="t-table-th">Risk</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((dependency) => (
                  <tr key={`${dependency.ecosystem}:${dependency.manifest}:${dependency.name}`}>
                    <td className="t-table-td font-mono text-[12px] text-ink">
                      {dependency.name}
                    </td>
                    <td className="t-table-td font-mono text-[12px] text-ink-muted">
                      {dependency.version ?? <span className="text-ink-faint">—</span>}
                    </td>
                    <td className="t-table-td">
                      <span className="text-[12px] text-ink-subtle">{dependency.scope}</span>
                    </td>
                    <td className="t-table-td">
                      <span className="font-mono text-[11px] text-ink-faint">
                        {dependency.manifest}
                      </span>
                    </td>
                    <td className="t-table-td">
                      {dependency.risks.length === 0 ? (
                        <Badge tone="success" dot>
                          Pinned
                        </Badge>
                      ) : (
                        <span className="flex flex-wrap gap-1">
                          {dependency.risks.map((risk) => (
                            <Badge key={risk} tone={RISK_COPY[risk]?.tone ?? 'neutral'} title={RISK_COPY[risk]?.hint}>
                              {RISK_COPY[risk]?.label ?? risk}
                            </Badge>
                          ))}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {report.manifests.length > 0 ? (
          <div className="mt-5 border-t border-white/[0.06] pt-4">
            <p className="eyebrow">Manifests probed</p>
            <ul className="mt-2 flex flex-wrap gap-2">
              {report.manifests.map((manifest) => (
                <li key={manifest.path}>
                  <Badge tone={manifest.found ? 'info' : 'neutral'} title={manifest.reason ?? undefined}>
                    {manifest.path}
                    {manifest.found ? '' : ' · not found'}
                  </Badge>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </CardBody>
    </Card>
  );
}
