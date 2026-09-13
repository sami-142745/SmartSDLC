import { useState } from 'react';

import { getRepositories } from '../api/github';
import { generateDocumentation, getDocumentations } from '../api/documents';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import { PageContainer } from '../components/PageContainer';
import { StateBadge } from '../components/Badge';
import { CinematicButton } from '../components/ui/CinematicButton';
import { useAsync } from '../hooks/useAsync';
import type { GeneratedDocumentation } from '../types';
import { formatDate } from '../utils/format';

function ProseBlock({ title, body }: { title: string; body: string }) {
  if (!body || body === 'Not provided in analyzed files') return null;
  return (
    <section className="glass-edge block rounded-xl p-5">
      <p className="hud-tag hud-tag-accent mb-3">{title}</p>
      <p className="whitespace-pre-line text-sm leading-relaxed text-slate-300/90">{body}</p>
    </section>
  );
}

function ListBlock({ title, items }: { title: string; items: string[] }) {
  const visible = items.filter((item) => item && item !== 'Not provided in analyzed files');
  if (visible.length === 0) return null;
  return (
    <section className="glass-edge block rounded-xl p-5">
      <p className="hud-tag hud-tag-accent mb-3">{title}</p>
      <ul className="space-y-2">
        {visible.map((item) => (
          <li key={item} className="flex items-start gap-2.5 text-sm leading-relaxed text-slate-300/90">
            <span aria-hidden className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-indigo-400 shadow-[0_0_8px_rgba(129,140,248,0.8)]" />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function DocumentView({ doc }: { doc: GeneratedDocumentation }) {
  const { source } = doc;
  return (
    <section className="space-y-4">
      <div className="glass-edge block rounded-xl p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="text-lg font-semibold text-slate-50">{doc.title}</h2>
            <p className="mt-1 font-mono text-xs text-slate-500">
              {source.repository}
              {source.pull_request ? ` · ${source.pull_request}` : ''}
              {source.branch ? ` · branch ${source.branch}` : ''}
            </p>
          </div>
          <StateBadge state={doc.status} />
        </div>

        <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-2 border-t border-white/[0.05] pt-4 text-sm md:grid-cols-4">
          <div>
            <dt className="hud-tag block">Model</dt>
            <dd className="mt-1 font-mono text-xs text-slate-400">{doc.model || '—'}</dd>
          </div>
          <div>
            <dt className="hud-tag block">Generated</dt>
            <dd className="mt-1 font-mono text-xs text-slate-400">{formatDate(doc.generated_at)}</dd>
          </div>
          <div>
            <dt className="hud-tag block">Commit</dt>
            <dd className="mt-1 font-mono text-xs text-slate-400">
              {source.commit ? source.commit.slice(0, 7) : '—'}
            </dd>
          </div>
          <div>
            <dt className="hud-tag block">Duration</dt>
            <dd className="mt-1 font-mono text-xs text-slate-400">
              {doc.duration_ms != null ? `${doc.duration_ms} ms` : '—'}
            </dd>
          </div>
        </dl>
      </div>

      {doc.status === 'failed' ? (
        <ErrorState title="Documentation generation failed" message={doc.error ?? undefined} />
      ) : (
        <>
          <ProseBlock title="Summary" body={doc.summary} />
          <ProseBlock title="Architecture" body={doc.architecture} />
          <ListBlock title="Modules" items={doc.modules} />
          <ListBlock title="API endpoints" items={doc.api} />
          <ListBlock title="Changes introduced" items={doc.changes} />
          <ListBlock title="Configuration" items={doc.configuration} />
          <ListBlock title="Security considerations" items={doc.security} />
          <ListBlock title="Setup" items={doc.setup} />
        </>
      )}
    </section>
  );
}

export function DocumentsPage() {
  const [selected, setSelected] = useState('');
  const [prNumber, setPrNumber] = useState('');
  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState<string | null>(null);
  const [active, setActive] = useState<GeneratedDocumentation | null>(null);

  const repositories = useAsync(() => getRepositories(1, 100), []);
  const history = useAsync(() => getDocumentations({ perPage: 50 }), []);

  const handleGenerate = async () => {
    const repo = repositories.data?.repositories.find((r) => r.full_name === selected);
    if (!repo) return;
    setGenerating(true);
    setGenerateError(null);
    try {
      const doc = await generateDocumentation({
        owner: repo.owner ?? repo.full_name.split('/')[0],
        repository: repo.name,
        pull_request: prNumber ? Number(prNumber) : undefined,
      });
      setActive(doc);
      history.refetch();
    } catch (err) {
      setGenerateError((err as { message?: string }).message ?? 'Could not generate documentation.');
    } finally {
      setGenerating(false);
    }
  };

  if (repositories.loading) return <LoadingState label="Loading repositories\u2026" />;
  if (repositories.error || !repositories.data) {
    return (
      <ErrorState
        title="Could not load repositories"
        message={repositories.error ?? undefined}
        retry={repositories.refetch}
      />
    );
  }

  const repos = repositories.data.repositories;

  return (
    <PageContainer className="space-y-10">
      {/* Documentation vault hero */}
      <section className="py-6 lg:py-9">
        <p className="hud-tag hud-tag-accent flex items-center gap-3">
          <span aria-hidden className="h-px w-10 bg-indigo-400/60" />
          Knowledge synthesis
        </p>
        <h1 className="hero-display mt-4 text-slate-50">
          <span className="block">AI DOCUMENTATION</span>
          <span className="h-grad block">VAULT</span>
        </h1>
        <p className="mt-5 max-w-md text-sm leading-relaxed text-slate-400">
          Generate developer documentation for any connected repository and
          revisit every archived version, down to the exact commit it was built from.
        </p>
      </section>

      {/* Generator console */}
      <div className="holo-panel flex flex-wrap items-end gap-4 p-5">
        <label className="flex flex-col gap-1.5">
          <span className="section-title">Repository</span>
          <select
            value={selected}
            onChange={(event) => setSelected(event.target.value)}
            aria-label="Repository"
            className="field min-w-[16rem]"
          >
            <option value="" disabled className="bg-surface-1 text-slate-100">
              Select a repository…
            </option>
            {repos.map((repo) => (
              <option key={repo.full_name} value={repo.full_name} className="bg-surface-1 text-slate-100">
                {repo.full_name}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1.5">
          <span className="section-title">Pull request (optional)</span>
          <input
            type="number"
            min={1}
            placeholder="e.g. 12"
            value={prNumber}
            onChange={(event) => setPrNumber(event.target.value)}
            aria-label="Pull request number (optional)"
            className="field w-32"
          />
        </label>

        <CinematicButton onClick={handleGenerate} disabled={generating || !selected}>
          {generating ? (
            <span className="flex items-center gap-2">
              <span
                aria-hidden
                className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-transparent border-t-current"
              />
              Generating…
            </span>
          ) : (
            <>Generate documentation</>
          )}
        </CinematicButton>

        {generateError && <p className="w-full text-sm text-rose-300">{generateError}</p>}
      </div>

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div>
          <div className="mb-4 flex items-center justify-between border-b border-white/[0.06] pb-3">
            <span className="eyebrow">Live document</span>
          </div>
          {active ? (
            <DocumentView doc={active} />
          ) : (
            <EmptyState
              title="No documentation displayed"
              description="Select a repository and generate, or open an archived document from the vault."
            />
          )}
        </div>

        <aside>
          <div className="mb-4 flex items-center justify-between border-b border-white/[0.06] pb-3">
            <span className="eyebrow">Vault</span>
            {history.data && (
              <span className="font-mono text-xs tabular-nums text-slate-500">
                {history.data.total} archived
              </span>
            )}
          </div>

          {history.loading ? (
            <LoadingState label="Loading vault\u2026" />
          ) : history.error ? (
            <ErrorState title="Could not load documentation" message={history.error} retry={history.refetch} />
          ) : history.data && history.data.items.length === 0 ? (
            <EmptyState
              title="No documentation yet"
              description="Generated documents will be archived here for later reference."
            />
          ) : (
            <div className="space-y-1.5">
              {history.data?.items.map((doc) => {
                const { source } = doc;
                return (
                  <button
                    key={doc.id}
                    type="button"
                    onClick={() => setActive(doc)}
                    className={`group/hrow relative w-full overflow-hidden rounded-xl border bg-surface-1/70 py-3 pl-5 pr-4 text-left backdrop-blur-sm transition-all duration-200 hover:-translate-y-0.5 hover:border-accent-indigo/20 hover:bg-surface-2/80 ${
                      active?.id === doc.id
                        ? 'border-accent-indigo/25 bg-surface-2/80 shadow-[0_0_22px_-10px_rgba(99,102,241,0.5)]'
                        : 'border-white/[0.06]'
                    }`}
                  >
                    <span
                      aria-hidden
                      className="pointer-events-none absolute inset-y-0 left-0 w-[3px] rounded-r-full bg-gradient-to-b from-accent-indigo/0 via-accent-indigo/50 to-accent-indigo/0 opacity-0 transition-opacity duration-200 group-hover/hrow:opacity-100"
                    />
                    <span className="block truncate text-sm text-slate-200">{doc.title}</span>
                    <span className="mt-0.5 block font-mono text-[11px] text-slate-600">
                      {source.repository}
                      {source.pull_request ? ` · ${source.pull_request}` : ''} · {formatDate(doc.generated_at)}
                    </span>
                  </button>
                );
              })}
            </div>
          )}
        </aside>
      </div>
    </PageContainer>
  );
}