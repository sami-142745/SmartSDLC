import { useMemo, useState } from 'react';

import {
  filesNeedingReview,
  getTestGeneration,
  ISSUE_LABEL,
  issuesByCode,
  modelWrittenFiles,
  prioritizedTargets,
  priorityBand,
  proposalStatus,
  REASON_LABEL,
  targetsByFile,
} from '../../api/testGeneration';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { Card, CardBody, CardHeader, InlineStat } from '../ui/Card';
import { EmptyState } from '../EmptyState';
import { ErrorState } from '../ErrorState';
import { PageSkeleton } from '../ui/Skeleton';
import { useAsync } from '../../hooks/useAsync';
import { cn } from '../../lib/cn';
import type {
  GeneratedTestFile,
  ScmProvider,
  TestGeneration,
  TestTarget,
} from '../../types';

const PRIORITY_TONE = {
  high: 'danger',
  medium: 'warning',
  low: 'info',
  minimal: 'neutral',
} as const;

const BAND_LABEL: Record<ReturnType<typeof priorityBand>, string> = {
  high: 'High value',
  medium: 'Worth testing',
  low: 'Lower value',
  minimal: 'Marginal',
};

const SOURCE_LABEL = {
  gemini: 'Model-written',
  deterministic: 'Scaffold',
} as const;

export interface TestGenerationRepositoryOption {
  owner: string;
  repository: string;
}

export interface RepositoryTestGenerationPanelProps {
  options: TestGenerationRepositoryOption[];
  provider: ScmProvider;
  className?: string;
}

/**
 * Proposed tests for one repository.
 *
 * The distinction this screen exists to keep visible: a target is chosen by
 * measurement (which test files reference which symbols), while only the body
 * of a test is written by a model, and nothing is ever executed or written back.
 * A file that fell back to a scaffold says so, and a file the screener flagged
 * is shown with its finding rather than quietly counted as a success.
 */
