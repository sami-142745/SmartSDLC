import { useMemo, useState } from 'react';

import { Card, CardBody, CardHeader } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { EmptyState } from '../EmptyState';
import { formatBytes } from './languageColor';
import type { ReadmeIntelligence } from '../../types';

type ReadinessKey =
  | 'has_toc'
  | 'has_install_section'
  | 'has_usage_section'
  | 'has_license_section';

const READINESS: { key: ReadinessKey; label: string }[] = [
  { key: 'has_toc', label: 'Table of contents' },
  { key: 'has_install_section', label: 'Install instructions' },
  { key: 'has_usage_section', label: 'Usage examples' },
  { key: 'has_license_section', label: 'License section' },
];

export function ReadmePanel({
  readme,
  className,
}: {
  readme: ReadmeIntelligence;
  className?: string;
}) {
  const [showRaw, setShowRaw] = useState(false);

  const depth = useMemo(
    () => new Set(readme.sections.map((section) => section.level)).size,
    [readme.sections],
  );

  if (!readme.available) {
    return (
      <Card className={className}>
        <CardHeader title="README" />
        <CardBody>
          <EmptyState
            title="No README found"
            description={
              readme.reason ??
              'The provider did not return a README for this repository at its default branch.'
            }
          />
        </CardBody>
      </Card>
    );
  }

  return (
    <div className={className}>
      <Card>
        <CardHeader
          title="README intelligence"
          description={readme.path ?? undefined}
          actions={
            <Button
              size="sm"
              variant="secondary"
              onClick={() => setShowRaw((previous) => !previous)}
              aria-expanded={showRaw}
            >
              {showRaw ? 'Hide source' : 'View source'}
            </Button>
          }
        />
        <CardBody>
          <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div>
              <dt className="eyebrow">Size</dt>
              <dd className="mt-1 font-mono text-[13px] tabular-nums text-ink">
                {formatBytes(readme.size_bytes)}
              </dd>
            </div>
            <div>
              <dt className="eyebrow">Lines</dt>
              <dd className="mt-1 font-mono text-[13px] tabular-nums text-ink">
                {readme.line_count.toLocaleString()}
              </dd>
            </div>
            <div>
              <dt className="eyebrow">Words</dt>
              <dd className="mt-1 font-mono text-[13px] tabular-nums text-ink">
                {readme.word_count.toLocaleString()}
              </dd>
            </div>
            <div>
              <dt className="eyebrow">Sections</dt>
              <dd className="mt-1 font-mono text-[13px] tabular-nums text-ink">
                {readme.sections.length}
              </dd>
            </div>
          </dl>

          <div className="mt-5 grid grid-cols-1 gap-5 border-t border-white/[0.06] pt-5 lg:grid-cols-2">
            <section>
              <p className="eyebrow">Coverage</p>
              <ul className="mt-2.5 space-y-1.5">
                {READINESS.map(({ key, label }) => (
                  <li key={key} className="flex items-center justify-between gap-3 text-[12px]">
                    <span className="text-ink-muted">{label}</span>
                    <Badge tone={readme[key] ? 'success' : 'neutral'} dot>
                      {readme[key] ? 'Present' : 'Missing'}
                    </Badge>
                  </li>
                ))}
              </ul>
            </section>

            <section>
              <p className="eyebrow">Content</p>
              <ul className="mt-2.5 space-y-1.5 text-[12px] text-ink-muted">
                <li className="flex items-center justify-between gap-3">
                  <span>Images</span>
                  <span className="font-mono tabular-nums text-ink-subtle">{readme.images}</span>
                </li>
                <li className="flex items-center justify-between gap-3">
                  <span>Links</span>
                  <span className="font-mono tabular-nums text-ink-subtle">{readme.links}</span>
                </li>
                <li className="flex items-center justify-between gap-3">
                  <span>Code blocks</span>
                  <span className="font-mono tabular-nums text-ink-subtle">{readme.code_blocks}</span>
                </li>
                <li className="flex items-center justify-between gap-3">
                  <span>Badges</span>
                  <span className="font-mono tabular-nums text-ink-subtle">{readme.badge_count}</span>
                </li>
              </ul>

              {readme.languages_used.length > 0 ? (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {readme.languages_used.map((language) => (
                    <Badge key={language} tone="info">
                      {language}
                    </Badge>
                  ))}
                </div>
              ) : null}
            </section>
          </div>
        </CardBody>
      </Card>

      <Card className="mt-4">
        <CardHeader
          title="Document outline"
          description={
            readme.sections.length > 0
              ? `${readme.sections.length} headings across ${depth} level${depth === 1 ? '' : 's'}`
              : undefined
          }
        />
        <CardBody>
          {readme.sections.length === 0 ? (
            <p className="py-4 text-center text-[13px] text-ink-subtle">
              This README has no headings, so there is no outline to show.
            </p>
          ) : (
            <ol className="space-y-1.5">
              {readme.sections.map((section, index) => (
                <li
                  key={`${section.line}-${section.heading}-${index}`}
                  className="rounded-lg border border-white/[0.05] bg-surface-1/40 px-3.5 py-2.5"
                  style={{ marginLeft: `${(section.level - 1) * 14}px` }}
                >
                  <div className="flex items-baseline gap-2.5">
                    <span className="shrink-0 font-mono text-[11px] tabular-nums text-ink-faint">
                      {section.line}
                    </span>
                    <span className="min-w-0 truncate text-[13px] font-medium text-ink">
                      {section.heading}
                    </span>
                  </div>
                  {section.preview ? (
                    <p className="mt-1 line-clamp-2 pl-8 text-[12px] leading-relaxed text-ink-faint">
                      {section.preview}
                    </p>
                  ) : null}
                </li>
              ))}
            </ol>
          )}
        </CardBody>
      </Card>

      {showRaw && readme.raw ? (
        <Card className="mt-4">
          <CardHeader
            title="README source"
            description={`${readme.path ?? 'README'} · ${readme.line_count} lines`}
            actions={
              <Button size="sm" variant="ghost" onClick={() => setShowRaw(false)}>
                Close
              </Button>
            }
          />
          <CardBody>
            <pre className="max-h-[32rem] overflow-auto whitespace-pre-wrap break-words font-mono text-[12px] leading-relaxed text-ink-muted">
              {readme.raw}
            </pre>
          </CardBody>
        </Card>
      ) : null}
    </div>
  );
}
