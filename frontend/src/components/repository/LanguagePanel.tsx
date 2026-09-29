import { Card, CardBody, CardHeader } from '../ui/Card';
import { Donut } from '../ui/Charts';
import { Badge } from '../ui/Badge';
import { formatBytes, languageColor } from './languageColor';
import type { LanguageBreakdown } from '../../types';

/**
 * Language composition by bytes.
 *
 * `percent` comes from the backend as a 0-1 fraction of total bytes. The
 * "Other" bucket is shown separately because the provider only reports its top
 * languages — folding it into one of them would overstate it.
 */
export function LanguagePanel({
  languages,
  className,
}: {
  languages: LanguageBreakdown;
  className?: string;
}) {
  const reported = languages.languages.reduce((sum, slice) => sum + slice.percent, 0);
  const otherPercent = languages.total_bytes > 0 ? languages.other_bytes / languages.total_bytes : 0;

  const segments = [
    ...languages.languages.map((slice) => ({
      key: slice.name,
      label: slice.name,
      value: slice.bytes,
      color: languageColor(slice.name),
    })),
    ...(languages.other_bytes > 0
      ? [{ key: '__other', label: 'Other', value: languages.other_bytes, color: '#52525B' }]
      : []),
  ];

  return (
    <Card className={className}>
      <CardHeader
        title="Language composition"
        description="Share of repository bytes per language"
        actions={<Badge tone="neutral">{formatBytes(languages.total_bytes)}</Badge>}
      />
      <CardBody>
        {languages.total_bytes === 0 ? (
          <p className="py-6 text-center text-[13px] text-ink-subtle">
            The provider did not report any language data for this repository.
          </p>
        ) : (
          <Donut
            segments={segments}
            centerValue={languages.languages.length}
            centerLabel="languages"
          />
        )}

        <dl className="mt-5 grid grid-cols-2 gap-3 border-t border-white/[0.06] pt-4 sm:grid-cols-3">
          <div>
            <dt className="eyebrow">Reported</dt>
            <dd className="mt-1 font-mono text-[13px] tabular-nums text-ink">
              {(reported * 100).toFixed(1)}%
            </dd>
          </div>
          <div>
            <dt className="eyebrow">Unattributed</dt>
            <dd className="mt-1 font-mono text-[13px] tabular-nums text-ink">
              {formatBytes(languages.other_bytes)}
            </dd>
          </div>
          <div>
            <dt className="eyebrow">Coverage</dt>
            <dd className="mt-1 font-mono text-[13px] tabular-nums text-ink">
              {languages.truncated ? 'Partial' : 'Complete'}
            </dd>
          </div>
        </dl>

        {languages.truncated ? (
          <p className="mt-4 text-[12px] leading-relaxed text-ink-faint">
            The provider returns only a limited set of languages, so the figures above are a lower
            bound rather than a complete breakdown.
          </p>
        ) : null}
      </CardBody>
    </Card>
  );
}
