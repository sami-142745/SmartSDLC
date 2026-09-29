import { describe, expect, it, vi } from 'vitest';

import {
  filesNeedingReview,
  getTestGeneration,
  issuesByCode,
  modelWrittenFiles,
  prioritizedTargets,
  priorityBand,
  proposalStatus,
  targetsByFile,
} from '../api/testGeneration';
import { generatedTestFile, testGeneration, testTarget } from '../test/fixtures';

// Hoisted, so the factory cannot close over an import: the assertions below
// cover the request, and the selectors are exercised against local fixtures.
const mocks = vi.hoisted(() => ({
  get: vi.fn().mockResolvedValue({ data: {} }),
}));

vi.mock('../api/client', () => ({
  http: { get: mocks.get },
}));

import { http } from '../api/client';

describe('getTestGeneration', () => {
  it('requests the repository endpoint with snake_case parameters', async () => {
    await getTestGeneration('acme', 'webapp', {
      provider: 'gitlab',
      ref: 'main',
      refresh: true,
      maxFiles: 40,
      maxTargets: 12,
    });

    expect(http.get).toHaveBeenCalledWith(
      '/test-generation/repositories/acme/webapp',
      {
        params: {
          provider: 'gitlab',
          ref: 'main',
          refresh: true,
          max_files: 40,
          max_targets: 12,
        },
      },
    );
  });

  it('omits parameters that were not set, so the backend keeps its defaults', async () => {
    vi.mocked(http.get).mockClear();
    await getTestGeneration('acme', 'webapp');

    expect(http.get).toHaveBeenCalledWith('/test-generation/repositories/acme/webapp', {
      params: {},
    });
  });

  it('encodes an owner or repository that contains a slash', async () => {
    vi.mocked(http.get).mockClear();
    await getTestGeneration('a/b', 'web app');
    expect(vi.mocked(http.get).mock.calls[0][0]).toBe('/test-generation/repositories/a%2Fb/web%20app');
  });
});

describe('prioritizedTargets', () => {
  it('orders by descending priority without mutating the input', () => {
    const report = testGeneration();
    const ordered = prioritizedTargets(report);

    expect(ordered.map((target) => target.priority)).toEqual([90, 60]);
    expect(report.targets[0].priority).toBe(60);
  });
});

describe('targetsByFile', () => {
  it('groups targets by their declaring file, largest group first', () => {
    const grouped = targetsByFile([
      testTarget({ qualified_name: 'a' }),
      testTarget({ qualified_name: 'b' }),
      testTarget({ qualified_name: 'c', file: 'app/other.py' }),
    ]);

    expect(grouped).toHaveLength(2);
    expect(grouped[0].file).toBe('app/services/scm.py');
    expect(grouped[0].targets).toHaveLength(2);
  });
});

describe('filesNeedingReview', () => {
  it('includes rejected files and flagged files, and excludes clean ones', () => {
    const files = [
      generatedTestFile({ path: 'tests/clean.py' }),
      generatedTestFile({
        path: 'tests/flagged.py',
        validation: [{ code: 'forbidden_import', detail: '`os` may not be imported' }],
      }),
      generatedTestFile({
        path: 'tests/rejected.py',
        usable: false,
        validation: [{ code: 'syntax_error', detail: 'line 4: invalid syntax' }],
      }),
    ];

    expect(filesNeedingReview(files).map((file) => file.path)).toEqual([
      'tests/flagged.py',
      'tests/rejected.py',
    ]);
  });

  it('reports on the files it is given, so a filtered view is not miscounted', () => {
    const files = [
      generatedTestFile({ path: 'tests/clean.py' }),
      generatedTestFile({ path: 'tests/rejected.py', usable: false }),
    ];

    expect(filesNeedingReview(files.slice(0, 1))).toEqual([]);
  });
});

describe('issuesByCode', () => {
  it('groups a repeated finding into one row listing every affected file', () => {
    const report = testGeneration({
      files: [
        generatedTestFile({
          path: 'tests/a.py',
          validation: [{ code: 'forbidden_call', detail: 'open() is not allowed' }],
        }),
        generatedTestFile({
          path: 'tests/b.py',
          validation: [{ code: 'forbidden_call', detail: 'open() is not allowed' }],
        }),
      ],
    });

    const issues = issuesByCode(report);
    expect(issues).toHaveLength(1);
    expect(issues[0].code).toBe('forbidden_call');
    expect(issues[0].paths).toEqual(['tests/a.py', 'tests/b.py']);
  });
});

describe('modelWrittenFiles', () => {
  it('separates model-written files from deterministic scaffolds', () => {
    const report = testGeneration();
    expect(modelWrittenFiles(report).map((file) => file.path)).toEqual(['tests/test_scm.py']);
  });
});

describe('proposalStatus', () => {
  it('reports a scaffold run distinctly from a model run', () => {
    expect(proposalStatus(testGeneration())).toBe('model');

    const scaffoldOnly = testGeneration({
      files: [generatedTestFile({ source: 'deterministic', model: null })],
    });
    expect(proposalStatus(scaffoldOnly)).toBe('scaffold');

    expect(proposalStatus(testGeneration({ files: [] }))).toBe('none');
  });

  it('does not call a mixed run a scaffold run', () => {
    const mixed = testGeneration({
      files: [
        generatedTestFile({ path: 'tests/a.py', source: 'gemini' }),
        generatedTestFile({ path: 'tests/b.py', source: 'deterministic', model: null }),
      ],
    });
    expect(proposalStatus(mixed)).toBe('model');
  });
});

describe('priorityBand', () => {
  it('maps the score onto four bands', () => {
    expect(priorityBand(100)).toBe('high');
    expect(priorityBand(60)).toBe('medium');
    expect(priorityBand(40)).toBe('low');
    expect(priorityBand(0)).toBe('minimal');
  });
});
