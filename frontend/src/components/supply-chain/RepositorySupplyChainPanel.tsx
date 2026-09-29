import { useMemo, useState } from 'react';

import {
  blockingIssues,
  getSupplyChain,
  isReproducible,
  licenseCategoryLabel,
  licensesInCategory,
  ratioPercent,
} from '../../api/supplyChain';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { Card, CardBody, CardHeader, InlineStat } from '../ui/Card';
import { EmptyState } from '../EmptyState';
import { ErrorState } from '../ErrorState';
import { PageSkeleton } from '../ui/Skeleton';
import { useAsync } from '../../hooks/useAsync';
import { cn } from '../../lib/cn';
import type {
  LicenseCategory,
  ScmProvider,
  SupplyChainReport,
  SupplyChainSeverity,
} from '../../types';

const SEVERITY_FILTERS: (SupplyChainSeverity | 'all')[] = [
  'all',
  'critical',
  'high',
  'medium',
  'low',
  'info',
];

const BAND_LABEL: Record<SupplyChainReport['summary']['score_band'], string> = {
  strong: 'Well governed',
  fair: 'Mostly governed',
  weak: 'Loosely governed',
  critical: 'Ungoverned',
};

const SEVERITY_TONE: Record<SupplyChainSeverity, 'warning' | 'neutral'> = {
  critical: 'warning',
  high: 'warning',
  medium: 'warning',
  low: 'neutral',
  info: 'neutral',
};

/** Licence categories a reader should look at, worst posture first. */
const LICENCE_ORDER: LicenseCategory[] = [
  'strong_copyleft',
  'proprietary',
  'weak_copyleft',
  'unknown',
  'permissive',
  'public_domain',
];

export interface SupplyChainRepositoryOption {
  owner: string;
  repository: string;
}

export interface RepositorySupplyChainPanelProps {
  options: SupplyChainRepositoryOption[];
  provider: ScmProvider;
  className?: string;
}

/**
 * Supply-chain hygiene for one repository.
 *
 * No model is involved: the backend reads only the repository's own manifests and
 * lockfiles, so every number here is reproducible and every issue names the file
 * and line behind it. The panel is explicit about the limits of that: an unknown
 * licence is shown as unknown rather than folded into "permissive", a project with
 * no lockfile is called unreproducible, and a hygiene score is never presented as
 * a vulnerability verdict - known CVEs belong to the security engine.
 */
export function RepositorySupplyChainPanel({
  options,
  provider,
  className,
}: RepositorySupplyChainPanelProps) {
  const [selection, setSelection] = useState<SupplyChainRepositoryOption | null>(
    options[0] ?? null,
  );
  const [severity, setSeverity] = useState<SupplyChainSeverity | 'all'>('all');
  const [search, setSearch] = useState('');
  const [refresh, setRefresh] = useState(false);

  const report = useAsync<SupplyChainReport | null>(
    async () => {
      if (!selection) return null;
      return getSupplyChain(selection.owner, selection.repository, { provider, refresh });
    },
    [selection?.owner, selection?.repository, provider, refresh],
  );

  const visibleIssues = useMemo(() => {
    const issues = report.data?.issues ?? [];
    return severity === 'all' ? issues : issues.filter((issue) => issue.severity === severity);
  }, [report.data, severity]);

  const visibleDependencies = useMemo(() => {
    const dependencies = report.data?.dependencies ?? [];
    if (!search.trim()) return dependencies;
    const needle = search.trim().toLowerCase();
    return dependencies.filter(
      (dependency) =>
        dependency.name.toLowerCase().includes(needle) ||
        (dependency.license_expression ?? '').toLowerCase().includes(needle),
    );
  }, [report.data, search]);

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
              <label htmlFor="supply-chain-repo" className="text-[11px] uppercase tracking-wide text-ink-subtle">
                Repository
              </label>
              <select
                id="supply-chain-repo"
                value={selection ? `${selection.owner}/${selection.repository}` : ''}
                onChange={(event) => {
                  const [owner, repository] = event.target.value.split('/');
                  setSelection({ owner, repository });
                }}
                className="mt-1 w-full rounded-lg border border-white/[0.09] bg-surface-2 px-3 py-2 text-[13px] text-ink"
              >
                {options.map((option) => (
                  <option
                    key={`${option.owner}/${option.repository}`}
                    value={`${option.owner}/${option.repository}`}
                  >
                    {option.owner}/{option.repository}
                  </option>
                ))}
              </select>
            </div>

            <label className="min-w-[200px] flex-1">
              <span className="text-[11px] uppercase tracking-wide text-ink-subtle">
                Search dependencies
              </span>
              <input
                type="search"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="name or licence"
                className="mt-1 w-full rounded-lg border border-white/[0.09] bg-surface-2 px-3 py-2 text-[13px] text-ink"
              />
            </label>

            <Button variant="secondary" onClick={() => setRefresh(true)} disabled={report.loading}>
              {refresh ? 'Refreshed' : 'Re-analyse'}
            </Button>
          </div>
        </CardBody>
      </Card>

      {report.loading ? (
        <PageSkeleton label="Reading dependency manifests" />
      ) : report.error ? (
        <ErrorState
          title="Could not read this repository's supply chain"
          message={report.error}
          retry={report.refetch}
        />
      ) : !report.data ? null : (
        <SupplyChainReportView
          report={report.data}
          severity={severity}
          onSeverity={setSeverity}
          visibleIssues={visibleIssues}
          visibleDependencies={visibleDependencies}
        />
      )}
    </div>
  );
}

