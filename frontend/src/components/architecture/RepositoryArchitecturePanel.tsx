import { useMemo, useState } from 'react';

import { getArchitecture } from '../../api/architecture';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { Card, CardBody, CardHeader, InlineStat } from '../ui/Card';
import { EmptyState } from '../EmptyState';
import { ErrorState } from '../ErrorState';
import { PageSkeleton } from '../ui/Skeleton';
import { ArchitectureGraphView, ModuleDetail } from './ArchitectureGraphView';
import {
  KIND_COLOR,
  KIND_LABEL,
  MAX_RENDERED_NODES,
  layoutGraph,
  moduleById,
  rankModules,
} from './graphLayout';
import type { GraphLayout } from './graphLayout';
import { useAsync } from '../../hooks/useAsync';
import { cn } from '../../lib/cn';
import type {
  ArchitectureGraph,
  ArchitectureIssue,
  ArchitectureNodeKind,
  ScmProvider,
} from '../../types';

const KIND_FILTERS: ArchitectureNodeKind[] = [
  'service',
  'route',
  'controller',
  'database',
  'module',
];

export interface RepositoryOption {
  owner: string;
  repository: string;
}

export interface RepositoryArchitecturePanelProps {
  options: RepositoryOption[];
  provider: ScmProvider;
  className?: string;
}

/**
 * Code-level architecture analysis for one repository.
 *
 * The analysis runs entirely on the backend from the fetched source tree; no
 * model is involved, so every number on this screen is reproducible and every
 * claim can be traced to a file. The page states partial coverage explicitly
 * rather than presenting a truncated graph as a complete one.
 */
export function RepositoryArchitecturePanel({
  options,
  provider,
  className,
}: RepositoryArchitecturePanelProps) {
  const [selection, setSelection] = useState<RepositoryOption | null>(options[0] ?? null);
  const [selected, setSelected] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [kinds, setKinds] = useState<ArchitectureNodeKind[]>([]);
  const [refresh, setRefresh] = useState(false);

  const graph = useAsync<ArchitectureGraph | null>(
    async () => {
      if (!selection) return null;
      return getArchitecture(selection.owner, selection.repository, { provider, refresh });
    },
    [selection?.owner, selection?.repository, provider, refresh],
  );

  const layout = useMemo(() => (graph.data ? layoutGraph(graph.data) : null), [graph.data]);
  const ranked = useMemo(
    () => (graph.data ? rankModules(graph.data, { search, kinds }) : []),
    [graph.data, search, kinds],
  );
  const activeNode = useMemo(
    () => (graph.data ? moduleById(graph.data, selected) : null),
    [graph.data, selected],
  );

  const toggleKind = (kind: ArchitectureNodeKind) => {
    setKinds((current) =>
      current.includes(kind) ? current.filter((item) => item !== kind) : [...current, kind],
    );
  };

  if (options.length === 0) {
    return (
      <EmptyState
        title="No repository to analyse"
        description="Analyse a repository from the index once a pull request has been reviewed."
      />
    );
  }

  return (
    <div className={cn('space-y-4', className)}>
      <Card tone="flat">
        <CardBody>
          <div className="flex flex-wrap items-end gap-3">
            <div className="min-w-[220px] flex-1">
              <label htmlFor="architecture-repo" className="text-[11px] uppercase tracking-wide text-ink-subtle">
                Repository
              </label>
              <select
                id="architecture-repo"
                value={selection ? `${selection.owner}/${selection.repository}` : ''}
                onChange={(event) => {
                  const [owner, repository] = event.target.value.split('/');
                  setSelection({ owner, repository });
                  // Clear the selection so a detail panel from the previous
                  // repository cannot be shown against a new graph.
                  setSelected(null);
                }}
                className="mt-1 w-full rounded-lg border border-white/[0.09] bg-surface-2 px-3 py-2 text-[13px] text-ink"
              >
                {options.map((option) => (
                  <option key={`${option.owner}/${option.repository}`} value={`${option.owner}/${option.repository}`}>
                    {option.owner}/{option.repository}
                  </option>
                ))}
              </select>
            </div>

            <label className="min-w-[200px] flex-1">
              <span className="text-[11px] uppercase tracking-wide text-ink-subtle">Search modules</span>
              <input
                type="search"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="path or module id"
                className="mt-1 w-full rounded-lg border border-white/[0.09] bg-surface-2 px-3 py-2 text-[13px] text-ink"
              />
            </label>

            <Button variant="secondary" onClick={() => setRefresh(true)} disabled={graph.loading}>
              {refresh ? 'Refreshed' : 'Re-analyse'}
            </Button>
          </div>

          <div className="mt-3 flex flex-wrap gap-1.5">
            {KIND_FILTERS.map((kind) => {
              const active = kinds.includes(kind);
              return (
                <button
                  key={kind}
                  type="button"
                  onClick={() => toggleKind(kind)}
                  aria-pressed={active}
                  className={cn(
                    'inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-[11px] transition-colors',
                    active
                      ? 'border-white/20 bg-white/[0.08] text-ink'
                      : 'border-white/[0.07] text-ink-subtle hover:bg-white/[0.04]',
                  )}
                >
                  <span
                    aria-hidden
                    className="size-2 rounded-full"
                    style={{ backgroundColor: KIND_COLOR[kind] }}
                  />
                  {KIND_LABEL[kind]}
                </button>
              );
            })}
            {kinds.length > 0 ? (
              <button
                type="button"
                onClick={() => setKinds([])}
                className="rounded-md px-2 py-1 text-[11px] text-ink-faint hover:text-ink-subtle"
              >
                Clear
              </button>
            ) : null}
          </div>
        </CardBody>
      </Card>

      {graph.loading ? (
        <PageSkeleton label="Analysing repository structure" />
      ) : graph.error ? (
        <ErrorState
          title="Could not analyse this repository"
          message={graph.error}
          retry={graph.refetch}
        />
      ) : !graph.data ? null : (
        <ArchitectureReport
          graph={graph.data}
          layout={layout ?? layoutGraph(graph.data)}
          selected={selected}
          onSelect={setSelected}
          ranked={ranked}
          activeNode={activeNode}
        />
      )}
    </div>
  );
}

