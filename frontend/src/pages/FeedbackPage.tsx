import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { getFeedbackHistory } from '../api/reviews';
import { DataTable } from '../components/DataTable';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import { Pagination } from '../components/Pagination';
import { SeverityBadge } from '../components/SeverityBadge';
import type { FeedbackHistoryResponse, FeedbackItem } from '../types';
import { categoryLabel } from '../utils/severity';
import { formatDate } from '../utils/format';

const PER_PAGE = 20;

export function FeedbackPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [data, setData] = useState<FeedbackHistoryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    getFeedbackHistory(page, PER_PAGE)
      .then(setData)
      .catch((err) => setError((err as { message?: string }).message ?? 'Could not load feedback.'))
      .finally(() => setLoading(false));
  }, [page]);

  useEffect(() => {
    load();
  }, [load]);

  const columns = [
    {
      key: 'pr',
      header: 'Pull request',
      render: (row: FeedbackItem) => (
        <span className="font-medium text-slate-900">
          {row.owner}/{row.repository} #{row.pull_request_number}
        </span>
      ),
    },
    {
      key: 'action',
      header: 'Action',
      render: (row: FeedbackItem) => (
        <span
          className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${
            row.action === 'accepted'
              ? 'bg-emerald-100 text-emerald-800 border-emerald-300'
              : 'bg-red-100 text-red-800 border-red-300'
          }`}
        >
          {row.action}
        </span>
      ),
    },
    {
      key: 'severity',
      header: 'Severity',
      render: (row: FeedbackItem) => <SeverityBadge severity={row.severity} />,
    },
    {
      key: 'category',
      header: 'Category',
      render: (row: FeedbackItem) => (
        <span className="text-slate-600">{categoryLabel(row.category)}</span>
      ),
    },
    {
      key: 'finding',
      header: 'Finding',
      render: (row: FeedbackItem) => (
        <span className="font-mono text-xs text-slate-500">{row.finding_id}</span>
      ),
    },
    {
      key: 'date',
      header: 'Date',
      render: (row: FeedbackItem) => (
        <span className="whitespace-nowrap">{formatDate(row.updated_at ?? row.created_at)}</span>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Feedback</h1>
        <p className="mt-1 text-sm text-slate-500">
          Findings you accepted or dismissed. This feedback helps refine future reviews.
        </p>
      </div>

      {loading ? (
        <LoadingState label="Loading feedback…" />
      ) : error ? (
        <ErrorState title="Could not load feedback" message={error} retry={load} />
      ) : data && data.items.length === 0 ? (
        <EmptyState
          title="No feedback yet"
          description="Accept or dismiss findings on a review to see them here."
        />
      ) : data ? (
        <>
          <DataTable
            columns={columns}
            rows={data.items}
            rowKey={(row) => `${row.review_id}:${row.finding_id}`}
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