import { useMemo, useState } from 'react';

import {
  createSecurityScan,
  getRepositoryPosture,
  getSecurityFindingExplanation,
  getSecurityFindings,
  getSecurityScan,
  getSecurityScans,
} from '../api/security';
import { PageContainer } from '../components/PageContainer';
import { PageHeader } from '../components/PageHeader';
import { ErrorState } from '../components/ErrorState';
import { EmptyState } from '../components/EmptyState';
import { PageSkeleton } from '../components/ui/Skeleton';
import { Card, CardBody, CardHeader } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Donut } from '../components/ui/Charts';
import { ScoreGauge } from '../components/ui/ScoreGauge';
import { SeverityBadge } from '../components/SeverityBadge';
import { Tabs } from '../components/ui/Tabs';
import { useAsync } from '../hooks/useAsync';
import {
  SEVERITY_CHART_COLORS,
  securityCategoryColor,
  securityCategoryLabel,
  securityScannerLabel,
  severityLabel,
  SEVERITY_ORDER,
} from '../utils/severity';
import { cn } from '../lib/cn';
import type {
  SecurityFinding,
  SecurityScan,
  SecuritySeverity,
  SecuritySeverityCounts,
} from '../types';

const OWNER_PATTERN = /^[A-Za-z0-9._-]+$/;

/** How many repositories the "riskiest" panel shows. */
const MAX_RISKIEST = 8;

/** Findings fetched for the detail panel. The API pages beyond this. */
const FINDINGS_PAGE = 100;

type FindingFilter = 'all' | SecuritySeverity;

interface ParsedSlug {
  owner: string;
  repo: string;
}

