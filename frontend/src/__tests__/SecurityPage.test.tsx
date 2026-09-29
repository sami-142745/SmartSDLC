import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const mocks = vi.hoisted(() => ({
  getSecurityScans: vi.fn(),
  getRepositoryPosture: vi.fn(),
  createSecurityScan: vi.fn(),
  getSecurityScan: vi.fn(),
  getSecurityFindings: vi.fn(),
  getSecurityFindingExplanation: vi.fn(),
}));

vi.mock('../api/security', () => ({
  getSecurityScans: mocks.getSecurityScans,
  getRepositoryPosture: mocks.getRepositoryPosture,
  createSecurityScan: mocks.createSecurityScan,
  getSecurityScan: mocks.getSecurityScan,
  getSecurityFindings: mocks.getSecurityFindings,
  getSecurityFindingExplanation: mocks.getSecurityFindingExplanation,
  getSecurityScanners: vi.fn(),
}));

import { SecurityPage } from '../pages/SecurityPage';
import {
  securityExplanation,
  securityFindingsResponse,
  securityFinding,
  securityPosture,
  securityScan,
  securitySeverityCounts,
  securitySummary,
  TEST_TOKEN,
} from '../test/fixtures';
import { renderWithProviders } from '../test/utils';

const render = () =>
  renderWithProviders(<SecurityPage />, { route: '/security', authToken: TEST_TOKEN });

/** Types a slug and submits the form, returning the settled user session. */
async function openRepository(slug = 'octocat/Hello-World') {
  const user = userEvent.setup();
  // The form only exists once the landing read settles, so the input is awaited
  // rather than queried synchronously while the page is still a skeleton.
  await user.type(await screen.findByLabelText('Repository'), slug);
  await user.click(screen.getByRole('button', { name: /load posture/i }));
  return user;
}

/** Opens a repository and expands the first finding row. */
async function openFirstFinding(title = 'Exposed AWS access key') {
  const user = await openRepository();
  await user.click(await screen.findByText(title));
  return user;
}

beforeEach(() => {
  mocks.getSecurityScans.mockReset().mockResolvedValue([securityScan()]);
  mocks.getRepositoryPosture.mockReset().mockResolvedValue(securityPosture());
  mocks.createSecurityScan.mockReset().mockResolvedValue(securityScan());
  mocks.getSecurityScan.mockReset().mockResolvedValue(securityScan());
  mocks.getSecurityFindings.mockReset().mockResolvedValue(securityFindingsResponse());
  mocks.getSecurityFindingExplanation.mockReset().mockResolvedValue(securityExplanation());
});

