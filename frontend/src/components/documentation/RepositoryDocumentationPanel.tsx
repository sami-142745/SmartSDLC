import { useMemo, useState } from 'react';

import {
  actionableGaps,
  coverageBand,
  getDocumentationIntelligence,
  leastDocumented,
} from '../../api/documentationIntelligence';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { Card, CardBody, CardHeader, InlineStat } from '../ui/Card';
import { EmptyState } from '../EmptyState';
import { ErrorState } from '../ErrorState';
import { PageSkeleton } from '../ui/Skeleton';
import { useAsync } from '../../hooks/useAsync';
import { cn } from '../../lib/cn';
import type {
  DocumentationAssetKind,
  DocumentationGapSeverity,
  DocumentationIntelligence,
  ScmProvider,
} from '../../types';

const KIND_LABEL: Record<DocumentationAssetKind, string> = {
  readme: 'README',
  changelog: 'Changelog',
  contributing: 'Contributing',
  license: 'License',
  security_policy: 'Security',
  code_of_conduct: 'Code of conduct',
  api_reference: 'API reference',
  adr: 'ADR',
  guide: 'Guide',
  documentation: 'Documentation',
  other: 'Other',
};

const SEVERITY_FILTERS: (DocumentationGapSeverity | 'all')[] = ['all', 'warning', 'info'];

const BAND_LABEL: Record<ReturnType<typeof coverageBand>, string> = {
  strong: 'Well documented',
  partial: 'Partly documented',
  weak: 'Barely documented',
  none: 'Undocumented',
};

export interface DocumentationRepositoryOption {
  owner: string;
  repository: string;
}

export interface RepositoryDocumentationPanelProps {
  options: DocumentationRepositoryOption[];
  provider: ScmProvider;
  className?: string;
}

/**
 * Documentation coverage for one repository.
 *
 * No model is involved: the backend measures the repository's own files, so
 * every number here is reproducible and every gap names the observation behind
 * it. Partial coverage is stated on screen rather than left for the reader to
 * infer, and the score is presented as a band with its inputs visible rather
 * than as a grade.
 */
