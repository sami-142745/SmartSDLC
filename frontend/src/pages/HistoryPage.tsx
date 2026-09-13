import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { getHistory } from '../api/dashboard';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import { PageContainer } from '../components/PageContainer';
import { Pagination } from '../components/Pagination';
import { SeverityBadge } from '../components/SeverityBadge';
import { Reveal } from '../components/motion/Reveal';
import { StateBadge } from '../components/Badge';
import type { HistoryItem } from '../types';
import { formatDate, formatShortDate } from '../utils/format';

const PER_PAGE = 20;

interface HistoryFilters {
  repository: string;
  status: string;
}

function TimelineRow({ item, onClick }: { item: HistoryItem; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group/hrow relative w-full overflow-hidden rounded-xl border border-white/[0.06] bg-surface-1/70 py-3 pl-5 pr-4 text-left backdrop-blur-sm transition-all duration-200 hover:-translate-y-0.5 hover:border-accent-indigo/20 hover:bg-surface-2/80 hover:shadow-[0_14px_34px_-18px_rgba(0,0,0,0.65),0_0_24px_-14px_rgba(99,102,241,0.4)]"
    >
      <span
        aria-hidden
        className="pointer-events-none absolute inset-y-0 left-0 w-[3px] rounded-r-full bg-gradient-to-b from-accent-indigo/0 via-accent-indigo/50 to-accent-indigo/0 opacity-0 transition-opacity duration-200 group-hover/hrow:opacity-100"
      />
      <span
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-accent-indigo/30 to-transparent opacity-0 transition-opacity duration-200 group-hover/hrow:opacity-100"
      />
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5">
        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-2">
            <span className="font-mono text-sm text-slate-200">
              {item.owner}/{item.repository} #{item.pull_request_number}
            </span>
            {item.pull_request_title && (
              <span className="hidden max-w-56 truncate text-sm text-slate-400 md:inline">
                {item.pull_request_title}
              </span>
            )}
          </span>
          <span className="mt-0.5 block font-mono text-[11px] text-slate-600">
            {item.commit_sha ? `commit ${item.commit_sha.slice(0, 7)}` : '\u2014'}
          </span>
        </span>

        <span className="flex shrink-0 items-center gap-3">
          <span className="font-mono text-xs text-slate-500">
            <span className="text-slate-200 tabular-nums">{item.total_finding_count}</span> findings
          </span>
          {item.review_score != null && (
            <span className="font-mono text-xs tabular-nums text-slate-400">
              {item.review_score} score
            </span>
          )}
          {item.review_severity ? <SeverityBadge severity={item.review_severity} /> : null}
          <StateBadge state={item.status} />
          <span className="w-36 text-right font-mono text-xs text-slate-600">
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
  const [filters, setFilters] = useState<HistoryFilters>({ repository: '', status: '' });
  const [applied, setApplied] = useState<HistoryFilters>({ repository: '', status: '' });
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
    <PageContainer className="space-y-10">
      {/* Timeline archive header */}
      <section className="py-6 lg:py-9">
        <p className="hud-tag hud-tag-accent flex items-center gap-3">
          <span aria-hidden className="h-px w-10 bg-indigo-400/60" />
          Reconstruction archive
        </p>
        <h1 className="hero-display mt-4 text-slate-50">
          <span className="block">REVIEW</span>
          <span className="h-grad block">HISTORY</span>
        </h1>
        <p className="mt-5 max-w-md text-sm leading-relaxed text-slate-400">
          Every AI review you have run, in chronological order. Travel
          backward along the timeline to revisit any analysis.
        </p>
      </section>

      {/* Filter strip */}
      <div className="holo-panel flex flex-wrap items-end gap-4 p-5">
        <label className="flex flex-col gap-1.5">
          <span className="section-title">Repository</span>
          <input
            type="text"
            placeholder="owner/name"
            value={filters.repository}
            onChange={(event) => setFilters((prev) => ({ ...prev, repository: event.target.value }))}
            className="field min-w-[14rem]"
          />
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="section-title">Status</span>
          <select
            value={filters.status}
            onChange={(event) => setFilters((prev) => ({ ...prev, status: event.target.value }))}
            className="field min-w-[12rem]"
          >
            <option value="" className="bg-surface-1 text-slate-100">All</option>
            <option value="complete" className="bg-surface-1 text-slate-100">Complete</option>
            <option value="gemini_unavailable" className="bg-surface-1 text-slate-100">Gemini unavailable</option>
            <option value="failed" className="bg-surface-1 text-slate-100">Failed</option>
          </select>
        </label>
        <button type="button" onClick={applyFilters} className="btn-secondary">
          Apply filters
        </button>

        {data && (
          <span className="ml-auto font-mono text-xs tabular-nums text-slate-600">
            {data.total} review{data.total === 1 ? '' : 's'} found
          </span>
        )}
      </div>

      {loading ? (
        <LoadingState label="Loading history\u2026" />
      ) : error ? (
        <ErrorState title="Could not load history" message={error} retry={() => setApplied({ ...applied })} />
      ) : data && data.items.length === 0 ? (
        <EmptyState
          title="No reviews found"
          description="Try clearing the filters, or run your first AI review."
        />
      ) : data ? (
        <>
          <div className="space-y-10">
            {[...groups.keys()].map((day, groupIndex) => (
              <Reveal key={day} delay={Math.min(groupIndex * 60, 240)}>
                <section className="grid grid-cols-1 gap-5 md:grid-cols-[10rem_1fr]">
                  <div className="relative flex items-start pt-2">
                    <span className="font-mono text-sm font-semibold uppercase tracking-[0.14em] text-slate-300">
                      {day}
                    </span>
                    <span
                      aria-hidden
                      className="absolute bottom-2 left-0 top-9 hidden w-px bg-gradient-to-b from-indigo-500/50 via-white/[0.05] to-transparent md:block"
                    />
                    <span aria-hidden className="hidden md:block md:ml-2">
                      <span className="railing-dot block h-1.5 w-1.5 rounded-full bg-indigo-400 shadow-[0_0_10px_rgba(129,140,248,0.9)]" />
                    </span>
                  </div>
                  <div className="relative space-y-1.5 pl-5 md:pl-10">
                    <span aria-hidden className="timeline-head-dot" />
                    <span
                      aria-hidden
                      className="absolute left-0 top-1.5 h-[calc(100%-1.5rem)] w-px bg-gradient-to-b from-accent-indigo/30 via-white/[0.06] to-transparent md:left-[30px]"
                    />
                    {groups.get(day)?.map((item) => (
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
                </section>
              </Reveal>
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