export function RepositoryTestGenerationPanel({
  options,
  provider,
  className,
}: RepositoryTestGenerationPanelProps) {
  const [selection, setSelection] = useState<TestGenerationRepositoryOption | null>(
    options[0] ?? null,
  );
  const [refresh, setRefresh] = useState(false);
  const [search, setSearch] = useState('');

  const report = useAsync<TestGeneration | null>(
    async () => {
      if (!selection) return null;
      return getTestGeneration(selection.owner, selection.repository, { provider, refresh });
    },
    [selection?.owner, selection?.repository, provider, refresh],
  );

  const visibleFiles = useMemo(() => {
    const files = report.data?.files ?? [];
    if (!search.trim()) return files;
    const needle = search.trim().toLowerCase();
    return files.filter(
      (file) =>
        file.path.toLowerCase().includes(needle) ||
        file.covers.some((name) => name.toLowerCase().includes(needle)),
    );
  }, [report.data, search]);

  if (options.length === 0) {
    return (
      <EmptyState
        title="No repository to propose tests for"
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
              <label htmlFor="test-generation-repo" className="text-[11px] uppercase tracking-wide text-ink-subtle">
                Repository
              </label>
              <select
                id="test-generation-repo"
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
                Search files and symbols
              </span>
              <input
                type="search"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="path or symbol"
                className="mt-1 w-full rounded-lg border border-white/[0.09] bg-surface-2 px-3 py-2 text-[13px] text-ink"
              />
            </label>

            <Button variant="secondary" onClick={() => setRefresh(true)} disabled={report.loading}>
              {refresh ? 'Refreshed' : 'Regenerate'}
            </Button>
          </div>
        </CardBody>
      </Card>

      {report.loading ? (
        <PageSkeleton label="Finding untested symbols" />
      ) : report.error ? (
        <ErrorState
          title="Could not propose tests for this repository"
          message={report.error}
          retry={report.refetch}
        />
      ) : !report.data ? null : (
        <TestGenerationReport report={report.data} visibleFiles={visibleFiles} />
      )}
    </div>
  );
}

interface TestGenerationReportProps {
  report: TestGeneration;
  visibleFiles: GeneratedTestFile[];
}

function TestGenerationReport({ report, visibleFiles }: TestGenerationReportProps) {
  const { summary } = report;
  const status = proposalStatus(report);
  const targets = useMemo(() => prioritizedTargets(report), [report]);
  const grouped = useMemo(() => targetsByFile(targets), [targets]);
  const modelFiles = useMemo(() => modelWrittenFiles(report), [report]);
  // Computed from what is on screen, not from the whole report: a review
  // summary that still lists files the search has hidden would contradict the
  // list directly beneath it.
  const needsReview = useMemo(() => filesNeedingReview(visibleFiles), [visibleFiles]);
  const issues = useMemo(() => issuesByCode({ ...report, files: visibleFiles }), [report, visibleFiles]);
  const rejectedCount = useMemo(() => visibleFiles.filter((file) => !file.usable).length, [visibleFiles]);
  const flaggedCount = useMemo(
    () => visibleFiles.filter((file) => file.usable && file.validation.length > 0).length,
    [visibleFiles],
  );

  if (report.targets.length === 0) {
    return (
      <EmptyState
        title="No untested symbols found"
        description={
          report.truncated
            ? 'File selection stopped at its limit before an untested symbol was found.'
            : summary.existing_test_files > 0
              ? 'Every public symbol scanned is referenced by a test file in this repository.'
              : 'No public source symbols were found to propose tests for.'
        }
      />
    );
  }

  return (
    <div className="space-y-4">
      <Card tone="flat">
        <CardBody>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
            <InlineStat label="Framework" value={summary.framework} />
            <InlineStat label="Source files" value={summary.source_files_scanned} />
            <InlineStat label="Public symbols" value={summary.public_symbols} />
            <InlineStat
              label="Untested"
              value={summary.untested_symbols}
              tone={summary.untested_symbols > 0 ? 'warning' : 'default'}
            />
            <InlineStat label="Targets" value={summary.targets} />
            <InlineStat
              label="Proposed tests"
              value={summary.generated_tests}
              tone={needsReview.length > 0 ? 'warning' : 'default'}
            />
          </div>

          {/*
            What kind of output this is, stated before the files. A scaffold run
            and a model run are not the same artefact, and a reader who is not
            told which one they have will read a skipped placeholder as a test.
          */}
          <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-white/[0.06] pt-3">
            <Badge tone={status === 'model' ? 'brand' : status === 'scaffold' ? 'warning' : 'neutral'}>
              {status === 'model'
                ? `${modelFiles.length} model-written file${modelFiles.length === 1 ? '' : 's'}`
                : status === 'scaffold'
                  ? 'Scaffolds only — no assertions were written'
                  : 'No files proposed'}
            </Badge>
            {report.model ? (
              <span className="font-mono text-[10.5px] text-ink-faint">{report.model}</span>
            ) : null}
            {report.unavailable_reason ? (
              <span className="text-[11.5px] text-ink-subtle">{report.unavailable_reason}</span>
            ) : null}
          </div>

          {report.truncated || report.errors.length > 0 ? (
            <div className="mt-3 space-y-1.5 text-[12px] text-ink-subtle">
              {report.truncated ? (
                <p>
                  Partial analysis: a selection or generation cap was reached, so
                  symbols outside the cap are not represented in this report.
                </p>
              ) : null}
              {report.errors.length > 0 ? (
                <p>
                  {report.errors.length} file{report.errors.length === 1 ? '' : 's'} could
                  not be read. {report.errors.slice(0, 2).join(' ')}
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
            title="Untested symbols"
            description="Chosen by measurement, highest value first"
            actions={
              <span className="text-[11px] text-ink-faint">
                {targets.length} of {report.targets.length} shown
              </span>
            }
          />
          <CardBody>
            <ul className="space-y-3">
              {grouped.map(({ file, targets: fileTargets }) => (
                <li key={file}>
                  <p className="font-mono text-[11px] text-ink-muted">{file}</p>
                  <ul className="mt-1.5 space-y-1.5">
                    {fileTargets.map((target) => (
                      <TargetRow key={target.qualified_name} target={target} />
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          </CardBody>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader
              title="Needs review"
              description="Files a screener flagged, or rejected outright"
            />
            <CardBody>
              {needsReview.length === 0 ? (
                <p className="text-[12px] text-ink-subtle">
                  {report.files.length === 0
                    ? 'No file was proposed in this run.'
                    : 'No proposed file carries a screening finding.'}
                </p>
              ) : (
                <>
                  {/*
                    Counts, not paths. The file list directly below already
                    carries each path with its own badge, and repeating it here
                    would show the same file twice and contradict a search.
                  */}
                  <ul className="space-y-1.5 text-[12px] text-ink-subtle">
                    {rejectedCount > 0 ? (
                      <li className="flex items-center justify-between gap-2">
                        <Badge tone="danger">Rejected</Badge>
                        <span className="font-mono tabular-nums text-ink-faint">
                          {rejectedCount}
                        </span>
                      </li>
                    ) : null}
                    {flaggedCount > 0 ? (
                      <li className="flex items-center justify-between gap-2">
                        <Badge tone="warning">Flagged</Badge>
                        <span className="font-mono tabular-nums text-ink-faint">
                          {flaggedCount}
                        </span>
                      </li>
                    ) : null}
                  </ul>
                  {issues.length > 0 ? (
                    <ul className="mt-3 space-y-1.5 border-t border-white/[0.06] pt-3">
                      {issues.map((issue) => (
                        <li
                          key={`${issue.code}-${issue.detail}`}
                          className="flex items-start justify-between gap-2 text-[11.5px] text-ink-subtle"
                        >
                          <span className="min-w-0">
                            <span className="text-ink-muted">{ISSUE_LABEL[issue.code]}</span>
                            <span className="block text-ink-faint">{issue.detail}</span>
                          </span>
                          <span className="shrink-0 font-mono tabular-nums text-ink-faint">
                            {issue.paths.length} file{issue.paths.length === 1 ? '' : 's'}
                          </span>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </>
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Repository's own tests" description="Detected, not generated" />
            <CardBody>
              <div className="space-y-2 text-[12px] text-ink-subtle">
                <p>
                  {summary.existing_test_files} test file
                  {summary.existing_test_files === 1 ? '' : 's'} found
                  {report.test_directories.length > 0
                    ? ` under ${report.test_directories.join(', ')}`
                    : ''}
                  .
                </p>
                {report.existing_test_files.length > 0 ? (
                  <ul className="max-h-40 space-y-1 overflow-y-auto font-mono text-[10.5px] text-ink-faint">
                    {report.existing_test_files.slice(0, 40).map((path) => (
                      <li key={path} className="truncate">
                        {path}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
            </CardBody>
          </Card>
        </div>
      </div>

      <Card>
        <CardHeader
          title="Proposed test files"
          description={`${visibleFiles.length} of ${report.files.length} shown · nothing is written to the repository`}
        />
        <CardBody padded={false}>
          {visibleFiles.length === 0 ? (
            <p className="px-5 py-4 text-[12px] text-ink-subtle">
              No proposed file matches this search.
            </p>
          ) : (
            <ul className="divide-y divide-white/[0.04]">
              {visibleFiles.map((file) => (
                <GeneratedFileRow key={file.path} file={file} />
              ))}
            </ul>
          )}
        </CardBody>
      </Card>
    </div>
  );
}

function TargetRow({ target }: { target: TestTarget }) {
  return (
    <li className="flex flex-wrap items-center gap-2">
      <Badge tone={PRIORITY_TONE[priorityBand(target.priority)]}>
        {BAND_LABEL[priorityBand(target.priority)]}
      </Badge>
      <span className="font-mono text-[11.5px] text-ink">{target.qualified_name}</span>
      <span className="font-mono text-[10.5px] text-ink-faint">
        {target.file}:{target.line}
      </span>
      <span className="text-[11px] text-ink-subtle">{REASON_LABEL[target.reason]}</span>
      <p className="w-full font-mono text-[10.5px] leading-relaxed text-ink-faint">
        {target.evidence}
      </p>
    </li>
  );
}

function GeneratedFileRow({ file }: { file: GeneratedTestFile }) {
  const [expanded, setExpanded] = useState(false);
  const hasFindings = file.validation.length > 0;

  return (
    <li className="px-5 py-3.5">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={file.source === 'gemini' ? 'brand' : 'warning'}>
          {SOURCE_LABEL[file.source]}
        </Badge>
        <span className="min-w-0 flex-1 truncate font-mono text-[11.5px] text-ink-muted">
          {file.path}
        </span>
        <span className="shrink-0 font-mono text-[10.5px] tabular-nums text-ink-faint">
          {file.test_names.length} test{file.test_names.length === 1 ? '' : 's'}
        </span>
        {hasFindings ? (
          <Badge tone={file.usable ? 'warning' : 'danger'}>
            {file.usable ? `${file.validation.length} finding${file.validation.length === 1 ? '' : 's'}` : 'Rejected'}
          </Badge>
        ) : null}
        <Button variant="ghost" size="sm" onClick={() => setExpanded((open) => !open)}>
          {expanded ? 'Hide' : 'View'}
        </Button>
      </div>

      {file.covers.length > 0 ? (
        <p className="mt-1.5 font-mono text-[10.5px] text-ink-faint">
          covers {file.covers.join(', ')}
        </p>
      ) : null}

      {hasFindings ? (
        <ul className="mt-2 space-y-1">
          {file.validation.map((issue, index) => (
            <li key={`${issue.code}-${index}`} className="text-[11px] text-ink-subtle">
              <span className="text-ink-muted">{ISSUE_LABEL[issue.code]}</span>
              {issue.line ? <span className="text-ink-faint"> (line {issue.line})</span> : null}
              {': '}
              <span className="text-ink-faint">{issue.detail}</span>
            </li>
          ))}
        </ul>
      ) : null}

      {expanded ? (
        <pre className="mt-2.5 max-h-96 overflow-auto rounded-lg border border-white/[0.06] bg-surface-2 p-3 font-mono text-[11px] leading-relaxed text-ink-muted">
          {file.content}
        </pre>
      ) : null}
    </li>
  );
}
