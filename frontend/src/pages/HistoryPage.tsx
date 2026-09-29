import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { getHistory } from '../api/dashboard';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import { PageContainer } from '../components/PageContainer';
import { PageHeader } from '../components/PageHeader';
import { Pagination } from '../components/Pagination';
import { SeverityBadge } from '../components/SeverityBadge';
import { StateBadge } from '../components/Badge';
import { Button } from '../components/ui/Button';
import { Card, CardBody, CardHeader } from '../components/ui/Card';
import type { HistoryItem } from '../types';
import { formatDate, formatShortDate } from '../utils/format';

const PER_PAGE = 20;

const STATUS_OPTIONS = [
  { value: '', label: 'All' },
  { value: 'complete', label: 'Complete' },
  { value: 'gemini_unavailable', label: 'Gemini unavailable' },
  { value: 'failed', label: 'Failed' },
];

interface HistoryFilters {
  repository: string;
  status: string;
}

const EMPTY_FILTERS: HistoryFilters = { repository: '', status: '' };

function TimelineRow({ item, onClick }: { item: HistoryItem; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group/hrow relative w-full overflow-hidden rounded-xl border border-white/[0.06] bg-surface-1/70 py-3 pl-5 pr-4 text-left backdrop-blur-sm transition-all duration-200 hover:border-accent-indigo/25 hover:bg-surface-2/80"
    >
      <span
        aria-hidden
        className="pointer-events-none absolute inset-y-0 left-0 w-[3px] rounded-r-full bg-gradient-to-b from-accent-indigo/0 via-accent-indigo/60 to-accent-indigo/0 opacity-0 transition-opacity duration-200 group-hover/hrow:opacity-100"
      />
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5">
        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-2">
            <span className="font-mono text-sm text-ink-muted">
              {item.owner}/{item.repository} #{item.pull_request_number}
            </span>
            {item.pull_request_title ? (
              <span className="max-w-56 truncate text-sm text-ink">{item.pull_request_title}</span>
            ) : null}
          </span>
          <span className="mt-0.5 block font-mono text-[11px] text-ink-faint">
            {item.commit_sha ? `commit ${item.commit_sha.slice(0, 7)}` : '\u2014'}
          </span>
        </span>

        <span className="flex shrink-0 flex-wrap items-center gap-3">
          <span className="font-mono text-xs text-ink-muted tabular-nums">
            {item.total_finding_count} findings
          </span>
          {item.review_score_100 != null ? (
            <span className="font-mono text-xs text-ink">
              {item.review_score_100} / 100
            </span>
          ) : null}
          {item.review_severity ? <SeverityBadge severity={item.review_severity} /> : null}
          <StateBadge state={item.status} />
          <span className="w-32 text-right font-mono text-[11px] text-ink-faint">
            {formatDate(item.created_at)}
          </span>
        </span>
      </div>
    </button>
  );
}

export function HistoryPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState<HistoryFilters>(EMPTY_FILTERS);
  const [applied, setApplied] = useState<HistoryFilters>(EMPTY_FILTERS);
  const [data, setData] = useState<Awaited<ReturnType<typeof getHistory>> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getHistory({
      page,
      perPage: PER_PAGE,
      repository: applied.repository || undefined,
      status: applied.status || undefined,
    })
      .then(setData)
      .catch((err) => setError((err as { message?: string }).message ?? 'Could not load history.'))
      .finally(() => setLoading(false));
  }, [page, applied]);

  const applyFilters = () => {
    setPage(1);
    setApplied(filters);
  };

  const groups = new Map<string, HistoryItem[]>();
  for (const item of data?.items ?? []) {
    const day = formatShortDate(item.created_at);
    const bucket = groups.get(day) ?? [];
    bucket.push(item);
    groups.set(day, bucket);
  }

  return (
    <PageContainer className="space-y-6">
      <PageHeader
        eyebrow={
          <>
            <span aria-hidden className="h-px w-8 bg-indigo-400/60" />
            Reconstruction archive
          </>
        }
        title="Review history"
        description="Every AI review you have run, grouped by day. Select any entry to revisit its analysis."
      />

      <Card tone="flat">
        <CardHeader
          title="Filters"
          actions={
            data ? (
              <span className="font-mono text-[11.5px] tabular-nums text-ink-faint">
                {data.total} review{data.total === 1 ? '' : 's'} found
              </span>
            ) : null
          }
        />
        <CardBody>
          <div className="flex flex-wrap items-end gap-4">
            <label className="flex flex-col gap-1.5">
              <span className="eyebrow">Repository</span>
              <input
                type="text"
                placeholder="owner/name"
                value={filters.repository}
                onChange={(event) =>
                  setFilters((prev) => ({ ...prev, repository: event.target.value }))
                }
                className="field min-w-[14rem]"
              />
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="eyebrow">Status</span>
              <select
                value={filters.status}
                onChange={(event) => setFilters((prev) => ({ ...prev, status: event.target.value }))}
                className="field min-w-[12rem]"
              >
                {STATUS_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value} className="bg-surface-1 text-ink">
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <Button variant="secondary" onClick={applyFilters}>
              Apply filters
            </Button>
          </div>
        </CardBody>
      </Card>

      {loading ? (
        <LoadingState label="Loading history…" />
      ) : error ? (
        <ErrorState title="Could not load history" message={error} retry={() => setApplied({ ...applied })} />
      ) : data && data.items.length === 0 ? (
        <EmptyState
          title="No reviews found"
          description="Try clearing the filters, or run your first AI review."
        />
      ) : data ? (
        <>
          <div className="space-y-4">
            {[...groups.entries()].map(([day, items]) => (
              <Card key={day} tone="flat">
                <CardHeader
                  title={
                    <span className="font-mono text-[12px] uppercase tracking-[0.14em]">
                      {day}
                    </span>
                  }
                  description={`${items.length} review${items.length === 1 ? '' : 's'}`}
                />
                <CardBody>
                  <div className="space-y-1.5">
                    {items.map((item) => (
                      <TimelineRow
                        key={`${item.owner}/${item.repository}/${item.pull_request_number}/${item.created_at}`}
                        item={item}
                        onClick={() =>
                          navigate(
                            `/reviews/${item.owner}/${item.repository}/${item.pull_request_number}`,
                          )
                        }
                      />
                    ))}
                  </div>
                </CardBody>
              </Card>
            ))}
          </div>

          <Pagination
            page={page}
            perPage={PER_PAGE}
            total={data.total}
            totalPages={data.total_pages}
            onPageChange={setPage}
          />
        </>
      ) : null}
    </PageContainer>
  );
}