export function RepositoryDocumentationPanel({
  options,
  provider,
  className,
}: RepositoryDocumentationPanelProps) {
  const [selection, setSelection] = useState<DocumentationRepositoryOption | null>(options[0] ?? null);
  const [severity, setSeverity] = useState<DocumentationGapSeverity | 'all'>('all');
  const [search, setSearch] = useState('');
  const [refresh, setRefresh] = useState(false);

  const report = useAsync<DocumentationIntelligence | null>(
    async () => {
      if (!selection) return null;
      return getDocumentationIntelligence(selection.owner, selection.repository, { provider, refresh });
    },
    [selection?.owner, selection?.repository, provider, refresh],
  );

  const visibleGaps = useMemo(() => {
    const gaps = report.data?.gaps ?? [];
    return severity === 'all' ? gaps : gaps.filter((gap) => gap.severity === severity);
  }, [report.data, severity]);

  const visibleAssets = useMemo(() => {
    const assets = report.data?.assets ?? [];
    if (!search.trim()) return assets;
    const needle = search.trim().toLowerCase();
    return assets.filter((asset) => asset.path.toLowerCase().includes(needle));
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
              <label htmlFor="documentation-repo" className="text-[11px] uppercase tracking-wide text-ink-subtle">
                Repository
              </label>
              <select
                id="documentation-repo"
                value={selection ? `${selection.owner}/${selection.repository}` : ''}
                onChange={(event) => {
                  const [owner, repository] = event.target.value.split('/');
                  setSelection({ owner, repository });
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
              <span className="text-[11px] uppercase tracking-wide text-ink-subtle">Search documents</span>
              <input
                type="search"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="path"
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
        <PageSkeleton label="Measuring documentation coverage" />
      ) : report.error ? (
        <ErrorState
          title="Could not measure this repository's documentation"
          message={report.error}
          retry={report.refetch}
        />
      ) : !report.data ? null : (
        <DocumentationReport
          report={report.data}
          severity={severity}
          onSeverity={setSeverity}
          visibleGaps={visibleGaps}
          visibleAssets={visibleAssets}
        />
      )}
    </div>
  );
}

interface DocumentationReportProps {
  report: DocumentationIntelligence;
  severity: DocumentationGapSeverity | 'all';
  onSeverity: (value: DocumentationGapSeverity | 'all') => void;
  visibleGaps: DocumentationIntelligence['gaps'];
  visibleAssets: DocumentationIntelligence['assets'];
}

function DocumentationReport({
  report,
  severity,
  onSeverity,
  visibleGaps,
  visibleAssets,
}: DocumentationReportProps) {
  const { summary } = report;
  const band = coverageBand(summary.coverage_score);
  const warnings = actionableGaps(report).length;
  const least = useMemo(() => leastDocumented(report, 8), [report]);

  if (report.assets.length === 0 && report.coverage.length === 0) {
    return (
      <EmptyState
        title="Nothing to measure"
        description={
          report.truncated
            ? 'The file limit was reached before a documentation or source file was found.'
            : 'No documentation or supported source files were found in this repository at the analysed ref.'
        }
      />
    );
  }

  return (
    <div className="space-y-4">
      <Card tone="flat">
        <CardBody>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
            <InlineStat label="Coverage score" value={`${summary.coverage_score}/100`} />
            <InlineStat label="Verdict" value={BAND_LABEL[band]} />
            <InlineStat
              label="Docstring coverage"
              value={`${Math.round(summary.docstring_coverage * 100)}%`}
              tone={summary.docstring_coverage < 0.5 ? 'warning' : 'default'}
            />
            <InlineStat
              label="Gaps"
              value={summary.gap_count}
              tone={warnings > 0 ? 'warning' : 'default'}
            />
            <InlineStat
              label="Broken links"
              value={summary.broken_links}
              tone={summary.broken_links > 0 ? 'warning' : 'default'}
            />
            <InlineStat label="Docs / source" value={`${summary.documentation_files} / ${summary.source_files}`} />
          </div>

          {/*
            Coverage is stated, not implied. A truncated report that looked like
            a complete one is how a reader concludes a repository is documented
            when only the first few files were measured.
          */}
          {report.truncated || report.errors.length > 0 || summary.public_symbols === 0 ? (
            <div className="mt-4 space-y-1.5 border-t border-white/[0.06] pt-3 text-[12px] text-ink-subtle">
              {report.truncated ? (
                <p>
                  Partial analysis: file selection stopped at its limit, so files
                  outside the cap are not represented in this report.
                </p>
              ) : null}
              {report.errors.length > 0 ? (
                <p>
                  {report.errors.length} file{report.errors.length === 1 ? '' : 's'} could
                  not be read. {report.errors.slice(0, 2).join(' ')}
                </p>
              ) : null}
              {summary.public_symbols === 0 ? (
                <p>
                  No public source symbols were measured, so the docstring figure
                  above is not a statement about this code.
                </p>
              ) : null}
            </div>
          ) : null}

          <p className="mt-3 text-[11px] leading-relaxed text-ink-faint">{summary.methodology}</p>
        </CardBody>
      </Card>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
        <Card>
          <CardHeader
            title="Documentation gaps"
            description={
              summary.missing_canonical.length > 0
                ? `Missing canonical files: ${summary.missing_canonical.join(', ')}`
                : 'Every canonical file is present'
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
            {visibleGaps.length === 0 ? (
              <p className="text-[12px] text-ink-subtle">
                {report.gaps.length === 0
                  ? 'No documentation gap crossed its threshold in this analysis.'
                  : 'No gap matches this filter.'}
              </p>
            ) : (
              <ul className="space-y-3">
                {visibleGaps.map((gap) => (
                  <li key={`${gap.kind}-${gap.paths[0] ?? ''}-${gap.title}`}>
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone={gap.severity === 'warning' ? 'warning' : 'neutral'}>
                        {gap.title}
                      </Badge>
                      {gap.paths.slice(0, 3).map((path) => (
                        <span key={path} className="font-mono text-[10.5px] text-ink-faint">
                          {path}
                        </span>
                      ))}
                    </div>
                    <p className="mt-1 text-[11.5px] leading-relaxed text-ink-subtle">{gap.detail}</p>
                    <p className="mt-0.5 font-mono text-[10.5px] leading-relaxed text-ink-faint">
                      {gap.evidence}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader title="Least documented" description="Public symbols without a docstring" />
            <CardBody>
              {least.length === 0 ? (
                <p className="text-[12px] text-ink-subtle">No public symbols were measured.</p>
              ) : (
                <ul className="space-y-2">
                  {least.map((row) => (
                    <li key={row.path}>
                      <div className="flex items-center gap-2">
                        <span className="min-w-0 flex-1 truncate font-mono text-[11px] text-ink-muted">
                          {row.path}
                        </span>
                        <span className="shrink-0 font-mono text-[10.5px] tabular-nums text-ink-faint">
                          {row.documented_symbols}/{row.public_symbols}
                        </span>
                      </div>
                      <span className="mt-1 block h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
                        <span
                          className="block h-full rounded-full bg-amber-400/70"
                          style={{ width: `${Math.max(Math.round(row.coverage * 100), 2)}%` }}
                        />
                      </span>
                      {row.undocumented.length > 0 ? (
                        <p className="mt-1 font-mono text-[10.5px] text-ink-faint">
                          {row.undocumented.slice(0, 6).join(', ')}
                          {row.undocumented.length > 6 ? ' …' : ''}
                        </p>
                      ) : null}
                    </li>
                  ))}
                </ul>
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="README" />
            <CardBody>
              {summary.readme_present ? (
                <p className="text-[12px] leading-relaxed text-ink-subtle">
                  {summary.readme_word_count} words across {summary.readme_sections} sections.
                </p>
              ) : (
                <p className="text-[12px] text-ink-subtle">No README was found in this repository.</p>
              )}
            </CardBody>
          </Card>
        </div>
      </div>

      <Card>
        <CardHeader
          title="Documentation files"
          description={`${visibleAssets.length} of ${report.assets.length} shown`}
        />
        <CardBody padded={false}>
          {visibleAssets.length === 0 ? (
            <p className="px-5 py-4 text-[12px] text-ink-subtle">No document matches this search.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-[12px]">
                <thead>
                  <tr className="border-b border-white/[0.06] text-[10.5px] uppercase tracking-wide text-ink-faint">
                    <th className="px-5 py-2 font-medium">Path</th>
                    <th className="px-3 py-2 font-medium">Kind</th>
                    <th className="px-3 py-2 text-right font-medium">Words</th>
                    <th className="px-3 py-2 text-right font-medium">Sections</th>
                    <th className="px-3 py-2 text-right font-medium">Links</th>
                    <th className="px-5 py-2 text-right font-medium">Broken</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleAssets.map((asset) => {
                    const broken = asset.links.filter((link) => link.internal && link.resolved === false).length;
                    return (
                      <tr key={asset.path} className="border-b border-white/[0.03] last:border-0">
                        <td className="px-5 py-2 font-mono text-[11px] text-ink-muted">{asset.path}</td>
                        <td className="px-3 py-2 text-ink-subtle">{KIND_LABEL[asset.kind]}</td>
                        <td className="px-3 py-2 text-right font-mono tabular-nums text-ink-faint">
                          {asset.word_count}
                        </td>
                        <td className="px-3 py-2 text-right font-mono tabular-nums text-ink-faint">
                          {asset.headings.length}
                        </td>
                        <td className="px-3 py-2 text-right font-mono tabular-nums text-ink-faint">
                          {asset.links.length}
                        </td>
                        <td
                          className={cn(
                            'px-5 py-2 text-right font-mono tabular-nums',
                            broken > 0 ? 'text-amber-300' : 'text-ink-faint',
                          )}
                        >
                          {broken}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
