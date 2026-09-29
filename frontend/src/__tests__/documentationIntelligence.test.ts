import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
}));

vi.mock('../api/client', () => ({
  http: { get: mocks.get },
}));

import {
  actionableGaps,
  assetsByKind,
  brokenLinks,
  coverageBand,
  gapsByKind,
  getDocumentationIntelligence,
  leastDocumented,
} from '../api/documentationIntelligence';
import { documentationAsset, documentationIntelligence } from '../test/fixtures';

beforeEach(() => {
  mocks.get.mockReset().mockResolvedValue({ data: documentationIntelligence() });
});

describe('getDocumentationIntelligence', () => {
  it('requests the repository endpoint and returns the payload', async () => {
    const result = await getDocumentationIntelligence('acme', 'webapp');

    expect(mocks.get).toHaveBeenCalledWith(
      '/documentation-intelligence/repositories/acme/webapp',
      { params: {} },
    );
    expect(result.full_name).toBe('acme/webapp');
  });

  it('encodes owner and repository names', async () => {
    await getDocumentationIntelligence('a c', 'we/bapp');
    expect(mocks.get).toHaveBeenCalledWith(
      '/documentation-intelligence/repositories/a%20c/we%2Fbapp',
      { params: {} },
    );
  });

  it('omits the provider unless GitLab is selected', async () => {
    await getDocumentationIntelligence('acme', 'webapp', { provider: 'github' });
    expect(mocks.get).toHaveBeenLastCalledWith(expect.any(String), { params: {} });

    await getDocumentationIntelligence('acme', 'webapp', { provider: 'gitlab' });
    expect(mocks.get).toHaveBeenLastCalledWith(expect.any(String), { params: { provider: 'gitlab' } });
  });

  it('sends max_files in snake_case to match the backend', async () => {
    await getDocumentationIntelligence('acme', 'webapp', { maxFiles: 25 });
    expect(mocks.get).toHaveBeenLastCalledWith(expect.any(String), { params: { max_files: 25 } });
  });

  it('forwards refresh and ref when set', async () => {
    await getDocumentationIntelligence('acme', 'webapp', { ref: 'develop', refresh: true });
    expect(mocks.get).toHaveBeenLastCalledWith(expect.any(String), {
      params: { ref: 'develop', refresh: true },
    });
  });
});

describe('gapsByKind', () => {
  it('groups gaps and keeps the backend ordering within a kind', () => {
    const report = documentationIntelligence({
      gaps: [
        { kind: 'missing_license', severity: 'warning', title: 'A', detail: '', evidence: '', paths: [] },
        { kind: 'thin_readme', severity: 'warning', title: 'B', detail: '', evidence: '', paths: [] },
        { kind: 'missing_license', severity: 'info', title: 'C', detail: '', evidence: '', paths: [] },
      ],
    });

    const grouped = gapsByKind(report.gaps);

    expect(grouped.missing_license.map((gap) => gap.title)).toEqual(['A', 'C']);
    expect(grouped.thin_readme).toHaveLength(1);
  });
});

describe('actionableGaps', () => {
  it('keeps only the gaps the backend marked as warnings', () => {
    const report = documentationIntelligence({
      gaps: [
        { kind: 'missing_license', severity: 'warning', title: 'A', detail: '', evidence: '', paths: [] },
        { kind: 'no_docs_directory', severity: 'info', title: 'B', detail: '', evidence: '', paths: [] },
      ],
    });

    expect(actionableGaps(report).map((gap) => gap.title)).toEqual(['A']);
  });
});

describe('brokenLinks', () => {
  it('reports internal links that do not resolve, with their document', () => {
    const assets = [
      documentationAsset({
        path: 'docs/guide.md',
        links: [
          { text: 'gone', target: './missing.md', internal: true, resolved: false },
          { text: 'ok', target: './here.md', internal: true, resolved: true },
          // An external link is never fetched, so it can never be called broken.
          { text: 'site', target: 'https://example.com', internal: false, resolved: null },
        ],
      }),
    ];

    expect(brokenLinks(assets)).toEqual([{ path: 'docs/guide.md', target: './missing.md' }]);
  });
});

describe('assetsByKind', () => {
  it('returns only the assets of one kind', () => {
    const assets = [
      documentationAsset({ path: 'README.md', kind: 'readme' }),
      documentationAsset({ path: 'docs/adr/0001.md', kind: 'adr' }),
    ];

    expect(assetsByKind(assets, 'adr').map((asset) => asset.path)).toEqual(['docs/adr/0001.md']);
  });
});

describe('leastDocumented', () => {
  it('orders by coverage ascending and drops files with no public symbols', () => {
    const report = documentationIntelligence({
      coverage: [
        { path: 'app/full.py', language: 'python', public_symbols: 2, documented_symbols: 2, coverage: 1, undocumented: [] },
        { path: 'app/empty.py', language: 'python', public_symbols: 0, documented_symbols: 0, coverage: 1, undocumented: [] },
        { path: 'app/half.py', language: 'python', public_symbols: 4, documented_symbols: 0, coverage: 0, undocumented: ['a', 'b', 'c', 'd'] },
      ],
    });

    expect(leastDocumented(report, 5).map((row) => row.path)).toEqual(['app/half.py', 'app/full.py']);
  });

  it('respects the requested limit', () => {
    const report = documentationIntelligence();
    expect(leastDocumented(report, 1)).toHaveLength(1);
  });
});

describe('coverageBand', () => {
  it('maps a score onto published bands', () => {
    expect(coverageBand(100)).toBe('strong');
    expect(coverageBand(80)).toBe('strong');
    expect(coverageBand(79)).toBe('partial');
    expect(coverageBand(50)).toBe('partial');
    expect(coverageBand(49)).toBe('weak');
    expect(coverageBand(20)).toBe('weak');
    expect(coverageBand(19)).toBe('none');
  });
});
