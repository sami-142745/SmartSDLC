import { useCallback, useEffect, useMemo, useState } from 'react';

import { DiffViewer } from '../DiffViewer';
import { EmptyState } from '../EmptyState';
import { AssessmentPanel } from './AssessmentPanel';
import { FileRail } from './FileRail';
import { FindingList, sortAiReviewFindings } from './FindingList';
import { AI_REVIEW_CATEGORIES, AI_REVIEW_FILE_LEVEL_LINE, AI_REVIEW_SEVERITIES } from '../../types';
import { categoryLabel } from '../../lib/aiReview';
import { cn } from '../../lib/cn';
import type { AiReview, AiReviewCategory, AiReviewFinding, AiReviewSeverity } from '../../types';

type SortMode = 'severity' | 'confidence' | 'category' | 'file' | 'line';
type FindingScope = 'all' | 'file';

export interface AiReviewWorkspaceProps {
  review: AiReview;
  /** Surfaced again in the right pane so the reason is not only in the header. */
  onRerun?: () => void;
  className?: string;
}

/**
 * Three-pane review surface: changed files, the diff, and the findings.
 *
 * Selection is the single piece of state that ties the panes together. Clicking
 * a finding moves the centre pane to that file and line; clicking a file shows
 * the findings for that file, filtered in place rather than by removing rows,
 * so a reviewer can always tell "this file has no issues" from "the filter hid
 * them".
 */
export function AiReviewWorkspace({ review, onRerun, className }: AiReviewWorkspaceProps) {
  const [activePath, setActivePath] = useState<string | null>(review.files[0]?.path ?? null);
  const [activeFindingId, setActiveFindingId] = useState<string | null>(null);
  const [focusLine, setFocusLine] = useState<number | null>(null);
  const [severityFilter, setSeverityFilter] = useState<AiReviewSeverity | null>(null);
  const [categoryFilter, setCategoryFilter] = useState<AiReviewCategory | null>(null);
  const [sort, setSort] = useState<SortMode>('severity');
  // Defaults to every file so that clicking a finding can actually move the
  // centre pane; a finding for another file is invisible in "this file" mode.
  const [scope, setScope] = useState<FindingScope>('all');

  // A new review replaces the old one, so reset the selection rather than
  // pointing at a file that may not exist in the new diff.
  useEffect(() => {
    setActivePath(review.files[0]?.path ?? null);
    setActiveFindingId(null);
    setFocusLine(null);
    setSeverityFilter(null);
    setCategoryFilter(null);
    setScope('all');
  }, [review.review_id]);

  const scopedFindings = useMemo(
    () =>
      scope === 'file'
        ? review.findings.filter((finding) => finding.file === activePath)
        : review.findings,
    [review.findings, activePath, scope],
  );

  const visibleFindings = useMemo(() => {
    const filtered = scopedFindings.filter(
      (finding) =>
        (severityFilter === null || finding.severity === severityFilter) &&
        (categoryFilter === null || finding.category === categoryFilter),
    );
    return sortAiReviewFindings(filtered, sort);
  }, [scopedFindings, severityFilter, categoryFilter, sort]);

  const activeFile = useMemo(
    () => review.files.find((file) => file.path === activePath) ?? null,
    [review.files, activePath],
  );

  const handleSelectFinding = useCallback((finding: AiReviewFinding) => {
    setActivePath(finding.file);
    setActiveFindingId(finding.finding_id);
    // The file-level sentinel has nothing to scroll to, so clear any previous
    // target instead of jumping to a stale line in the new file.
    setFocusLine(finding.line === AI_REVIEW_FILE_LEVEL_LINE ? null : finding.line);
  }, []);

  if (review.files.length === 0) {
    return (
      <div className={className}>
        <AssessmentPanel review={review} className="mb-4" />
        <EmptyState
          title="No changed files to review"
          description="This pull request has no file changes, so there is nothing to diff. It may have been closed without merging new commits, or it may only touch files the provider does not expose diffs for."
        />
      </div>
    );
  }

  return (
    <div className={cn('flex flex-col gap-4', className)}>
      <AssessmentPanel review={review} />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,22rem)]">
        <section
          className="flex max-h-[40rem] min-h-0 flex-col overflow-hidden rounded-xl border border-white/[0.07] bg-surface-0 shadow-elevated"
          aria-label="Changed files"
        >
          <div className="flex items-center justify-between border-b border-white/[0.05] px-3 py-2">
            <span className="eyebrow">Files</span>
            <span className="font-mono text-[10.5px] tabular-nums text-ink-faint">
              {review.files.length}
            </span>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto">
            <FileRail files={review.files} activePath={activePath} onSelect={setActivePath} />
          </div>
        </section>

        <section
          className="flex min-w-0 flex-col overflow-hidden rounded-xl border border-white/[0.07] bg-surface-0 shadow-elevated"
          aria-label="Diff"
        >
          {activeFile ? (
            <>
              <div className="flex min-w-0 flex-wrap items-center justify-between gap-2 border-b border-white/[0.05] bg-surface-1/50 px-3 py-2">
                <span className="min-w-0 truncate font-mono text-[11.5px] text-ink-muted" title={activeFile.path}>
                  {activeFile.path}
                </span>
                <span className="shrink-0 font-mono text-[10.5px] tabular-nums">
                  <span className="text-emerald-400/85">+{activeFile.additions}</span>{' '}
                  <span className="text-rose-400/85">-{activeFile.deletions}</span>
                </span>
              </div>
              <div className="min-h-0 flex-1 overflow-y-auto">
                {activeFile.status === 'binary' || !activeFile.patch ? (
                  <BinaryFileNotice filePath={activeFile.path} />
                ) : activeFile.status === 'deleted' ? (
                  <DeletedFileNotice filePath={activeFile.path} />
                ) : (
                  <DiffViewer diff={activeFile.patch} focusLine={focusLine} height={520} />
                )}
              </div>
            </>
          ) : (
            <p className="px-4 py-8 text-center text-[12.5px] text-ink-faint">
              Select a file to see its diff.
            </p>
          )}
        </section>

        <section
          className="flex max-h-[40rem] min-h-0 flex-col overflow-hidden rounded-xl border border-white/[0.07] bg-surface-0 shadow-elevated"
          aria-label="Findings"
        >
          <FilterBar
            severity={severityFilter}
            category={categoryFilter}
            scope={scope}
            available={scopedFindings}
            fileCount={review.files.length}
            onSeverityChange={setSeverityFilter}
            onCategoryChange={setCategoryFilter}
            onScopeChange={setScope}
          />
          <div className="min-h-0 flex-1 overflow-y-auto">
            <FindingList
              findings={visibleFindings}
              activeFindingId={activeFindingId}
              onSelect={handleSelectFinding}
              sort={sort}
              onSortChange={setSort}
            />
          </div>
        </section>
      </div>

      {onRerun ? (
        <div className="flex justify-end">
          <button
            type="button"
            onClick={onRerun}
            className="rounded-lg border border-white/[0.09] px-3 py-1.5 text-[12.5px] text-ink-muted transition-colors hover:bg-white/[0.04]"
          >
            Re-run AI review
          </button>
        </div>
      ) : null}
    </div>
  );
}

