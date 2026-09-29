import { useNavigate, useParams, useSearchParams } from 'react-router-dom';

import { getPullRequest, getPullRequestDiff, getPullRequestFiles } from '../api/github';
import { Badge } from '../components/Badge';
import { DiffViewer } from '../components/DiffViewer';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import { PageContainer } from '../components/PageContainer';
import { PageHeader } from '../components/PageHeader';
import { Card, CardBody, CardHeader } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { useAsync } from '../hooks/useAsync';
import { formatShortDate } from '../utils/format';
import type { ScmProvider } from '../types';

export function PullRequestDetailPage() {
  const { owner, repo, number } = useParams<{ owner: string; repo: string; number: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const prNumber = Number(number);

  const provider: ScmProvider = searchParams.get('provider') === 'gitlab' ? 'gitlab' : 'github';
  const changeTerm = provider === 'gitlab' ? 'merge request' : 'pull request';
  const providerQuery = provider === 'gitlab' ? '?provider=gitlab' : '';

  const pr = useAsync(
    () => getPullRequest(owner ?? '', repo ?? '', prNumber, provider),
    [owner, repo, prNumber, provider],
  );
  const files = useAsync(
    () => getPullRequestFiles(owner ?? '', repo ?? '', prNumber, provider),
    [owner, repo, prNumber, provider],
  );
  const opened = useAsync(
    () => getPullRequestDiff(owner ?? '', repo ?? '', prNumber, provider),
    [owner, repo, prNumber, provider],
  );

  if (pr.loading) return <LoadingState label={`Loading ${changeTerm}\u2026`} />;
  if (pr.error || !pr.data) {
    return (
      <ErrorState
        title={`Could not load this ${changeTerm}`}
        message={pr.error ?? undefined}
        retry={pr.refetch}
      />
    );
  }

  const pullRequest = pr.data;
  const fileCount = files.data?.length ?? 0;

  return (
    <PageContainer className="space-y-6">
      <PageHeader
        eyebrow={
          <>
            <span aria-hidden className="h-px w-8 bg-indigo-400/60" />
            <span className="font-mono">
              {owner}/{repo} #{pullRequest.number}
            </span>
          </>
        }
        title={pullRequest.title}
        description={
          <span className="flex flex-wrap items-center gap-x-4 gap-y-1.5">
            <Badge
              className={
                pullRequest.state === 'open'
                  ? 'border-emerald-500/25 bg-emerald-500/[0.06] text-emerald-300'
                  : 'border-white/10 bg-ink-faint/[0.05] text-ink-muted'
              }
            >
              {pullRequest.state}
            </Badge>
            <span>
              by <span className="text-ink-muted">{pullRequest.user ?? '\u2014'}</span>
            </span>
            <span className="font-mono">
              <span className="text-ink-subtle">{pullRequest.base ?? ''}</span>
              <span className="mx-1 text-accent-indigo">&#x2190;</span>
              <span className="text-ink-muted">{pullRequest.head ?? ''}</span>
            </span>
            <span className="font-mono text-xs">Updated {formatShortDate(pullRequest.updated_at)}</span>
          </span>
        }
        actions={
          <>
            <Button
              variant="primary"
              onClick={() => navigate(`/reviews/${owner}/${repo}/${pullRequest.number}${providerQuery}`)}
            >
              Run AI review
            </Button>
            {/* Sprint 3 surface. No review_id yet, so the page takes the
                owner/repo/number query and offers to start a v2 review. */}
            <Button
              variant="secondary"
              onClick={() =>
                navigate(
                  `/ai-reviews/new?owner=${encodeURIComponent(owner ?? '')}&repository=${encodeURIComponent(
                    repo ?? '',
                  )}&number=${pullRequest.number}${providerQuery}`,
                )
              }
            >
              Review workspace
            </Button>
            <a
              href={pullRequest.html_url}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-secondary"
            >
              Open on {provider === 'gitlab' ? 'GitLab' : 'GitHub'} &#x2197;
            </a>
          </>
        }
      />

      <Card>
        <CardHeader
          title="Changed files"
          description={fileCount > 0 ? `${fileCount} touched by this ${changeTerm}` : undefined}
        />
        <CardBody>
          {files.loading ? (
            <LoadingState label="Loading files…" />
          ) : files.error ? (
            <ErrorState
              title="Could not load files"
              message={files.error ?? undefined}
              retry={files.refetch}
            />
          ) : files.data && files.data.length > 0 ? (
            <div className="t-table-wrap">
              <table className="t-table">
                <thead className="t-table-head">
                  <tr>
                    <th className="t-table-th">File</th>
                    <th className="t-table-th">Status</th>
                    <th className="t-table-th text-right">Additions</th>
                    <th className="t-table-th text-right">Deletions</th>
                  </tr>
                </thead>
                <tbody>
                  {files.data.map((file) => (
                    <tr key={`${file.filename}:${file.status}`}>
                      <td className="t-table-td font-mono text-xs">{file.filename}</td>
                      <td className="t-table-td text-xs text-ink">{file.status}</td>
                      <td className="t-table-td text-right font-mono text-xs font-semibold tabular-nums text-emerald-300">
                        +{file.additions}
                      </td>
                      <td className="t-table-td text-right font-mono text-xs font-semibold tabular-nums text-rose-300">
                        &minus;{file.deletions}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState title="No changed files" />
          )}
        </CardBody>
      </Card>

      <div>
        {opened.loading ? (
          <LoadingState label="Loading diff…" />
        ) : opened.error ? (
          <ErrorState
            title="Could not load the diff"
            message={opened.error ?? undefined}
            retry={opened.refetch}
          />
        ) : opened.data ? (
          <DiffViewer diff={opened.data} />
        ) : (
          <EmptyState title="No diff available" />
        )}
      </div>
    </PageContainer>
  );
}
