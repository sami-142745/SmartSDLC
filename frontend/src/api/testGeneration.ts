import { http } from './client';
import type {
  GeneratedTestFile,
  ScmProvider,
  TestGeneration,
  TestTarget,
  ValidationCode,
} from '../types';

const BASE = '/test-generation';

function repoBase(owner: string, repository: string): string {
  return `${BASE}/repositories/${encodeURIComponent(owner)}/${encodeURIComponent(repository)}`;
}

export interface TestGenerationParams {
  provider?: ScmProvider;
  ref?: string;
  refresh?: boolean;
  maxFiles?: number;
  maxTargets?: number;
}

function repoParams({
  provider,
  ref,
  refresh,
  maxFiles,
  maxTargets,
}: TestGenerationParams): Record<string, string | number | boolean> {
  const params: Record<string, string | number | boolean> = {};
  // GitLab is sent only when explicitly selected so the backend keeps defaulting to GitHub.
  if (provider === 'gitlab') params.provider = 'gitlab';
  if (ref) params.ref = ref;
  if (refresh) params.refresh = true;
  // The backend query parameters are snake_case, matching the rest of the API.
  if (maxFiles !== undefined) params.max_files = maxFiles;
  if (maxTargets !== undefined) params.max_targets = maxTargets;
  return params;
}

/**
 * Proposed tests for one repository, held for review.
 *
 * Nothing here is written to the repository: the backend only ever reads, and
 * this response is a preview. The backend caches it, so a second call is cheap
 * unless `refresh` is set.
 */
export async function getTestGeneration(
  owner: string,
  repository: string,
  options: TestGenerationParams = {},
): Promise<TestGeneration> {
  const { data } = await http.get<TestGeneration>(repoBase(owner, repository), {
    params: repoParams(options),
  });
  return data;
}

/** Targets in the backend's deterministic priority order. */
export function prioritizedTargets(report: TestGeneration): TestTarget[] {
  return [...report.targets].sort(
    (left, right) => right.priority - left.priority || left.file.localeCompare(right.file),
  );
}

/**
 * Files a reviewer must look at before anything else.
 *
 * Anything the screener rejected, then anything it accepted with a finding
 * against it. Takes a file list rather than a report so a caller that has
 * already filtered what it is showing does not report on hidden files.
 */
export function filesNeedingReview(files: GeneratedTestFile[]): GeneratedTestFile[] {
  return files.filter((file) => !file.usable || file.validation.length > 0);
}

/** Files whose bodies were written by a language model, as opposed to scaffolds. */
export function modelWrittenFiles(report: TestGeneration): GeneratedTestFile[] {
  return report.files.filter((file) => file.source === 'gemini');
}

/**
 * Every distinct screening finding, with the files it applies to.
 *
 * Grouped so one repeated finding does not occupy a row per file.
 */
export function issuesByCode(
  report: TestGeneration,
): { code: ValidationCode; detail: string; paths: string[] }[] {
  // Keyed by code *and* detail: two different findings that share a code are
  // two findings, while one finding across several files is one.
  const grouped = new Map<string, { code: ValidationCode; detail: string; paths: Set<string> }>();
  for (const file of report.files) {
    for (const issue of file.validation) {
      const key = `${issue.code}${issue.detail}`;
      const entry = grouped.get(key) ?? {
        code: issue.code,
        detail: issue.detail,
        paths: new Set<string>(),
      };
      entry.paths.add(file.path);
      grouped.set(key, entry);
    }
  }
  return [...grouped.values()]
    .map((entry) => ({ ...entry, paths: [...entry.paths].sort() }))
    .sort(
      (left, right) =>
        right.paths.length - left.paths.length || left.code.localeCompare(right.code),
    );
}

/** Targets grouped by the file that declares them, for a per-file view. */
export function targetsByFile(targets: TestTarget[]): { file: string; targets: TestTarget[] }[] {
  const grouped = new Map<string, TestTarget[]>();
  for (const target of targets) {
    const bucket = grouped.get(target.file);
    if (bucket) bucket.push(target);
    else grouped.set(target.file, [target]);
  }
  return [...grouped.entries()]
    .map(([file, fileTargets]) => ({ file, targets: fileTargets }))
    .sort((left, right) => right.targets.length - left.targets.length || left.file.localeCompare(right.file));
}

/**
 * A plain-language reason for a target, from the backend's own enum.
 *
 * Wording matters here: these are statements about what was observed in test
 * files, not verdicts on the code.
 */
export const REASON_LABEL: Record<TestTarget['reason'], string> = {
  no_test_reference: 'No test references it',
  reference_outside_test_paths: 'Referenced only outside test paths',
  no_test_suite: 'No test suite in this repository',
  tested_only_by_name_match: 'Matched only by name',
};

/**
 * What a screening finding means for the file, in one phrase.
 *
 * `placeholder` is not a defect: it is how a scaffold announces that no model
 * was available, so it is described rather than counted as a problem.
 */
export const ISSUE_LABEL: Record<ValidationCode, string> = {
  syntax_error: 'Will not parse',
  forbidden_import: 'Forbidden import',
  forbidden_call: 'Forbidden call',
  secret_redacted: 'Secret redacted',
  empty: 'Empty',
  too_long: 'Too long',
  too_many_tests: 'Too many tests',
  placeholder: 'Placeholder',
  no_test_detected: 'No test detected',
};

/** A 0-100 priority rendered as one of four bands. */
export function priorityBand(priority: number): 'high' | 'medium' | 'low' | 'minimal' {
  if (priority >= 80) return 'high';
  if (priority >= 60) return 'medium';
  if (priority >= 40) return 'low';
  return 'minimal';
}

/**
 * The strongest claim the report can make about itself.
 *
 * A run that fell back to scaffolds has written no assertions at all, which is
 * a different thing from a run whose assertions were written and not run.
 */
export function proposalStatus(report: TestGeneration): 'model' | 'scaffold' | 'none' {
  if (report.files.length === 0) return 'none';
  return modelWrittenFiles(report).length > 0 ? 'model' : 'scaffold';
}

/**
 * Validate a generated or edited test file without caching.
 *
 * Returns the validated file with screening issues.
 */
export async function validateTestFile(
  owner: string,
  repository: string,
  params: {
    file_path: string;
    language: string;
    framework: string;
    targets: TestTarget[];
    source: string;
    provider?: ScmProvider;
  },
): Promise<import('../types').GeneratedTestFile> {
  const { data } = await http.post<import('../types').GeneratedTestFile>(
    `${BASE}/repositories/${encodeURIComponent(owner)}/${encodeURIComponent(repository)}/validate`,
    null,
    { params: {
      file_path: params.file_path,
      language: params.language,
      framework: params.framework,
      targets: params.targets,
      source: params.source,
      provider: params.provider,
    }}
  );
  return data;
}

/**
 * Regenerate a single test file for the given targets.
 *
 * Returns the regenerated file without modifying the cached report.
 */
export async function regenerateTestFile(
  owner: string,
  repository: string,
  params: {
    file_path: string;
    language: string;
    framework: string;
    targets: TestTarget[];
    source_content: string;
    provider?: ScmProvider;
  },
): Promise<import('../types').GeneratedTestFile> {
  const { data } = await http.post<import('../types').GeneratedTestFile>(
    `${BASE}/repositories/${encodeURIComponent(owner)}/${encodeURIComponent(repository)}/regenerate`,
    null,
    { params: {
      file_path: params.file_path,
      language: params.language,
      framework: params.framework,
      targets: params.targets,
      source_content: params.source_content,
      provider: params.provider,
    }}
  );
  return data;
}