function FilterBar({
  severity,
  category,
  scope,
  available,
  fileCount,
  onSeverityChange,
  onCategoryChange,
  onScopeChange,
}: {
  severity: AiReviewSeverity | null;
  category: AiReviewCategory | null;
  scope: FindingScope;
  available: AiReviewFinding[];
  fileCount: number;
  onSeverityChange: (value: AiReviewSeverity | null) => void;
  onCategoryChange: (value: AiReviewCategory | null) => void;
  onScopeChange: (value: FindingScope) => void;
}) {
  const severitiesPresent = new Set(available.map((finding) => finding.severity));
  const categoriesPresent = new Set(available.map((finding) => finding.category));

  return (
    <div className="flex flex-col gap-1.5 border-b border-white/[0.05] px-3 py-2">
      {fileCount > 1 ? (
        <div className="flex items-center gap-1">
          <span className="eyebrow mr-1">Show</span>
          <FilterChip active={scope === 'all'} onClick={() => onScopeChange('all')}>
            All files
          </FilterChip>
          <FilterChip active={scope === 'file'} onClick={() => onScopeChange('file')}>
            This file
          </FilterChip>
        </div>
      ) : null}
      <div className="flex flex-wrap items-center gap-1">
        <span className="eyebrow mr-1">Severity</span>
        <FilterChip active={severity === null} onClick={() => onSeverityChange(null)}>
          All
        </FilterChip>
        {AI_REVIEW_SEVERITIES.filter((value) => severitiesPresent.has(value)).map((value) => (
          <FilterChip
            key={value}
            active={severity === value}
            onClick={() => onSeverityChange(severity === value ? null : value)}
          >
            {value}
          </FilterChip>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-1">
        <span className="eyebrow mr-1">Category</span>
        <FilterChip active={category === null} onClick={() => onCategoryChange(null)}>
          All
        </FilterChip>
        {AI_REVIEW_CATEGORIES.filter((value) => categoriesPresent.has(value)).map((value) => (
          <FilterChip
            key={value}
            active={category === value}
            onClick={() => onCategoryChange(category === value ? null : value)}
          >
            {categoryLabel(value)}
          </FilterChip>
        ))}
      </div>
    </div>
  );
}

function FilterChip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        'rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide transition-colors',
        active
          ? 'border-accent-violet/50 bg-accent-violet/15 text-accent-lavender'
          : 'border-white/10 bg-white/[0.03] text-ink-faint hover:text-ink-muted',
      )}
    >
      {children}
    </button>
  );
}

function BinaryFileNotice({ filePath }: { filePath: string }) {
  return (
    <div className="px-4 py-10 text-center">
      <p className="text-[13px] font-medium text-ink-muted">Binary file</p>
      <p className="mx-auto mt-1.5 max-w-sm text-[12.5px] leading-relaxed text-ink-faint">
        <span className="font-mono">{filePath}</span> has no textual diff, so it cannot be
        shown here. Findings on this file, if any, are still listed on the right.
      </p>
    </div>
  );
}

function DeletedFileNotice({ filePath }: { filePath: string }) {
  return (
    <div className="px-4 py-10 text-center">
      <p className="text-[13px] font-medium text-ink-muted">File deleted</p>
      <p className="mx-auto mt-1.5 max-w-sm text-[12.5px] leading-relaxed text-ink-faint">
        <span className="font-mono">{filePath}</span> was removed in this pull request, so the
        diff is shown from the pull request patch rather than the surviving source.
      </p>
    </div>
  );
}