describe('SecurityPage', () => {
  describe('page states', () => {
    it('shows a loading state while the scan list is fetched', async () => {
      mocks.getSecurityScans.mockReturnValue(new Promise(() => {}));
      render();
      // Awaited so the initial fetch settles inside act before the assertion.
      expect(await screen.findByText(/loading security posture/i)).toBeInTheDocument();
    });

    it('shows an error state when the scan list cannot be loaded', async () => {
      mocks.getSecurityScans.mockRejectedValue(new Error('Backend unreachable'));
      render();
      expect(await screen.findByRole('alert')).toHaveTextContent(
        /could not load the security posture/i,
      );
    });

    it('retries the scan list when the error state is used', async () => {
      mocks.getSecurityScans.mockRejectedValueOnce(new Error('Backend unreachable'));
      render();
      const alert = await screen.findByRole('alert');
      await userEvent.click(within(alert).getByRole('button', { name: /try again/i }));
      expect(mocks.getSecurityScans).toHaveBeenCalledTimes(2);
    });

    it('shows the empty state when the user has never scanned anything', async () => {
      mocks.getSecurityScans.mockResolvedValue([]);
      render();
      expect(await screen.findByText(/no scans yet/i)).toBeInTheDocument();
      expect(screen.getByText(/no security scan yet/i)).toBeInTheDocument();
    });
  });

  describe('loading a repository posture', () => {
    it('rejects a malformed repository slug without calling the API', async () => {
      render();
      await openRepository('not-a-slug');
      expect(await screen.findByText(/enter a repository as owner/i)).toBeInTheDocument();
      expect(mocks.getRepositoryPosture).not.toHaveBeenCalled();
    });

    it('accepts a full repository URL', async () => {
      render();
      await openRepository('https://github.com/octocat/Hello-World');
      await waitFor(() =>
        expect(mocks.getRepositoryPosture).toHaveBeenCalledWith('octocat', 'Hello-World'),
      );
    });

    it('shows the posture score and severity mix from the backend', async () => {
      render();
      await openRepository();
      expect(await screen.findByText('Posture score')).toBeInTheDocument();
      expect(screen.getByText('Severity mix')).toBeInTheDocument();
      expect(screen.getByText('Exposure by category')).toBeInTheDocument();
    });

    it('weights the score deterministically and says so', async () => {
      render();
      await openRepository();
      expect(await screen.findByText(/critical 8x, high 3x, medium 1x/i)).toBeInTheDocument();
    });

    it('states the deterministic methodology', async () => {
      render();
      await openRepository();
      expect(
        await screen.findByText(/deterministic rule and pattern analysis/i),
      ).toBeInTheDocument();
    });

    it('does not claim an advisory source it did not read', async () => {
      render();
      await openRepository();
      // A posture read carries no advisory field, so the page says so rather
      // than implying that no advisory database was consulted.
      expect(
        await screen.findByText(/not reported in the posture read/i),
      ).toBeInTheDocument();
    });

    it('reports that no advisory database was consulted for a fresh scan', async () => {
      render();
      const user = await openRepository();
      await user.click(screen.getByRole('button', { name: /run scan/i }));
      expect(
        await screen.findByText(/none \(pattern analysis only\)/i),
      ).toBeInTheDocument();
    });

    it('shows an unscanned repository as a state, not an error', async () => {
      mocks.getRepositoryPosture.mockResolvedValue(
        securityPosture({
          has_scan: false,
          scan_id: null,
          scanned_at: null,
          summary: securitySummary({
            total_findings: 0,
            severity_counts: securitySeverityCounts(),
            weighted_risk: 0,
            posture_score: 100,
            category_distribution: {},
            scanner_distribution: {},
            findings_by_file: {},
            files_scanned: 0,
          }),
        }),
      );
      render();
      await openRepository();
      // The scan-button stays available so the next step is obvious.
      expect(screen.getByRole('button', { name: /run scan/i })).toBeEnabled();
    });

    it('surfaces a posture failure without discarding the page', async () => {
      mocks.getRepositoryPosture.mockRejectedValue(new Error('Repository not found'));
      render();
      await openRepository();
      expect(
        await screen.findByText(/could not load the repository posture/i),
      ).toBeInTheDocument();
    });
  });

  describe('running a scan', () => {
    it('is disabled until a repository is chosen', async () => {
      render();
      expect(await screen.findByRole('button', { name: /run scan/i })).toBeDisabled();
    });

    it('posts the chosen repository and renders the new result', async () => {
      render();
      const user = await openRepository();
      await user.click(screen.getByRole('button', { name: /run scan/i }));

      await waitFor(() =>
        expect(mocks.createSecurityScan).toHaveBeenCalledWith({
          owner: 'octocat',
          repository: 'Hello-World',
        }),
      );
      expect(await screen.findByText('Hotspots in this scan')).toBeInTheDocument();
    });

    it('shows a scan-in-progress message while the scan runs', async () => {
      let release: (value: unknown) => void = () => {};
      mocks.createSecurityScan.mockReturnValue(
        new Promise((resolve) => {
          release = resolve;
        }),
      );

      render();
      const user = await openRepository();
      await user.click(screen.getByRole('button', { name: /run scan/i }));

      expect(await screen.findByText(/scanning is in progress/i)).toBeInTheDocument();
      release(securityScan());
      await waitFor(() =>
        expect(screen.queryByText(/scanning is in progress/i)).not.toBeInTheDocument(),
      );
    });

    it('reports a failed scan without clearing the previous result', async () => {
      render();
      const user = await openRepository();
      mocks.createSecurityScan.mockRejectedValue(new Error('Repository tree is empty'));

      await user.click(screen.getByRole('button', { name: /run scan/i }));

      const alert = await screen.findByRole('alert');
      expect(alert).toHaveTextContent(/repository tree is empty/i);
      // The previously loaded posture is still on screen.
      expect(screen.getByText('Posture score')).toBeInTheDocument();
    });

    it('reloads the recent-scan list after a successful scan', async () => {
      render();
      const user = await openRepository();
      const before = mocks.getSecurityScans.mock.calls.length;
      await user.click(screen.getByRole('button', { name: /run scan/i }));
      await waitFor(() =>
        expect(mocks.getSecurityScans.mock.calls.length).toBeGreaterThan(before),
      );
    });
  });

  describe('partial coverage', () => {
    it('surfaces files that could not be read', async () => {
      mocks.createSecurityScan.mockResolvedValue(
        securityScan({ errors: ['app/locked.py: server error', 'app/big.py: undecodable'] }),
      );
      render();
      const user = await openRepository();
      await user.click(screen.getByRole('button', { name: /run scan/i }));

      const alert = await screen.findByRole('alert');
      expect(alert).toHaveTextContent(/2 files could not be read/i);
      expect(within(alert).getByText('app/locked.py: server error')).toBeInTheDocument();
    });
  });

  describe('findings', () => {
    it('lists the findings recorded for the loaded scan', async () => {
      render();
      await openRepository();
      expect(await screen.findByText('Exposed AWS access key')).toBeInTheDocument();
      expect(screen.getByText('SQL query built by concatenation')).toBeInTheDocument();
    });

    it('shows the file and line for each finding', async () => {
      render();
      await openRepository();
      expect(await screen.findByText('app/config.py:4')).toBeInTheDocument();
      expect(screen.getByText('app/db.py:22')).toBeInTheDocument();
    });

    it('renders a file-level finding without a misleading line number', async () => {
      mocks.getSecurityFindings.mockResolvedValue(
        securityFindingsResponse({
          findings: [securityFinding({ line: 0, file: 'app/config.py' })],
        }),
      );
      render();
      await openRepository();
      expect(await screen.findByText('app/config.py')).toBeInTheDocument();
    });

    it('expands a finding to show its scanner remediation', async () => {
      render();
      const user = await openFirstFinding();
      expect(
        screen.getByText(/revoke the key and load it from the environment/i),
      ).toBeInTheDocument();
    });

    it('filters findings by severity band', async () => {
      render();
      const user = await openRepository();
      await user.click(await screen.findByRole('tab', { name: /^high/i }));

      expect(screen.queryByText('Exposed AWS access key')).not.toBeInTheDocument();
      expect(screen.getByText('SQL query built by concatenation')).toBeInTheDocument();
    });

    it('shows a no-results state when the scan found nothing', async () => {
      mocks.getSecurityFindings.mockResolvedValue(securityFindingsResponse({ findings: [] }));
      render();
      await openRepository();
      expect(await screen.findByText(/no findings/i)).toBeInTheDocument();
    });

    it('reports a findings failure', async () => {
      mocks.getSecurityFindings.mockRejectedValue(new Error('Findings are unavailable'));
      render();
      await openRepository();
      expect(
        await screen.findByText(/could not load the findings/i),
      ).toBeInTheDocument();
    });
  });

  describe('AI explanation', () => {
    it('requests and displays the explanation for a finding', async () => {
      render();
      const user = await openFirstFinding();
      await user.click(screen.getByRole('button', { name: /^explain$/i }));

      await waitFor(() =>
        expect(mocks.getSecurityFindingExplanation).toHaveBeenCalledWith('f-1'),
      );
      expect(await screen.findByText(/committed to source control/i)).toBeInTheDocument();
    });

    it('falls back to the scanner remediation when the model is unavailable', async () => {
      mocks.getSecurityFindingExplanation.mockResolvedValue(
        securityExplanation({
          explanation: '',
          impact: '',
          model: null,
          unavailable_reason: 'Gemini is not configured for this deployment',
        }),
      );
      render();
      const user = await openFirstFinding();
      await user.click(screen.getByRole('button', { name: /^explain$/i }));

      expect(await screen.findByText(/no model explanation available/i)).toBeInTheDocument();
      // The deterministic remediation is still authoritative above it.
      expect(
        screen.getByText(/revoke the key and load it from the environment/i),
      ).toBeInTheDocument();
    });

    it('reports an explanation failure without hiding the finding', async () => {
      mocks.getSecurityFindingExplanation.mockRejectedValue(new Error('Model is overloaded'));
      render();
      const user = await openFirstFinding();
      await user.click(screen.getByRole('button', { name: /^explain$/i }));

      expect(await screen.findByText(/model is overloaded/i)).toBeInTheDocument();
      expect(
        screen.getByText(/revoke the key and load it from the environment/i),
      ).toBeInTheDocument();
    });

    it('states that severity and score are decided without a model', async () => {
      render();
      await openFirstFinding();
      expect(
        screen.getByText(/severity and score are decided without a model/i),
      ).toBeInTheDocument();
    });

    it('does not request an explanation until the reviewer asks for one', async () => {
      render();
      await openFirstFinding();
      expect(mocks.getSecurityFindingExplanation).not.toHaveBeenCalled();
    });
  });

  describe('recent scans', () => {
    it('lists the stored scans', async () => {
      render();
      expect(await screen.findAllByText('octocat/Hello-World')).not.toHaveLength(0);
    });

    it('loads the findings of a stored scan on demand', async () => {
      const user = userEvent.setup();
      render();
      await user.click(await screen.findByRole('button', { name: /view findings/i }));
      await waitFor(() => expect(mocks.getSecurityScan).toHaveBeenCalledWith('scan-1'));
      expect(await screen.findByText('Exposed AWS access key')).toBeInTheDocument();
    });

    it('still renders the stored summary when the scan read fails', async () => {
      mocks.getSecurityScan.mockRejectedValue(new Error('Scan not found'));
      const user = userEvent.setup();
      render();
      await user.click(await screen.findByRole('button', { name: /view findings/i }));

      expect(await screen.findByText('Posture score')).toBeInTheDocument();
    });

    it('ranks repositories by weighted exposure, worst first', async () => {
      mocks.getSecurityScans.mockResolvedValue([
        securityScan({
          scan_id: 'scan-low',
          full_name: 'octocat/quiet',
          owner: 'octocat',
          repository: 'quiet',
          summary: securitySummary({
            weighted_risk: 2,
            posture_score: 98,
            total_findings: 1,
          }),
        }),
        securityScan({
          scan_id: 'scan-high',
          full_name: 'octocat/noisy',
          owner: 'octocat',
          repository: 'noisy',
          summary: securitySummary({
            weighted_risk: 40,
            posture_score: 61,
            total_findings: 6,
          }),
        }),
      ]);
      render();

      const list = await screen.findByRole('list', {
        name: /repositories by weighted risk/i,
      });
      const items = within(list).getAllByRole('listitem');
      expect(items[0]).toHaveTextContent('octocat/noisy');
      expect(items[1]).toHaveTextContent('octocat/quiet');
    });
  });

  describe('secret safety', () => {
    it('renders only what the scanner returns, and no raw credential material', async () => {
      mocks.getSecurityFindings.mockResolvedValue(
        securityFindingsResponse({ findings: [securityFinding({ line: 0 })] }),
      );
      render();
      await openRepository();

      expect(await screen.findByText('Exposed AWS access key')).toBeInTheDocument();
      expect(document.body.textContent ?? '').not.toMatch(/AKIA[0-9A-Z]{16}/);
    });
  });
});