/** Path-safe owner/repo pair so the typed value maps directly onto a request. */
function parseSlug(input: string): ParsedSlug | null {
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

function formatWhen(iso: string | null): string {
  if (!iso) return 'never';
  const parsed = new Date(iso);
  return Number.isNaN(parsed.getTime()) ? 'unknown' : parsed.toLocaleString();
}

/**
 * A finding at line 0 applies to the whole file, so the location reads as the
 * path alone rather than a misleading "line 0".
 */
function locationLabel(finding: SecurityFinding): string {
  if (!finding.file) return 'repository';
  return finding.line > 0 ? `${finding.file}:${finding.line}` : finding.file;
}

function severitySegments(counts: SecuritySeverityCounts) {
  return SEVERITY_ORDER.filter((severity) => (counts[severity] ?? 0) > 0).map((severity) => ({
    key: severity,
    label: severityLabel(severity),
    value: counts[severity] ?? 0,
    color: SEVERITY_CHART_COLORS[severity],
  }));
}

export function SecurityPage() {
  const [slug, setSlug] = useState('');
  const [slugError, setSlugError] = useState<string | null>(null);
  const [selected, setSelected] = useState<ParsedSlug | null>(null);

  // The recent-scan list is the page's landing state; a repository is opened by
  // typing its slug or by picking one from the list.
  const scans = useAsync(() => getSecurityScans(MAX_RISKIEST), []);

  const [scanning, setScanning] = useState(false);
  const [scanError, setScanError] = useState<string | null>(null);
  const [activeScan, setActiveScan] = useState<SecurityScan | null>(null);

  const openTarget = selected;

  const posture = useAsync(
    () =>
      openTarget
        ? getRepositoryPosture(openTarget.owner, openTarget.repo)
        : Promise.resolve(null),
    [openTarget?.owner, openTarget?.repo],
  );

  // A loaded posture names the scan it came from, so the findings load without
  // the reviewer having to run a second scan or open the stored one by hand.
  const scanId = activeScan?.scan_id ?? posture.data?.scan_id ?? null;

  const findings = useAsync(
    () => (scanId ? getSecurityFindings(scanId, { limit: FINDINGS_PAGE }) : Promise.resolve(null)),
    [scanId],
  );

  const onOpen = (event: React.FormEvent) => {
    event.preventDefault();
    const parsed = parseSlug(slug);
    if (!parsed) {
      setSlugError('Enter a repository as owner/name, for example acme/webapp.');
      return;
    }
    setSlugError(null);
    setSelected(parsed);
    setActiveScan(null);
  };

  const onScan = async () => {
    if (!openTarget) return;
    setScanning(true);
    setScanError(null);
    try {
      const scan = await createSecurityScan({
        owner: openTarget.owner,
        repository: openTarget.repo,
      });
      setActiveScan(scan);
      await Promise.all([posture.refetch(), scans.refetch()]);
    } catch (error) {
      // A failed scan is reported in place. Clearing the page would throw away
      // the last good result, which is the one thing a reviewer still needs.
      setScanError((error as { message?: string }).message ?? 'The scan could not be completed.');
    } finally {
      setScanning(false);
    }
  };

  const onOpenScan = async (scan: SecurityScan) => {
    setSelected({ owner: scan.owner, repo: scan.repository });
    setScanError(null);
    setActiveScan(scan);
  };

  const onLoadScan = async (scan: SecurityScan) => {
    try {
      const full = await getSecurityScan(scan.scan_id);
      setActiveScan(full);
    } catch {
      // The stored summary is enough to render; only the findings are missing.
      setActiveScan(scan);
    }
  };

  // The active scan is authoritative when present, because it is the most
  // recent result. Otherwise the stored posture is what the page shows.
  const summary = activeScan?.summary ?? posture.data?.summary ?? null;

  // The two sources expose different fields, so the header is rendered from one
  // shape. A posture read does not carry the advisory source, so it is left
  // unknown here rather than claimed as "none".
  const postureView = useMemo(() => {
    if (activeScan) {
      return {
        full_name: activeScan.full_name,
        scanned_at: activeScan.scanned_at,
        vulnerability_source: activeScan.vulnerability_source as string | null,
        errors: activeScan.errors,
      };
    }
    const stored = posture.data;
    if (!stored) return null;
    return {
      full_name: stored.full_name,
      scanned_at: stored.scanned_at,
      vulnerability_source: null,
      errors: [] as string[],
    };
  }, [activeScan, posture.data]);

  function advisorySourceLabel(source: string | null): string {
    if (source === null) return 'Not reported in the posture read';
    return source === 'none' ? 'None (pattern analysis only)' : source;
  }

  const hasStoredScans = (scans.data ?? []).length > 0;

  const riskiest = useMemo(() => {
    if (activeScan) {
      // Within one scan, the per-file distribution is the real hotspot list.
      return Object.entries(activeScan.summary.findings_by_file)
        .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
        .slice(0, MAX_RISKIEST)
        .map(([file, count]) => ({ key: file, label: file, value: count }));
    }
    return (scans.data ?? [])
      .filter((scan) => scan.summary.total_findings > 0)
      .sort((a, b) => {
        const bySeverity = b.summary.weighted_risk - a.summary.weighted_risk;
        return bySeverity !== 0 ? bySeverity : b.summary.total_findings - a.summary.total_findings;
      })
      .slice(0, MAX_RISKIEST)
      .map((scan) => ({
        key: scan.scan_id,
        label: scan.full_name,
        value: scan.summary.weighted_risk,
      }));
  }, [activeScan, scans.data]);

  // The ranking is the one panel that is meaningful with no repository open, so
  // it is shared between the loaded and the landing layout instead of being
  // hidden behind a summary that does not exist yet.
  const ranking = (
    <Card>
      <CardHeader
        title={activeScan ? 'Hotspots in this scan' : 'Riskiest repositories'}
        description={
          activeScan
            ? 'Files with the most findings, worst first'
            : 'Weighted exposure across your recent scans'
        }
      />
      <CardBody>
        {riskiest.length > 0 ? (
          <ul
            className="space-y-1.5"
            aria-label={
              activeScan ? 'Files by finding count' : 'Repositories by weighted risk'
            }
          >
            {riskiest.map((item) => {
              const max = riskiest[0]?.value || 1;
              const share = Math.max(4, Math.round((item.value / max) * 100));
              return (
                <li key={item.key} className="flex items-center gap-3">
                  <span className="w-40 shrink-0 truncate font-mono text-[12px] text-ink-muted">
                    {item.label}
                  </span>
                  <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/[0.05]">
                    <span
                      className="block h-full rounded-full bg-accent-violet/60"
                      style={{ width: `${share}%` }}
                    />
                  </span>
                  <span className="w-8 shrink-0 text-right font-mono text-[12px] tabular-nums text-ink-faint">
                    {item.value}
                  </span>
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="py-6 text-center text-[13px] text-ink-faint">
            No findings to rank yet.
          </p>
        )}
      </CardBody>
    </Card>
  );

  if (scans.loading && !scans.data) {
    return (
      <PageContainer>
        <PageSkeleton label="Loading security posture" />
      </PageContainer>
    );
  }

  if (scans.error && !scans.data) {
    return (
      <PageContainer>
        <ErrorState
          title="Could not load the security posture"
          message={scans.error}
          retry={scans.refetch}
        />
      </PageContainer>
    );
  }

  return (
    <PageContainer className="space-y-6">
      <PageHeader
        eyebrow="Posture"
        title="Security"
        description="Deterministic secret, source-code and dependency scanning. No language model assigns severity or computes the score."
        actions={
          summary ? (
            <span className="chip border-accent-violet/25 bg-accent-violet/10 text-accent-lavender">
              {summary.total_findings} findings across {summary.files_scanned} files
            </span>
          ) : null
        }
      />

      <Card>
        <CardHeader
          title="Scan a repository"
          description="Paste a GitHub slug or pick one of your recent scans"
          actions={
            <Button
              size="sm"
              variant="ghost"
              onClick={scans.refetch}
              loading={scans.loading}
            >
              Refresh
            </Button>
          }
        />
        <CardBody className="space-y-4">
          <form onSubmit={onOpen} className="flex flex-col gap-2.5 sm:flex-row">
            <div className="flex-1">
              <label htmlFor="security-repository-slug" className="sr-only">
                Repository
              </label>
              <input
                id="security-repository-slug"
                value={slug}
                onChange={(event) => {
                  setSlug(event.target.value);
                  setSlugError(null);
                }}
                placeholder="owner/repository"
                autoComplete="off"
                spellCheck={false}
                aria-invalid={slugError ? true : undefined}
                className="w-full rounded-lg border border-white/[0.08] bg-surface-0 px-3.5 py-2.5 font-mono text-[13px] text-ink placeholder:text-ink-faint focus:border-accent-violet/50 focus:outline-none"
              />
            </div>
            <Button type="submit" variant="secondary">
              Load posture
            </Button>
            <Button
              type="button"
              variant="primary"
              onClick={onScan}
              disabled={!openTarget}
              loading={scanning}
            >
              Run scan
            </Button>
          </form>
          {slugError ? (
            <p role="alert" className="text-[12px] text-rose-300">
              {slugError}
            </p>
          ) : null}

          {scanning ? (
            <p role="status" className="text-[12px] text-ink-subtle">
              Scanning is in progress. Reading the repository tree and running the secret,
              code and dependency scanners.
            </p>
          ) : null}

          {scanError ? (
            <div role="alert" className="rounded-lg border border-rose-500/25 bg-rose-500/[0.06] px-3.5 py-2.5">
              <p className="text-[12.5px] text-rose-300">{scanError}</p>
              <p className="mt-1 text-[12px] text-ink-faint">
                The previous result, if any, is still shown below.
              </p>
            </div>
          ) : null}

          {posture.error ? (
            <ErrorState
              title="Could not load the repository posture"
              message={posture.error}
              retry={posture.refetch}
            />
          ) : null}

          {postureView ? (
            <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <div>
                <dt className="text-[11px] uppercase tracking-wider text-ink-faint">
                  Repository
                </dt>
                <dd className="mt-0.5 font-mono text-[12.5px] text-ink">
                  {postureView.full_name}
                </dd>
              </div>
              <div>
                <dt className="text-[11px] uppercase tracking-wider text-ink-faint">Scanned</dt>
                <dd className="mt-0.5 text-[12.5px] text-ink-muted">
                  {formatWhen(postureView.scanned_at)}
                </dd>
              </div>
              <div>
                <dt className="text-[11px] uppercase tracking-wider text-ink-faint">
                  Files scanned
                </dt>
                <dd className="mt-0.5 text-[12.5px] text-ink-muted">
                  {summary?.files_scanned ?? 0}
                  {summary && summary.files_skipped > 0
                    ? ` (${summary.files_skipped} skipped)`
                    : ''}
                </dd>
              </div>
              <div>
                <dt className="text-[11px] uppercase tracking-wider text-ink-faint">
                  Advisory source
                </dt>
                <dd className="mt-0.5 text-[12.5px] text-ink-muted">
                  {advisorySourceLabel(postureView.vulnerability_source)}
                </dd>
              </div>
            </dl>
          ) : null}

          {posture.data?.methodology ? (
            <p className="text-[12px] leading-relaxed text-ink-faint">
              {posture.data.methodology}
            </p>
          ) : null}

          {postureView && postureView.errors.length > 0 ? (
            <div
              role="alert"
              className="rounded-lg border border-amber-400/25 bg-amber-400/[0.06] px-3.5 py-2.5"
            >
              <p className="text-[12.5px] text-amber-300">
                {postureView.errors.length} file
                {postureView.errors.length === 1 ? '' : 's'} could not be read. The scan
                completed on the rest.
              </p>
              <ul className="mt-1 space-y-0.5 font-mono text-[11.5px] text-ink-faint">
                {postureView.errors.slice(0, 5).map((error) => (
                  <li key={error}>{error}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </CardBody>
      </Card>

      {!summary ? (
        hasStoredScans ? (
          ranking
        ) : (
          <EmptyState
            title="No security scan yet"
            description="Run a scan on a repository to see its posture, severity mix and the findings behind them."
          />
        )
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <Card>
              <CardHeader
                title="Posture score"
                description="Critical 8x, high 3x, medium 1x"
              />
              <CardBody className="flex flex-col items-center gap-4">
                <ScoreGauge
                  score={summary.posture_score}
                  size={168}
                  thickness={13}
                  label="Security posture"
                  caption="of 100"
                />
                <p className="text-center text-[12px] leading-relaxed text-ink-subtle">
                  Weighted penalty of{' '}
                  <span className="font-mono text-ink-muted">{summary.weighted_risk}</span>{' '}
                  across <span className="font-mono text-ink-muted">{summary.total_findings}</span>{' '}
                  findings.
                </p>
              </CardBody>
            </Card>

            <Card>
              <CardHeader title="Severity mix" description="Where the exposure sits" />
              <CardBody>
                {summary.total_findings > 0 ? (
                  <Donut
                    segments={severitySegments(summary.severity_counts)}
                    size={158}
                    thickness={14}
                    centerValue={summary.total_findings}
                    centerLabel="findings"
                  />
                ) : (
                  <p className="py-8 text-center text-[13px] text-ink-faint">
                    No findings in this scan.
                  </p>
                )}
              </CardBody>
            </Card>

            <Card>
              <CardHeader
                title="Exposure by category"
                description="Recurring weakness themes"
              />
              <CardBody>
                {Object.keys(summary.category_distribution).length > 0 ? (
                  <Donut
                    segments={Object.entries(summary.category_distribution)
                      .filter(([, count]) => count > 0)
                      .sort((a, b) => b[1] - a[1])
                      .map(([key, value]) => ({
                        key,
                        label: securityCategoryLabel(key),
                        value,
                        color: securityCategoryColor(key),
                      }))}
                    size={158}
                    thickness={14}
                    legend
                  />
                ) : (
                  <p className="py-8 text-center text-[13px] text-ink-faint">
                    No categories in this scan.
                  </p>
                )}
              </CardBody>
            </Card>
          </div>

          <Card>
            <CardHeader
              title="Scanner coverage"
              description="Which detector produced each finding"
            />
            <CardBody>
              {Object.keys(summary.scanner_distribution).length > 0 ? (
                <ul className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                  {Object.entries(summary.scanner_distribution).map(([scanner, count]) => (
                    <li
                      key={scanner}
                      className="glass-subtle flex items-center justify-between px-4 py-3"
                    >
                      <span className="truncate text-[12.5px] font-medium text-ink-muted">
                        {securityScannerLabel(scanner)}
                      </span>
                      <span className="font-mono text-[15px] tabular-nums text-ink">
                        {count}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="py-4 text-center text-[13px] text-ink-faint">
                  No scanner produced findings.
                </p>
              )}
            </CardBody>
          </Card>

          {ranking}

          <FindingsPanel
            scanId={scanId}
            loading={findings.loading}
            error={findings.error}
            onRetry={findings.refetch}
            response={findings.data}
          />
        </>
      )}

      <Card>
        <CardHeader
          title="Recent scans"
          description="Your stored security scans, newest first"
        />
        <CardBody>
          {scans.loading ? (
            <PageSkeleton label="Loading recent scans" />
          ) : (scans.data ?? []).length === 0 ? (
            <EmptyState
              title="No scans yet"
              description="Run a scan above and it will be listed here."
            />
          ) : (
            <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {(scans.data ?? []).map((scan) => (
                <li
                  key={scan.scan_id}
                  className="rounded-xl border border-white/[0.06] bg-surface-1/60 px-4 py-3.5"
                >
                  <span className="flex items-center justify-between gap-3">
                    <button
                      type="button"
                      onClick={() => onOpenScan(scan)}
                      className="min-w-0 truncate text-left font-mono text-[13px] font-medium text-ink hover:text-accent-lavender"
                    >
                      {scan.full_name}
                    </button>
                    <Badge
                      tone={
                        scan.summary.posture_score >= 90
                          ? 'success'
                          : scan.summary.posture_score >= 70
                            ? 'warning'
                            : 'danger'
                      }
                    >
                      {scan.summary.posture_score}
                    </Badge>
                  </span>
                  <span className="mt-1.5 block text-[12px] text-ink-faint">
                    {scan.summary.total_findings} findings · {formatWhen(scan.scanned_at)}
                  </span>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="mt-2"
                    onClick={() => onLoadScan(scan)}
                  >
                    View findings
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </CardBody>
      </Card>
    </PageContainer>
  );
}

/**
 * The findings list with a severity filter. Findings are grouped by nothing and
 * sorted by the server, so the page shows the same sequence a scan returns.
 */
function FindingsPanel({
  scanId,
  loading,
  error,
  onRetry,
  response,
}: {
  scanId: string | null;
  loading: boolean;
  error: string | null;
  onRetry: () => unknown;
  response: { total: number; findings: SecurityFinding[] } | null;
}) {
  const [filter, setFilter] = useState<FindingFilter>('all');
  const [expanded, setExpanded] = useState<string | null>(null);

  if (!scanId) return null;

  const findings = response?.findings ?? [];
  const counts = findings.reduce<Partial<Record<SecuritySeverity, number>>>((acc, finding) => {
    acc[finding.severity] = (acc[finding.severity] ?? 0) + 1;
    return acc;
  }, {});
  const visible = filter === 'all' ? findings : findings.filter((f) => f.severity === filter);

  const tabs: { value: FindingFilter; label: string; count: number }[] = [
    { value: 'all', label: 'All', count: findings.length },
    ...SEVERITY_ORDER.filter((severity) => (counts[severity] ?? 0) > 0).map((severity) => ({
      value: severity as FindingFilter,
      label: severityLabel(severity),
      count: counts[severity] ?? 0,
    })),
  ];

  return (
    <Card>
      <CardHeader
        title="Findings"
        description={response ? `${response.total} recorded by the scanners` : undefined}
        actions={
          <Tabs
            items={tabs}
            value={filter}
            onChange={setFilter}
            aria-label="Filter findings by severity"
            size="sm"
            variant="segmented"
          />
        }
      />
      <CardBody>
        {loading ? (
          <PageSkeleton label="Loading findings" />
        ) : error ? (
          <ErrorState title="Could not load the findings" message={error} retry={onRetry} />
        ) : visible.length === 0 ? (
          <EmptyState
            title={findings.length === 0 ? 'No findings' : 'Nothing at this severity'}
            description={
              findings.length === 0
                ? 'The scanners completed without reporting anything on this repository.'
                : 'Choose another severity band to see the rest of the findings.'
            }
          />
        ) : (
          <ul className="space-y-2.5">
            {visible.map((finding) => (
              <li key={finding.finding_id || finding.fingerprint}>
                <FindingRow
                  finding={finding}
                  expanded={expanded === finding.finding_id}
                  onToggle={() =>
                    setExpanded((current) =>
                      current === finding.finding_id ? null : finding.finding_id,
                    )
                  }
                />
              </li>
            ))}
          </ul>
        )}
      </CardBody>
    </Card>
  );
}

/**
 * One finding. The remediation is always visible because it comes from the
 * scanner; the model explanation is opt-in, so a missing model degrades to the
 * deterministic text rather than an empty row.
 */
function FindingRow({
  finding,
  expanded,
  onToggle,
}: {
  finding: SecurityFinding;
  expanded: boolean;
  onToggle: () => void;
}) {
  const [explanation, setExplanation] = useState<{
    text: string;
    impact: string;
    source: string;
  } | null>(null);
  const [explaining, setExplaining] = useState(false);
  const [explanationError, setExplanationError] = useState<string | null>(null);

  const onExplain = async () => {
    setExplaining(true);
    setExplanationError(null);
    try {
      const result = await getSecurityFindingExplanation(finding.finding_id);
      if (result.explanation) {
        setExplanation({
          text: result.explanation,
          impact: result.impact,
          source: result.model ?? 'Model',
        });
      } else {
        setExplanation({
          text: '',
          impact: '',
          source: result.unavailable_reason ?? 'Unavailable',
        });
      }
    } catch (error) {
      setExplanationError(
        (error as { message?: string }).message ?? 'The explanation could not be loaded.',
      );
    } finally {
      setExplaining(false);
    }
  };

  return (
    <div
      className={cn(
        'rounded-xl border border-white/[0.06] bg-surface-1/50 transition-colors',
        expanded && 'border-accent-violet/25',
      )}
    >
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        className="flex w-full items-start gap-3 px-4 py-3 text-left"
      >
        <SeverityBadge severity={finding.severity} />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[13px] font-medium text-ink">
            {finding.title}
          </span>
          <span className="mt-0.5 block truncate font-mono text-[11.5px] text-ink-faint">
            {locationLabel(finding)}
          </span>
        </span>
        <Badge tone="neutral">{securityCategoryLabel(finding.category)}</Badge>
        <Badge tone="neutral">{securityScannerLabel(finding.scanner)}</Badge>
      </button>

      {expanded ? (
        <div className="space-y-3 border-t border-white/[0.05] px-4 py-3.5">
          <p className="text-[12.5px] leading-relaxed text-ink-subtle">{finding.description}</p>
          <div>
            <p className="text-[11px] uppercase tracking-wider text-ink-faint">Remediation</p>
            <p className="mt-0.5 text-[12.5px] leading-relaxed text-ink-muted">
              {finding.remediation}
            </p>
          </div>

          <div>
            <div className="flex items-center gap-2">
              <p className="text-[11px] uppercase tracking-wider text-ink-faint">
                AI explanation
              </p>
              <Button size="sm" variant="ghost" onClick={onExplain} loading={explaining}>
                {explanation ? 'Refresh' : 'Explain'}
              </Button>
            </div>
            {explanationError ? (
              <p role="alert" className="mt-1 text-[12px] text-rose-300">
                {explanationError}
              </p>
            ) : null}
            {explanation ? (
              explanation.text ? (
                <div className="mt-1 space-y-1.5">
                  <p className="text-[12.5px] leading-relaxed text-ink-muted">
                    {explanation.text}
                  </p>
                  {explanation.impact ? (
                    <p className="text-[12.5px] leading-relaxed text-ink-faint">
                      <span className="text-ink-subtle">Impact: </span>
                      {explanation.impact}
                    </p>
                  ) : null}
                  <p className="text-[11px] text-ink-faint">Explained by {explanation.source}</p>
                </div>
              ) : (
                <p className="mt-1 text-[12px] text-ink-faint">
                  No model explanation available ({explanation.source}). The scanner
                  remediation above is authoritative.
                </p>
              )
            ) : (
              <p className="mt-1 text-[12px] text-ink-faint">
                Explanations are optional prose. Severity and score are decided without a model.
              </p>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
