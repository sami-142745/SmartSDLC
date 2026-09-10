import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { getHistory } from '../api/dashboard';
import { DataTable } from '../components/DataTable';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import { Pagination } from '../components/Pagination';
import { SeverityBadge } from '../components/SeverityBadge';
import { StateBadge } from '../components/Badge';
import type { HistoryItem } from '../types';
import { formatDate } from '../utils/format';

const PER_PAGE = 20;

interface HistoryFilters {
  repository: string;
  status: string;
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

  const columns = [
    {
      key: 'pr',
      header: 'Pull request',
      render: (row: HistoryItem) => (
        <div>
          <span className="font-medium text-slate-900">
            {row.owner}/{row.repository} #{row.pull_request_number}
          </span>
          {row.pull_request_title && (
            <span className="block text-xs text-slate-500">{row.pull_request_title}</span>
          )}
        </div>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (row: HistoryItem) => <StateBadge state={row.status} />,
    },
    {
      key: 'findings',
      header: 'Findings',
      render: (row: HistoryItem) => (
        <span className="tabular-nums font-medium text-slate-700">{row.total_finding_count}</span>
      ),
    },
    {
      key: 'severity',
      header: 'Severity',
      render: (row: HistoryItem) => <SeverityBadge severity={row.review_severity} />,
    },
    {
      key: 'score',
      header: 'Score',
      render: (row: HistoryItem) => (
        <span className="tabular-nums">{row.review_score != null ? row.review_score : '—'}</span>
      ),
    },
    {
      key: 'date',
      header: 'Reviewed',
      render: (row: HistoryItem) => (
        <span className="whitespace-nowrap">{formatDate(row.created_at)}</span>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Review History</h1>
        <p className="mt-1 text-sm text-slate-500">Every AI review you have run.</p>
      </div>

      <div className="flex flex-wrap items-end gap-4">
        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Repository
          </span>
          <input
            type="text"
            placeholder="owner/name"
            value={filters.repository}
            onChange={(event) => setFilters((prev) => ({ ...prev, repository: event.target.value }))}
            className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm focus:border-slate-400 focus:outline-none"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">Status</span>
          <select
            value={filters.status}
            onChange={(event) => setFilters((prev) => ({ ...prev, status: event.target.value }))}
            className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm focus:border-slate-400 focus:outline-none"
          >
            <option value="">All</option>
            <option value="complete">Complete</option>
            <option value="gemini_unavailable">Gemini unavailable</option>
            <option value="failed">Failed</option>
          </select>
        </label>
        <button
          type="button"
          onClick={applyFilters}
          className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50"
        >
          Apply filters
        </button>
      </div>

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
          <DataTable
            columns={columns}
            rows={data.items}
            rowKey={(row) => `${row.owner}/${row.repository}/${row.pull_request_number}/${row.created_at}`}
            onRowClick={(row) =>
              navigate(`/reviews/${row.owner}/${row.repository}/${row.pull_request_number}`)
            }
          />
          <Pagination
            page={page}
            perPage={PER_PAGE}
            total={data.total}
            totalPages={data.total_pages}
            onPageChange={setPage}
          />
        </>
      ) : null}
    </div>
  );
}