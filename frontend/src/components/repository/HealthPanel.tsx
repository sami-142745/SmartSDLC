import { Card, CardBody, CardHeader } from '../ui/Card';
import { Meter, SCORE_TONE_COLOR, ScoreGauge, scoreTone } from '../ui/ScoreGauge';
import { Badge } from '../ui/Badge';
import type { BadgeTone } from '../ui/Badge';
import type { RepositoryHealth } from '../../types';

const GRADE_TONE: Record<string, BadgeTone> = {
  A: 'success',
  B: 'success',
  C: 'warning',
  D: 'warning',
  F: 'danger',
};

function gradeTone(grade: string): BadgeTone {
  return GRADE_TONE[grade] ?? 'neutral';
}

/**
 * Health breakdown.
 *
 * The gauge shows the overall score, but the honest part is what it was
 * measured from: components with a `null` score are listed separately as
 * unavailable signals, and the measured weight is stated, so a repository with
 * only two observable signals is never presented as a confident 100.
 */
export function HealthPanel({ health, className }: { health: RepositoryHealth; className?: string }) {
  const measured = health.components.filter((component) => component.score !== null);
  const unavailable = health.components.filter((component) => component.score === null);
  const tone = scoreTone(health.score);

  return (
    <Card className={className}>
      <CardHeader
        title="Repository health"
        description={health.method}
        actions={<Badge tone={gradeTone(health.grade)}>Grade {health.grade}</Badge>}
      />
      <CardBody>
        <div className="flex flex-col items-center gap-6 sm:flex-row sm:items-start">
          <div className="shrink-0">
            <ScoreGauge score={health.score} caption="out of 100" label="Health score" />
            <p className="mt-3 text-center text-[11px] text-ink-faint">
              Measured over {(health.measured_weight * 100).toFixed(0)}% of signal weight
            </p>
          </div>

          <div className="w-full min-w-0 flex-1 space-y-5">
            {measured.length > 0 ? (
              <div className="space-y-2.5">
                {measured.map((component) => (
                  <Meter
                    key={component.key}
                    label={component.label}
                    value={component.score as number}
                    color={SCORE_TONE_COLOR[scoreTone(component.score as number)]}
                    showValue
                  />
                ))}
              </div>
            ) : (
              <p className="text-[13px] text-ink-subtle">
                No health signals were observable for this repository.
              </p>
            )}

            {unavailable.length > 0 || health.unavailable_signals.length > 0 ? (
              <div className="rounded-lg border border-amber-400/20 bg-amber-400/[0.05] px-3.5 py-3">
                <p className="text-[12px] font-medium text-amber-200">Not measurable</p>
                <p className="mt-0.5 text-[12px] leading-relaxed text-amber-200/70">
                  These signals are excluded from the score rather than counted as zero:{' '}
                  {(
                    unavailable.length > 0
                      ? unavailable.map((component) => component.label)
                      : health.unavailable_signals
                  ).join(', ')}
                </p>
              </div>
            ) : null}
          </div>
        </div>

        {measured.length > 0 ? (
          <ul className="mt-5 space-y-1.5 border-t border-white/[0.06] pt-4">
            {measured.map((component) => (
              <li key={component.key} className="text-[12px] leading-relaxed text-ink-faint">
                <span className="text-ink-muted">{component.label}</span> — {component.detail}
              </li>
            ))}
          </ul>
        ) : null}
      </CardBody>
    </Card>
  );
}
