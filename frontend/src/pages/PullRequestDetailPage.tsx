import { useNavigate, useParams } from 'react-router-dom';

import { getPullRequest, getPullRequestDiff, getPullRequestFiles } from '../api/github';
import { Badge } from '../components/Badge';
import { DiffViewer } from '../components/DiffViewer';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import { useAsync } from '../hooks/useAsync';
import { formatShortDate } from '../utils/format';

export function PullRequestDetailPage() {
  const { owner, repo, number } = useParams<{ owner: string; repo: string; number: string }>();
  const navigate = useNavigate();
  const prNumber = Number(number);

  const pr = useAsync(() => getPullRequest(owner ?? '', repo ?? '', prNumber), [owner, repo, prNumber]);
  const files = useAsync(
    () => getPullRequestFiles(owner ?? '', repo ?? '', prNumber),
    [owner, repo, prNumber],
  );
  const opened = useAsync(
    () => getPullRequestDiff(owner ?? '', repo ?? '', prNumber),
    [owner, repo, prNumber],
  );

  if (pr.loading) return <LoadingState label="Loading pull request…" />;
  if (pr.error || !pr.data) {
    return (
      <ErrorState
        title="Could not load this pull request"
        message={pr.error ?? undefined}
        retry={pr.refetch}
      />
    );
  }

  const pullRequest = pr.data;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-sm text-slate-500">
            {owner}/{repo} #{pullRequest.number}
          </p>
          <h1 className="mt-1 text-2xl font-semibold text-slate-900">{pullRequest.title}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-3 text-sm text-slate-500">
            <Badge
              className={
                pullRequest.state === 'open'
                  ? 'bg-emerald-100 text-emerald-800 border-emerald-300'
                  : 'bg-slate-100 text-slate-700 border-slate-300'
              }
            >
              {pullRequest.state}
            </Badge>
            <span>by {pullRequest.user ?? '—'}</span>
            <span className="font-mono">
              {pullRequest.base ?? ''} ← {pullRequest.head ?? ''}
            </span>
            <span>Updated {formatShortDate(pullRequest.updated_at)}</span>
          </div>
        </div>
        <div className="flex shrink-0 flex-col gap-2">
          <button
            type="button"
            onClick={() => navigate(`/reviews/${owner}/${repo}/${pullRequest.number}`)}
            className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-emerald-700"
          >
            Run AI review
          </button>
          <a
            href={pullRequest.html_url}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-md border border-slate-300 bg-white px-4 py-2 text-center text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50"
          >
            Open on GitHub ↗
          </a>
        </div>
      </div>

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-500">
          Changed files
        </h2>
        {files.loading ? (
          <LoadingState label="Loading files…" />
        ) : files.error ? (
          <ErrorState title="Could not load files" message={files.error ?? undefined} retry={files.refetch} />
        ) : files.data && files.data.length > 0 ? (
          <div className="overflow-x-auto rounded-lg border border-slate-200">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">File</th>
                  <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">Status</th>
                  <th className="px-4 py-2 text-right text-xs font-semibold uppercase tracking-wide text-slate-500">Additions</th>
                  <th className="px-4 py-2 text-right text-xs font-semibold uppercase tracking-wide text-slate-500">Deletions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {files.data.map((file) => (
                  <tr key={`${file.filename}:${file.status}`} className="hover:bg-slate-50">
                    <td className="px-4 py-2 font-mono text-xs text-slate-700">{file.filename}</td>
                    <td className="px-4 py-2 text-xs text-slate-500">{file.status}</td>
                    <td className="px-4 py-2 text-right text-xs tabular-nums text-emerald-600">+{file.additions}</td>
                    <td className="px-4 py-2 text-right text-xs tabular-nums text-red-600">−{file.deletions}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No changed files" />
        )}
      </section>

      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">Diff</h2>
        {opened.loading ? (
          <LoadingState label="Loading diff…" />
        ) : opened.error ? (
          <ErrorState title="Could not load the diff" message={opened.error ?? undefined} retry={opened.refetch} />
        ) : opened.data ? (
          <DiffViewer diff={opened.data} />
        ) : (
          <EmptyState title="No diff available" />
        )}
      </section>
    </div>
  );
}