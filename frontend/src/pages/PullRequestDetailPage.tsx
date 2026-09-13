import { useNavigate, useParams, useSearchParams } from 'react-router-dom';

import { getPullRequest, getPullRequestDiff, getPullRequestFiles } from '../api/github';
import { Badge } from '../components/Badge';
import { DiffViewer } from '../components/DiffViewer';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import { PageContainer } from '../components/PageContainer';
import { Reveal } from '../components/motion/Reveal';
import { CinematicButton } from '../components/ui/CinematicButton';
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

  if (pr.loading)
    return <LoadingState label={`Loading ${changeTerm}\u2026`} />;
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

  return (
    <PageContainer className="space-y-10">
      {/* Chamber masthead */}
      <section className="py-6 lg:py-9">
        <p className="hud-tag hud-tag-accent flex items-center gap-3">
          <span aria-hidden className="h-px w-10 bg-indigo-400/60" />
          <span className="font-mono">
            {owner}/{repo} <span className="text-slate-500">#{pullRequest.number}</span>
          </span>
        </p>

        <div className="mt-6 flex flex-col gap-8 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <h1 className="text-[clamp(2.1rem,5.5vw,4.6rem)] font-semibold leading-[1] tracking-[-0.035em] text-slate-50">
              {pullRequest.title}
            </h1>
            <p className="mt-5 flex flex-wrap items-center gap-4 text-sm text-slate-400">
              <Badge
                className={
                  pullRequest.state === 'open'
                    ? 'border-emerald-500/20 bg-emerald-500/[0.06] text-emerald-300'
                    : 'border-slate-500/25 bg-slate-500/[0.05] text-slate-300'
                }
              >
                {pullRequest.state}
              </Badge>
              <span>
                by <span className="text-slate-200">{pullRequest.user ?? '\u2014'}</span>
              </span>
              <span className="font-mono">
                <span className="text-slate-400">{pullRequest.base ?? ''}</span>
                <span className="mx-1 text-accent-indigo">&#x2190;</span>
                <span className="text-slate-200">{pullRequest.head ?? ''}</span>
              </span>
              <span className="font-mono text-xs text-slate-500">
                Updated {formatShortDate(pullRequest.updated_at)}
              </span>
            </p>
          </div>

          <div className="flex shrink-0 flex-col gap-3 sm:flex-row lg:flex-col xl:flex-row">
            <CinematicButton
              type="button"
              onClick={() => navigate(`/reviews/${owner}/${repo}/${pullRequest.number}${providerQuery}`)}
              className="group relative overflow-hidden rounded-xl border border-white/[0.12] bg-gradient-to-r from-indigo-500/90 via-violet-500/80 to-indigo-500/90 px-6 py-3 text-sm font-semibold text-white shadow-[0_18px_50px_-20px_rgba(99,102,241,0.9),inset_0_1px_0_rgba(255,255,255,0.15)] transition-all duration-200 hover:shadow-[0_22px_60px_-18px_rgba(99,102,241,1)]"
              strength={0.3}
            >
              Run AI review
            </CinematicButton>
            <a
              href={pullRequest.html_url}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-secondary"
            >
              Open on {provider === 'gitlab' ? 'GitLab' : 'GitHub'} &#x2197;
            </a>
          </div>
        </div>
      </section>

      {/* Scan chamber — changed files under a live scan beam */}
      <Reveal>
        <section className="scan-beam holo-panel p-5 sm:p-6">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <span aria-hidden className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-cyan-400 opacity-50" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-cyan-400 shadow-[0_0_8px_rgba(34,211,238,0.8)]" />
              </span>
              <h2 className="section-title">Changed files</h2>
            </div>
            {files.data && files.data.length > 0 && (
              <span className="rounded-full border border-cyan-400/20 bg-cyan-400/[0.06] px-2.5 py-0.5 text-xs font-semibold tabular-nums text-cyan-300">
                {files.data.length} files
              </span>
            )}
          </div>
          <div className="mt-4">
            {files.loading ? (
              <LoadingState label="Loading files\u2026" />
            ) : files.error ? (
              <ErrorState title="Could not load files" message={files.error ?? undefined} retry={files.refetch} />
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
                  <tbody className="divide-y divide-white/[0.04]">
                    {files.data.map((file) => (
                      <tr key={`${file.filename}:${file.status}`} className="transition-colors hover:bg-white/[0.03]">
                        <td className="t-table-td font-mono text-xs">{file.filename}</td>
                        <td className="t-table-td text-xs text-slate-500">{file.status}</td>
                        <td className="t-table-td text-right text-xs font-semibold tabular-nums text-emerald-300">+{file.additions}</td>
                        <td className="t-table-td text-right text-xs font-semibold tabular-nums text-rose-300">&minus;{file.deletions}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyState title="No changed files" />
            )}
          </div>
        </section>
      </Reveal>

      {/* Diff readout */}
      <Reveal delay={90}>
        <section>
          <div className="flex items-center gap-2.5">
            <span aria-hidden className="h-px w-6 bg-indigo-400/50" />
            <h2 className="section-title">Diff</h2>
          </div>
          <div className="mt-4">
            {opened.loading ? (
              <LoadingState label="Loading diff\u2026" />
            ) : opened.error ? (
              <ErrorState title="Could not load the diff" message={opened.error ?? undefined} retry={opened.refetch} />
            ) : opened.data ? (
              <DiffViewer diff={opened.data} />
            ) : (
              <EmptyState title="No diff available" />
            )}
          </div>
        </section>
      </Reveal>
    </PageContainer>
  );
}