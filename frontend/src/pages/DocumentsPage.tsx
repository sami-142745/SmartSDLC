import { useState } from 'react';

import { getRepositories } from '../api/github';
import { generateDocumentation, getDocumentations } from '../api/documents';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import { PageContainer } from '../components/PageContainer';
import { PageHeader } from '../components/PageHeader';
import { StateBadge } from '../components/Badge';
import { Button } from '../components/ui/Button';
import { Card, CardBody, CardHeader } from '../components/ui/Card';
import { cn } from '../lib/cn';
import { useAsync } from '../hooks/useAsync';
import type { GeneratedDocumentation } from '../types';
import { formatDate } from '../utils/format';

const MISSING = 'Not provided in analyzed files';

function ProseBlock({ title, body }: { title: string; body: string }) {
  if (!body || body === MISSING) return null;
  return (
    <Card>
      <CardHeader title={title} />
      <CardBody>
        <p className="whitespace-pre-line text-sm leading-relaxed text-ink-subtle">{body}</p>
      </CardBody>
    </Card>
  );
}

function ListBlock({ title, items }: { title: string; items: string[] }) {
  const visible = items.filter((item) => item && item !== MISSING);
  if (visible.length === 0) return null;
  return (
    <Card>
      <CardHeader title={title} />
      <CardBody>
        <ul className="space-y-2">
          {visible.map((item) => (
            <li key={item} className="flex items-start gap-2.5 text-sm leading-relaxed text-ink-subtle">
              <span aria-hidden className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-accent-indigo" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </CardBody>
    </Card>
  );
}

function DocumentView({ doc }: { doc: GeneratedDocumentation }) {
  const { source } = doc;
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader
          title={<span className="text-[15px] font-semibold normal-case tracking-normal">{doc.title}</span>}
          description={
            <span className="font-mono">
              {source.repository}
              {source.pull_request ? ` \u00b7 ${source.pull_request}` : ''}
              {source.branch ? ` \u00b7 branch ${source.branch}` : ''}
            </span>
          }
          actions={<StateBadge state={doc.status} />}
        />
        <CardBody>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-3 md:grid-cols-4">
            <div>
              <dt className="eyebrow">Model</dt>
              <dd className="mt-1 font-mono text-xs text-ink-subtle">{doc.model || '\u2014'}</dd>
            </div>
            <div>
              <dt className="eyebrow">Generated</dt>
              <dd className="mt-1 font-mono text-xs text-ink-subtle">{formatDate(doc.generated_at)}</dd>
            </div>
            <div>
              <dt className="eyebrow">Commit</dt>
              <dd className="mt-1 font-mono text-xs text-ink-subtle">
                {source.commit ? source.commit.slice(0, 7) : '\u2014'}
              </dd>
            </div>
            <div>
              <dt className="eyebrow">Duration</dt>
              <dd className="mt-1 font-mono text-xs text-ink-subtle">
                {doc.duration_ms != null ? `${doc.duration_ms} ms` : '\u2014'}
              </dd>
            </div>
          </dl>
        </CardBody>
      </Card>

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
    </div>
  );
}

function VaultRow({
  doc,
  selected,
  onSelect,
}: {
  doc: GeneratedDocumentation;
  selected: boolean;
  onSelect: () => void;
}) {
  const { source } = doc;
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-current={selected ? 'true' : undefined}
      className={cn(
        'w-full rounded-xl border py-2.5 pl-3.5 pr-3 text-left transition-colors duration-150',
        selected
          ? 'border-accent-indigo/30 bg-surface-2/80'
          : 'border-white/[0.06] bg-surface-1/70 hover:border-accent-indigo/20 hover:bg-surface-2/70',
      )}
    >
      <span className="block truncate text-sm text-ink">{doc.title}</span>
      <span className="mt-0.5 block truncate font-mono text-[11px] text-ink-faint">
        {source.repository}
        {source.pull_request ? ` \u00b7 ${source.pull_request}` : ''} \u00b7{' '}
        {formatDate(doc.generated_at)}
      </span>
    </button>
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

  if (repositories.loading) return <LoadingState label="Loading repositories…" />;
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
    <PageContainer className="space-y-6">
      <PageHeader
        eyebrow={
          <>
            <span aria-hidden className="h-px w-8 bg-indigo-400/60" />
            Knowledge synthesis
          </>
        }
        title={
          <>
            <span className="block">AI DOCUMENTATION</span>
            <span className="text-brand-gradient block">Vault</span>
          </>
        }
        description="Generate developer documentation for any connected repository and revisit every archived version, down to the exact commit it was built from."
      />

      <Card tone="flat">
        <CardHeader title="Generator" />
        <CardBody>
          <div className="flex flex-wrap items-end gap-4">
            <label className="flex flex-col gap-1.5">
              <span className="eyebrow">Repository</span>
              <select
                value={selected}
                onChange={(event) => setSelected(event.target.value)}
                aria-label="Repository"
                className="field min-w-[16rem]"
              >
                <option value="" disabled className="bg-surface-1 text-ink">
                  Select a repository…
                </option>
                {repos.map((repo) => (
                  <option key={repo.full_name} value={repo.full_name} className="bg-surface-1 text-ink">
                    {repo.full_name}
                  </option>
                ))}
              </select>
            </label>

            <label className="flex flex-col gap-1.5">
              <span className="eyebrow">Pull request (optional)</span>
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

            <Button
              variant="primary"
              onClick={handleGenerate}
              disabled={generating || !selected}
              loading={generating}
            >
              Generate documentation
            </Button>
          </div>

          {generateError ? (
            <p role="alert" className="mt-4 text-sm text-rose-300">
              {generateError}
            </p>
          ) : null}
        </CardBody>
      </Card>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div>
          {active ? (
            <DocumentView doc={active} />
          ) : (
            <EmptyState
              title="No documentation displayed"
              description="Select a repository and generate, or open an archived document from the vault."
            />
          )}
        </div>

        <Card tone="flat" className="self-start">
          <CardHeader
            title="Vault"
            actions={
              history.data ? (
                <span className="font-mono text-[11.5px] tabular-nums text-ink-faint">
                  {history.data.total} archived
                </span>
              ) : null
            }
          />
          <CardBody>
            {history.loading ? (
              <LoadingState label="Loading vault…" />
            ) : history.error ? (
              <ErrorState
                title="Could not load documentation"
                message={history.error}
                retry={history.refetch}
              />
            ) : history.data && history.data.items.length === 0 ? (
              <EmptyState
                title="No documentation yet"
                description="Generated documents will be archived here for later reference."
              />
            ) : (
              <div className="space-y-1.5">
                {history.data?.items.map((doc) => (
                  <VaultRow
                    key={doc.id}
                    doc={doc}
                    selected={active?.id === doc.id}
                    onSelect={() => setActive(doc)}
                  />
                ))}
              </div>
            )}
          </CardBody>
        </Card>
      </div>
    </PageContainer>
  );
}