interface ArchitectureReportProps {
  graph: ArchitectureGraph;
  layout: GraphLayout;
  selected: string | null;
  onSelect: (id: string | null) => void;
  ranked: ReturnType<typeof rankModules>;
  activeNode: ReturnType<typeof moduleById>;
}

function ArchitectureReport({
  graph,
  layout,
  selected,
  onSelect,
  ranked,
  activeNode,
}: ArchitectureReportProps) {
  const { summary } = graph;
  const hidden = Math.max(graph.modules.length - layout.nodes.length, 0);

  if (graph.modules.length === 0) {
    return (
      <EmptyState
        title="No analysable modules"
        description={
          graph.truncated
            ? 'The file limit was reached before any supported source file was found.'
            : 'No supported source files were found in this repository at the analysed ref.'
        }
      />
    );
  }

  return (
    <div className="space-y-4">
      <Card tone="flat">
        <CardBody>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
            <InlineStat label="Modules" value={summary.total_modules} />
            <InlineStat label="Dependencies" value={summary.total_edges} />
            <InlineStat label="Third-party packages" value={summary.external_packages} />
            <InlineStat
              label="Cycles"
              value={summary.cycles ?? 'not computed'}
              tone={summary.cycles ? 'warning' : 'default'}
            />
            <InlineStat
              label="Structural signals"
              value={graph.issues.length}
              tone={graph.issues.length > 0 ? 'warning' : 'default'}
            />
            <InlineStat
              label="Unresolved imports"
              value={summary.unresolved_imports}
              tone={summary.unresolved_imports > 0 ? 'warning' : 'default'}
            />
          </div>

          {/*
            Coverage is stated, not implied. A truncated or partial analysis
            that looks identical to a complete one is how a reviewer ends up
            trusting a graph that never saw most of the repository.
          */}
          {graph.truncated || summary.unresolved_imports > 0 || graph.errors.length > 0 ? (
            <div className="mt-4 space-y-1.5 border-t border-white/[0.06] pt-3 text-[12px] text-ink-subtle">
              {graph.truncated ? (
                <p>
                  Partial analysis: file selection stopped at its limit, so modules
                  outside the cap are not in this graph.
                </p>
              ) : null}
              {summary.unresolved_imports > 0 ? (
                <p>
                  {summary.unresolved_imports} import
                  {summary.unresolved_imports === 1 ? '' : 's'} could not be resolved
                  to a file, so some dependencies are missing.
                </p>
              ) : null}
              {graph.errors.length > 0 ? (
                <p>
                  {graph.errors.length} file{graph.errors.length === 1 ? '' : 's'} could
                  not be read. {graph.errors.slice(0, 2).join(' ')}
                </p>
              ) : null}
            </div>
          ) : null}

          <p className="mt-3 text-[11px] leading-relaxed text-ink-faint">
            {summary.methodology}
          </p>
        </CardBody>
      </Card>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_300px]">
        <Card>
          <CardHeader
            title="Dependency graph"
            description={
              hidden > 0
                ? `Showing the ${layout.nodes.length} most connected of ${graph.modules.length} modules`
                : `${layout.nodes.length} modules`
            }
          />
          <CardBody>
            <ArchitectureGraphView
              graph={graph}
              layout={layout}
              selected={selected}
              onSelect={onSelect}
              issues={graph.issues}
            />
            {hidden > 0 ? (
              <p className="mt-2 text-[11px] text-ink-faint">
                {hidden} further module{hidden === 1 ? '' : 's'} above the{' '}
                {MAX_RENDERED_NODES}-node rendering limit can be found in the module
                list.
              </p>
            ) : null}
          </CardBody>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader title="Selected module" />
            <CardBody>
              <ModuleDetail node={activeNode} graph={graph} issues={graph.issues} />
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="Modules"
              description={ranked.length === 0 ? 'No module matches the filter' : undefined}
            />
            <CardBody padded={false}>
              {ranked.length === 0 ? (
                <p className="px-5 py-4 text-[12px] text-ink-subtle">No match.</p>
              ) : (
                <ul className="max-h-[320px] overflow-y-auto">
                  {ranked.map(({ module }) => {
                    const active = module.id === selected;
                    return (
                      <li key={module.id}>
                        <button
                          type="button"
                          onClick={() => onSelect(active ? null : module.id)}
                          aria-pressed={active}
                          className={cn(
                            'flex w-full items-center gap-2 px-5 py-2 text-left transition-colors',
                            active ? 'bg-white/[0.07]' : 'hover:bg-white/[0.03]',
                          )}
                        >
                          <span
                            aria-hidden
                            className="size-2 shrink-0 rounded-full"
                            style={{ backgroundColor: KIND_COLOR[module.kind] }}
                          />
                          <span className="min-w-0 flex-1 truncate font-mono text-[11.5px] text-ink-muted">
                            {module.id}
                          </span>
                          <span className="shrink-0 font-mono text-[10.5px] tabular-nums text-ink-faint">
                            {module.fan_in}&#8593; {module.fan_out}&#8595;
                          </span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Structural signals" />
            <CardBody>
              {graph.issues.length === 0 ? (
                <p className="text-[12px] text-ink-subtle">
                  No structural signal crossed its threshold in this analysis.
                </p>
              ) : (
                <ul className="space-y-2.5">
                  {graph.issues.map((issue) => (
                    <li key={`${issue.kind}-${issue.title}`}>
                      <div className="flex items-center gap-2">
                        <Badge tone={issue.severity === 'warning' ? 'warning' : 'neutral'}>
                          {issue.title}
                        </Badge>
                      </div>
                      <p className="mt-1 text-[11.5px] leading-relaxed text-ink-subtle">
                        {issue.detail}
                      </p>
                      <div className="mt-1 flex flex-wrap gap-1">
                        {issue.nodes.slice(0, 5).map((id) => (
                          <button
                            key={id}
                            type="button"
                            onClick={() => onSelect(id)}
                            className="rounded border border-white/[0.06] bg-white/[0.03] px-1.5 py-0.5 font-mono text-[10px] text-ink-muted hover:text-ink"
                          >
                            {id}
                          </button>
                        ))}
                        {issue.nodes.length > 5 ? (
                          <span className="px-1 py-0.5 font-mono text-[10px] text-ink-faint">
                            +{issue.nodes.length - 5}
                          </span>
                        ) : null}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </CardBody>
          </Card>
        </div>
      </div>

      {Object.keys(summary.language_distribution).length > 0 ? (
        <Card>
          <CardHeader title="Composition" description="Observed languages and module roles" />
          <CardBody>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <DistributionList
                title="Languages"
                entries={Object.entries(summary.language_distribution)}
                emptyLabel="No language detected"
              />
              <DistributionList
                title="Module roles"
                entries={Object.entries(summary.kind_distribution)}
                emptyLabel="No module roles detected"
              />
            </div>
            {summary.most_depended_on.length > 0 ? (
              <p className="mt-3 text-[12px] text-ink-subtle">
                Most depended on:{' '}
                {summary.most_depended_on.slice(0, 5).join(', ')}
              </p>
            ) : null}
          </CardBody>
        </Card>
      ) : null}
    </div>
  );
}

function DistributionList({
  title,
  entries,
  emptyLabel,
}: {
  title: string;
  entries: [string, number][];
  emptyLabel: string;
}) {
  if (entries.length === 0) {
    return (
      <div>
        <h3 className="text-[11px] uppercase tracking-wide text-ink-subtle">{title}</h3>
        <p className="mt-1 text-[12px] text-ink-faint">{emptyLabel}</p>
      </div>
    );
  }
  const total = entries.reduce((sum, [, count]) => sum + count, 0) || 1;
  return (
    <div>
      <h3 className="text-[11px] uppercase tracking-wide text-ink-subtle">{title}</h3>
      <ul className="mt-2 space-y-1.5">
        {entries.map(([label, count]) => (
          <li key={label} className="flex items-center gap-2 text-[12px]">
            <span className="w-24 shrink-0 truncate text-ink-muted">{label}</span>
            <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/[0.06]">
              <span
                className="block h-full rounded-full bg-accent-violet/70"
                style={{ width: `${Math.max((count / total) * 100, 2)}%` }}
              />
            </span>
            <span className="w-8 shrink-0 text-right font-mono tabular-nums text-ink-faint">
              {count}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export type { ArchitectureIssue };