interface SupplyChainReportViewProps {
  report: SupplyChainReport;
  severity: SupplyChainSeverity | 'all';
  onSeverity: (value: SupplyChainSeverity | 'all') => void;
  visibleIssues: SupplyChainReport['issues'];
  visibleDependencies: SupplyChainReport['dependencies'];
}

function SupplyChainReportView({
  report,
  severity,
  onSeverity,
  visibleIssues,
  visibleDependencies,
}: SupplyChainReportViewProps) {
  const { summary } = report;
  const blocking = blockingIssues(report).length;
  const reproducible = isReproducible(report);

  return (
    <div className="space-y-4">
      <Card tone="flat">
        <CardBody>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
            <InlineStat
              label="Hygiene score"
              value={`${summary.hygiene_score}/100`}
              tone={summary.hygiene_score < 80 ? 'warning' : 'default'}
            />
            <InlineStat label="Verdict" value={BAND_LABEL[summary.score_band]} />
            <InlineStat label="Dependencies" value={summary.total_dependencies} />
            <InlineStat
              label="Direct / inherited"
              value={`${summary.direct_dependencies} / ${summary.transitive_dependencies}`}
            />
            <InlineStat
              label="Pinned"
              value={`${ratioPercent(summary.pinned_ratio)}%`}
              tone={summary.pinned_ratio < 1 ? 'warning' : 'default'}
            />
            <InlineStat
              label="Licence declared"
              value={`${ratioPercent(summary.license_coverage_ratio)}%`}
              tone={summary.license_coverage_ratio < 0.5 ? 'warning' : 'default'}
            />
          </div>

          {/*
            The conditions under which the numbers above should not be read at
            face value are stated on screen. A truncated inventory, an unreadable
            manifest, or a project with no manifest at all all change what the
            totals mean, and silently showing a confident-looking number would be
            worse than showing nothing.
          */}
          {report.truncated || report.errors.length > 0 || summary.manifest_count === 0 ? (
            <div className="mt-4 space-y-1.5 border-t border-white/[0.06] pt-3 text-[12px] text-ink-subtle">
              {report.truncated ? (
                <p>
                  Partial inventory: the dependency cap was reached, so packages
                  beyond it are not represented in these totals.
                </p>
              ) : null}
              {report.errors.length > 0 ? (
                <p>
                  {report.errors.length} file{report.errors.length === 1 ? '' : 's'} could
                  not be read. {report.errors.slice(0, 2).join(' ')}
                </p>
              ) : null}
              {summary.manifest_count === 0 ? (
                <p>
                  No dependency manifest was found, so these totals describe a
                  project that declares no external dependencies.
                </p>
              ) : null}
            </div>
          ) : null}

          {!reproducible && summary.manifest_count > 0 ? (
            <p className="mt-3 text-[12px] text-amber-300">
              No lockfile is committed, so installs are not reproducible from this
              repository alone.
            </p>
          ) : null}

          <p className="mt-3 text-[11px] leading-relaxed text-ink-faint">
            Measured from the manifests and lockfiles in this repository. No registry
            or advisory feed is consulted, so nothing here accounts for a known
            vulnerability or for how old a version is - see the security scan for
            that.
            {summary.declared_license
              ? ` This project declares its own licence as ${summary.declared_license}.`
              : ' This project does not declare its own licence in a form this report can read.'}
          </p>
        </CardBody>
      </Card>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
        <Card>
          <CardHeader
            title="Supply-chain issues"
            description={
              blocking > 0
                ? `${blocking} high or critical`
                : 'No high or critical issues'
            }
            actions={
              <div className="flex gap-1.5">
                {SEVERITY_FILTERS.map((option) => (
                  <button
                    key={option}
                    type="button"
                    onClick={() => onSeverity(option)}
                    aria-pressed={severity === option}
                    className={cn(
                      'rounded-md border px-2 py-1 text-[11px] transition-colors',
                      severity === option
                        ? 'border-white/20 bg-white/[0.08] text-ink'
                        : 'border-white/[0.07] text-ink-subtle hover:bg-white/[0.04]',
                    )}
                  >
                    {option}
                  </button>
                ))}
              </div>
            }
          />
          <CardBody>
            {visibleIssues.length === 0 ? (
              <p className="text-[12px] text-ink-subtle">
                {report.issues.length === 0
                  ? 'No supply-chain issue crossed its threshold in this analysis.'
                  : 'No issue matches this filter.'}
              </p>
            ) : (
              <ul className="space-y-3">
                {visibleIssues.map((issue) => (
                  <li key={`${issue.code}-${issue.title}`}>
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone={SEVERITY_TONE[issue.severity]}>{issue.severity}</Badge>
                      <span className="text-[12px] text-ink">{issue.title}</span>
                    </div>
                    <p className="mt-1 text-[11.5px] leading-relaxed text-ink-subtle">
                      {issue.detail}
                    </p>
                    <p className="mt-0.5 text-[11.5px] leading-relaxed text-ink-faint">
                      {issue.remediation}
                    </p>
                    {issue.evidence.length > 0 ? (
                      <p className="mt-1 font-mono text-[10.5px] leading-relaxed text-ink-faint">
                        {issue.evidence.slice(0, 4).join(' · ')}
                        {/*
                          The evidence list is capped by the backend. Saying so is
                          necessary, otherwise a capped list reads as the complete
                          set of affected packages.
                        */}
                        {issue.affected_count > issue.evidence.length
                          ? ` · +${issue.affected_count - issue.evidence.length} more`
                          : ''}
                      </p>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader title="Licence posture" description="By declared expression" />
            <CardBody>
              {report.licenses.length === 0 ? (
                <p className="text-[12px] text-ink-subtle">
                  No dependency declares a licence in this repository.
                </p>
              ) : (
                <ul className="space-y-2">
                  {LICENCE_ORDER.filter((category) =>
                    licensesInCategory(report.licenses, category).length > 0,
                  ).map((category) => {
                    const entries = licensesInCategory(report.licenses, category);
                    const count = entries.reduce(
                      (total, entry) => total + entry.dependency_count,
                      0,
                    );
                    const share =
                      summary.total_dependencies === 0
                        ? 0
                        : count / summary.total_dependencies;
                    return (
                      <li key={category}>
                        <div className="flex items-center gap-2">
                          <span className="min-w-0 flex-1 truncate text-[11.5px] text-ink-muted">
                            {licenseCategoryLabel(category)}
                          </span>
                          <span className="shrink-0 font-mono text-[10.5px] tabular-nums text-ink-faint">
                            {count}
                          </span>
                        </div>
                        <span className="mt-1 block h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
                          <span
                            className={cn(
                              'block h-full rounded-full',
                              category === 'strong_copyleft' || category === 'proprietary'
                                ? 'bg-amber-400/70'
                                : 'bg-white/20',
                            )}
                            style={{ width: `${Math.max(Math.round(share * 100), 2)}%` }}
                          />
                        </span>
                        <p className="mt-1 truncate font-mono text-[10.5px] text-ink-faint">
                          {entries.map((entry) => entry.expression).join(', ')}
                        </p>
                      </li>
                    );
                  })}
                </ul>
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Score" description="Every deduction applied" />
            <CardBody>
              {summary.score_notes.length === 0 ? (
                <p className="text-[12px] text-ink-subtle">
                  Nothing was deducted: manifests, lockfile, pinning and licences are
                  all in order.
                </p>
              ) : (
                <ul className="space-y-1.5">
                  {summary.score_notes.map((note) => (
                    <li key={note} className="font-mono text-[10.5px] leading-relaxed text-ink-faint">
                      {note}
                    </li>
                  ))}
                </ul>
              )}
            </CardBody>
          </Card>
        </div>
      </div>

      <Card>
        <CardHeader title="Manifests and lockfiles" />
        <CardBody padded={false}>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-[12px]">
              <thead>
                <tr className="border-b border-white/[0.06] text-[10.5px] uppercase tracking-wide text-ink-faint">
                  <th className="px-5 py-2 font-medium">Path</th>
                  <th className="px-3 py-2 font-medium">Role</th>
                  <th className="px-3 py-2 font-medium">Ecosystem</th>
                  <th className="px-3 py-2 text-right font-medium">Dependencies</th>
                  <th className="px-3 py-2 text-right font-medium">Inherited</th>
                  <th className="px-5 py-2 font-medium">Note</th>
                </tr>
              </thead>
              <tbody>
                {report.manifests.map((manifest) => (
                  <tr key={manifest.path} className="border-b border-white/[0.03] last:border-0">
                    <td className="px-5 py-2 font-mono text-[11px] text-ink-muted">
                      {manifest.path}
                    </td>
                    <td className="px-3 py-2 text-ink-subtle">
                      {manifest.found ? manifest.role : 'absent'}
                    </td>
                    <td className="px-3 py-2 text-ink-subtle">{manifest.ecosystem}</td>
                    <td className="px-3 py-2 text-right font-mono tabular-nums text-ink-faint">
                      {manifest.dependency_count}
                    </td>
                    <td className="px-3 py-2 text-right font-mono tabular-nums text-ink-faint">
                      {manifest.transitive_count}
                    </td>
                    <td
                      className={cn(
                        'px-5 py-2 text-[11px]',
                        manifest.parse_failed ? 'text-amber-300' : 'text-ink-faint',
                      )}
                    >
                      {manifest.note}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader
          title="Dependency inventory"
          description={`${visibleDependencies.length} of ${report.dependencies.length} shown`}
        />
        <CardBody padded={false}>
          {visibleDependencies.length === 0 ? (
            <p className="px-5 py-4 text-[12px] text-ink-subtle">
              No dependency matches this search.
            </p>
          ) : (
            <div className="max-h-[520px] overflow-auto">
              <table className="w-full text-left text-[12px]">
                <thead className="sticky top-0 bg-surface-1">
                  <tr className="border-b border-white/[0.06] text-[10.5px] uppercase tracking-wide text-ink-faint">
                    <th className="px-5 py-2 font-medium">Package</th>
                    <th className="px-3 py-2 font-medium">Version</th>
                    <th className="px-3 py-2 font-medium">Origin</th>
                    <th className="px-3 py-2 font-medium">Licence</th>
                    <th className="px-5 py-2 font-medium">Risks</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleDependencies.map((dependency) => (
                    <tr
                      key={`${dependency.ecosystem}-${dependency.name}`}
                      className="border-b border-white/[0.03] last:border-0"
                    >
                      <td className="px-5 py-2 font-mono text-[11px] text-ink-muted">
                        {dependency.name}
                        {dependency.scope === 'development' ? (
                          <span className="ml-1.5 text-[10.5px] text-ink-faint">dev</span>
                        ) : null}
                      </td>
                      <td
                        className={cn(
                          'px-3 py-2 font-mono text-[11px]',
                          dependency.pinned ? 'text-ink-faint' : 'text-amber-300',
                        )}
                      >
                        {dependency.version ?? 'unpinned'}
                      </td>
                      <td className="px-3 py-2 text-ink-subtle">{dependency.origin}</td>
                      <td className="px-3 py-2 text-ink-subtle">
                        {dependency.license_expression ?? (
                          <span className="text-ink-faint">undeclared</span>
                        )}
                      </td>
                      <td className="px-5 py-2 font-mono text-[10.5px] text-amber-300/80">
                        {dependency.risks.join(', ')}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
