import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { getCachedRepositories } from '../api/repositoryIntelligence';
import { PageContainer } from '../components/PageContainer';
import { PageHeader } from '../components/PageHeader';
import { ErrorState } from '../components/ErrorState';
import { EmptyState } from '../components/EmptyState';
import { PageSkeleton } from '../components/ui/Skeleton';
import { Card, CardBody, CardHeader } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { useAsync } from '../hooks/useAsync';
import type { CachedRepositoryRef } from '../types';

const OWNER_PATTERN = /^[A-Za-z0-9._-]+$/;

/** Path-safe owner/repo pair so the typed value maps directly onto a route. */
function parseSlug(input: string): { owner: string; repo: string } | null {
  const [owner, repo, ...rest] = input
    .trim()
    .replace(/^https?:\/\/[^/]+\//, '')
    .replace(/\.git$/, '')
    .replace(/\/+$/, '')
    .split('/');
  if (!owner || !repo || rest.length > 0) return null;
  if (!OWNER_PATTERN.test(owner) || !OWNER_PATTERN.test(repo)) return null;
  return { owner, repo };
}

export function RepositoryIntelligencePage() {
  const navigate = useNavigate();
  const [slug, setSlug] = useState('');
  const [error, setError] = useState<string | null>(null);
  const cached = useAsync(() => getCachedRepositories(), []);

  const onOpen = (event: React.FormEvent) => {
    event.preventDefault();
    const parsed = parseSlug(slug);
    if (!parsed) {
      setError('Enter a repository as owner/name, for example acme/webapp.');
      return;
    }
    setError(null);
    navigate(
      `/repository-intelligence/${encodeURIComponent(parsed.owner)}/${encodeURIComponent(parsed.repo)}`,
    );
  };

  const open = (entry: CachedRepositoryRef) =>
    navigate(
      `/repository-intelligence/${encodeURIComponent(entry.owner)}/${encodeURIComponent(entry.repository)}`,
    );

  return (
    <PageContainer className="space-y-6">
      <PageHeader
        eyebrow={
          <>
            <span aria-hidden className="h-px w-8 bg-indigo-400/60" />
            Repository intelligence
          </>
        }
        title="Analyse a repository"
        description="Health scoring, language composition, dependency risk, README structure and a browsable source tree — computed deterministically from live provider data and cached server-side."
      />

      <Card>
        <CardHeader
          title="Open a repository"
          description="Paste a GitHub slug or a full repository URL"
        />
        <CardBody>
          <form onSubmit={onOpen} className="flex flex-col gap-2.5 sm:flex-row">
            <div className="flex-1">
              <label htmlFor="repository-slug" className="sr-only">
                Repository
              </label>
              <input
                id="repository-slug"
                value={slug}
                onChange={(event) => {
                  setSlug(event.target.value);
                  setError(null);
                }}
                placeholder="owner/repository"
                autoComplete="off"
                spellCheck={false}
                aria-invalid={error ? true : undefined}
                className="w-full rounded-lg border border-white/[0.08] bg-surface-0 px-3.5 py-2.5 font-mono text-[13px] text-ink placeholder:text-ink-faint focus:border-accent-violet/50 focus:outline-none"
              />
            </div>
            <Button type="submit" variant="primary">
              Analyse
            </Button>
          </form>
          {error ? (
            <p role="alert" className="mt-2.5 text-[12px] text-rose-300">
              {error}
            </p>
          ) : null}
        </CardBody>
      </Card>

      <Card>
        <CardHeader
          title="Recently analysed"
          description="Repositories with a live cached analysis"
          actions={
            cached.data && cached.data.length > 0 ? (
              <Button size="sm" variant="ghost" onClick={cached.refetch} loading={cached.loading}>
                Refresh
              </Button>
            ) : null
          }
        />
        <CardBody>
          {cached.loading ? (
            <PageSkeleton label="Loading recently analysed repositories" />
          ) : cached.error ? (
            <ErrorState
              title="Could not load your analysed repositories"
              message={cached.error}
              retry={cached.refetch}
            />
          ) : !cached.data || cached.data.length === 0 ? (
            <EmptyState
              title="Nothing analysed yet"
              description="Open a repository above and its analysis will be listed here."
            />
          ) : (
            <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {cached.data.map((entry) => (
                <li key={entry.full_name}>
                  <button
                    type="button"
                    onClick={() => open(entry)}
                    className="w-full rounded-xl border border-white/[0.06] bg-surface-1/60 px-4 py-3.5 text-left transition-colors duration-150 hover:border-accent-violet/25 hover:bg-surface-2/50"
                  >
                    <span className="flex items-center justify-between gap-3">
                      <span className="min-w-0 truncate font-mono text-[13px] font-medium text-ink">
                        {entry.full_name}
                      </span>
                      <Badge tone="neutral">Cached</Badge>
                    </span>
                    <span className="mt-1.5 block text-[12px] text-ink-faint">
                      {entry.cached_at
                        ? `Analysed ${new Date(entry.cached_at).toLocaleString()}`
                        : 'Analysis date unavailable'}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </CardBody>
      </Card>
    </PageContainer>
  );
}
