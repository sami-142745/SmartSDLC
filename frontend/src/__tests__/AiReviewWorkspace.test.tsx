import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, within } from '@testing-library/react';

import { AiReviewWorkspace } from '../components/ai-review/AiReviewWorkspace';
import { AssessmentPanel } from '../components/ai-review/AssessmentPanel';
import { FileRail } from '../components/ai-review/FileRail';
import { sortAiReviewFindings } from '../components/ai-review/FindingList';
import {
  makeAiReview,
  makeAiReviewFile,
  makeAiReviewFinding,
} from '../test/fixtures';
import { renderWithProviders } from '../test/utils';
import { AI_REVIEW_FILE_LEVEL_LINE } from '../types';
import type { AiReviewFinding } from '../types';

beforeEach(() => {
  // The workspace lazily loads Monaco for the split view. jsdom cannot mount
  // it, so it is replaced with a marker for the rest of the suite.
  vi.doMock('../components/diff/MonacoDiff', () => ({
    default: () => <div data-testid="monaco-stub" />,
  }));
});

describe('FileRail', () => {
  it('lists every changed file with its status and change counts', () => {
    renderWithProviders(
      <FileRail
        files={[
          makeAiReviewFile(),
          makeAiReviewFile({
            path: 'assets/logo.png',
            status: 'binary',
            is_binary: true,
            patch: null,
            additions: 0,
            deletions: 0,
          }),
          makeAiReviewFile({ path: 'src/old.py', status: 'deleted', finding_ids: [], additions: 0, deletions: 12 }),
          makeAiReviewFile({
            path: 'src/renamed.py',
            previous_path: 'src/before.py',
            status: 'renamed',
            finding_ids: [],
            additions: 3,
            deletions: 1,
          }),
        ]}
        activePath="src/api/users.py"
        onSelect={() => {}}
      />,
    );

    expect(screen.getByRole('button', { name: /src\/api\/users\.py/ })).toHaveAttribute(
      'aria-current',
      'true',
    );
    expect(screen.getByText('binary')).toBeInTheDocument();
    expect(screen.getByText('deleted')).toBeInTheDocument();
    expect(screen.getByText('renamed')).toBeInTheDocument();
    expect(screen.getByText('+6')).toBeInTheDocument();
    expect(screen.getByText('-2')).toBeInTheDocument();
    expect(screen.getByText('-12')).toBeInTheDocument();
  });

  it('shows how many findings each file has', () => {
    renderWithProviders(
      <FileRail
        files={[makeAiReviewFile({ finding_ids: ['a', 'b', 'c'] })]}
        activePath="src/api/users.py"
        onSelect={() => {}}
      />,
    );

    expect(screen.getByTitle('3 findings')).toBeInTheDocument();
  });

  it('explains an empty diff instead of rendering an empty list', () => {
    renderWithProviders(<FileRail files={[]} activePath={null} onSelect={() => {}} />);

    expect(screen.getByText(/no changed files/i)).toBeInTheDocument();
  });
});

describe('sortAiReviewFindings', () => {
  const findings: AiReviewFinding[] = [
    makeAiReviewFinding({ finding_id: 'low', severity: 'low', confidence: 0.2, file: 'b.py' }),
    makeAiReviewFinding({ finding_id: 'crit', severity: 'critical', confidence: 0.4, file: 'b.py' }),
    makeAiReviewFinding({
      finding_id: 'med',
      severity: 'medium',
      confidence: 0.95,
      file: 'a.py',
      category: 'testing',
    }),
  ];

  it('orders by severity first, using confidence only to break ties', () => {
    expect(sortAiReviewFindings(findings, 'severity').map((f) => f.finding_id)).toEqual([
      'crit',
      'med',
      'low',
    ]);
  });

  it('orders by descending confidence when asked', () => {
    expect(sortAiReviewFindings(findings, 'confidence').map((f) => f.finding_id)).toEqual([
      'med',
      'crit',
      'low',
    ]);
  });

  it('groups by file and line when asked', () => {
    expect(sortAiReviewFindings(findings, 'file').map((f) => f.file)).toEqual([
      'a.py',
      'b.py',
      'b.py',
    ]);
  });

  it('does not mutate the input array', () => {
    const original = [...findings];
    sortAiReviewFindings(findings, 'severity');
    expect(findings).toEqual(original);
  });
});

describe('AssessmentPanel', () => {
  it('labels the score and repeats the disclaimer', () => {
    const review = makeAiReview();
    renderWithProviders(<AssessmentPanel review={review} />);

    expect(screen.getByText('AI review assessment')).toBeInTheDocument();
    expect(screen.getByText('62')).toBeInTheDocument();
    expect(screen.getByText(review.summary.assessment_disclaimer)).toBeInTheDocument();
  });

  it('renders all six assessment dimensions', () => {
    renderWithProviders(<AssessmentPanel review={makeAiReview()} />);

    for (const label of [
      'Bugs',
      'Security',
      'Performance',
      'Quality',
      'Maintainability',
      'Testing',
    ]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it('explains when the model leg did not contribute', () => {
    renderWithProviders(
      <AssessmentPanel review={makeAiReview({ status: 'partial', ai_status: 'unavailable' })} />,
    );

    expect(screen.getByText(/unreachable/i)).toBeInTheDocument();
    expect(screen.getByText(/static analysis only/i)).toBeInTheDocument();
  });

  it('stays quiet about the model when it succeeded', () => {
    renderWithProviders(<AssessmentPanel review={makeAiReview()} />);

    expect(screen.queryByText(/unreachable/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/did not match the expected format/i)).not.toBeInTheDocument();
  });
});

describe('AiReviewWorkspace', () => {
  it('renders the three panes for a stored review', () => {
    renderWithProviders(<AiReviewWorkspace review={makeAiReview()} />);

    expect(screen.getByRole('region', { name: 'Changed files' })).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Diff' })).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Findings' })).toBeInTheDocument();
    expect(screen.getByText('Unvalidated redirect target')).toBeInTheDocument();
  });

  it('navigates to the file and line a finding belongs to', () => {
    const ordersPatch = [
      '--- a/src/api/orders.py',
      '+++ b/src/api/orders.py',
      '@@ -10,2 +10,4 @@ def orders():',
      '     total = 0',
      '+    for row in conn.execute(query):',
      '+        total += row.total',
      '     return total',
      '',
    ].join('\n');

    const review = makeAiReview({
      files: [
        makeAiReviewFile(),
        makeAiReviewFile({
          path: 'src/api/orders.py',
          patch: ordersPatch,
          finding_ids: ['f-2'],
          additions: 2,
          deletions: 0,
        }),
      ],
      findings: [
        makeAiReviewFinding(),
        makeAiReviewFinding({
          finding_id: 'f-2',
          file: 'src/api/orders.py',
          line: 12,
          title: 'Unbounded query',
        }),
      ],
    });

    renderWithProviders(<AiReviewWorkspace review={review} />);

    // Default scope is every file, so the orders finding is reachable even
    // though the centre pane is showing users.py.
    const target = screen.getByText('Unbounded query');
    expect(target).toBeInTheDocument();

    fireEvent.click(target.closest('button') as HTMLButtonElement);

    // The centre pane followed the finding to the other file.
    const diffPane = screen.getByRole('region', { name: 'Diff' });
    expect(within(diffPane).getByText('src/api/orders.py')).toBeInTheDocument();

    // The rail marked the new file as selected. Scoped to the rail because a
    // finding card's accessible name also contains the file path.
    const rail = screen.getByRole('region', { name: 'Changed files' });
    expect(within(rail).getByRole('button', { name: /src\/api\/orders\.py/ })).toHaveAttribute(
      'aria-current',
      'true',
    );
  });

  it('narrows the findings to the selected file on request', () => {
    const review = makeAiReview({
      files: [
        makeAiReviewFile(),
        makeAiReviewFile({ path: 'src/api/orders.py', finding_ids: ['f-2'], additions: 1, deletions: 1 }),
      ],
      findings: [
        makeAiReviewFinding(),
        makeAiReviewFinding({
          finding_id: 'f-2',
          file: 'src/api/orders.py',
          line: 12,
          title: 'Unbounded query',
        }),
      ],
    });

    renderWithProviders(<AiReviewWorkspace review={review} />);

    expect(screen.getByText('Unbounded query')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'This file' }));

    // users.py is the active file and it has no orders.py finding.
    expect(screen.queryByText('Unbounded query')).not.toBeInTheDocument();
    expect(screen.getByText('Unvalidated redirect target')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /src\/api\/orders\.py/ }));

    expect(screen.getByText('Unbounded query')).toBeInTheDocument();
    expect(screen.queryByText('Unvalidated redirect target')).not.toBeInTheDocument();
  });

  it('explains a binary file instead of rendering an empty diff', () => {
    const review = makeAiReview({
      files: [makeAiReviewFile({ path: 'assets/logo.png', status: 'binary', is_binary: true, patch: null })],
      findings: [],
    });

    renderWithProviders(<AiReviewWorkspace review={review} />);

    expect(screen.getByText('Binary file')).toBeInTheDocument();
    expect(screen.getByText(/no textual diff/i)).toBeInTheDocument();
  });

  it('explains a deleted file', () => {
    const review = makeAiReview({
      files: [makeAiReviewFile({ path: 'src/legacy.py', status: 'deleted' })],
      findings: [],
    });

    renderWithProviders(<AiReviewWorkspace review={review} />);

    expect(screen.getByText('File deleted')).toBeInTheDocument();
  });

  it('shows a distinct empty state when the diff has no files at all', () => {
    const review = makeAiReview({ files: [], findings: [] });

    renderWithProviders(<AiReviewWorkspace review={review} />);

    expect(screen.getByText('No changed files to review')).toBeInTheDocument();
  });

  it('labels a file-level finding instead of pointing at line 0', () => {
    const review = makeAiReview({
      findings: [makeAiReviewFinding({ line: AI_REVIEW_FILE_LEVEL_LINE })],
    });

    renderWithProviders(<AiReviewWorkspace review={review} />);

    expect(screen.getByText('whole file')).toBeInTheDocument();
    expect(screen.queryByText('L0')).not.toBeInTheDocument();
  });

  it('filters findings by severity and clears the filter again', () => {
    const review = makeAiReview({
      findings: [
        makeAiReviewFinding({ finding_id: 'sec', severity: 'high', category: 'security' }),
        makeAiReviewFinding({
          finding_id: 'perf',
          severity: 'low',
          category: 'performance',
          title: 'Repeated string concat in a loop',
        }),
      ],
    });

    renderWithProviders(<AiReviewWorkspace review={review} />);

    expect(screen.getByText('Repeated string concat in a loop')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'low' }));

    expect(screen.getByText('Repeated string concat in a loop')).toBeInTheDocument();
    expect(screen.queryByText('Unvalidated redirect target')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'low' }));

    expect(screen.getByText('Unvalidated redirect target')).toBeInTheDocument();
  });

  it('re-sorts findings from the dropdown', () => {
    const review = makeAiReview({
      findings: [
        makeAiReviewFinding({ finding_id: 'a', severity: 'low', confidence: 0.2, title: 'Low confidence nit' }),
        makeAiReviewFinding({
          finding_id: 'b',
          severity: 'critical',
          confidence: 0.95,
          title: 'Critical issue',
        }),
      ],
    });

    renderWithProviders(<AiReviewWorkspace review={review} />);

    const items = within(screen.getByRole('region', { name: 'Findings' })).getAllByRole('listitem');
    expect(items[0]).toHaveTextContent('Critical issue');

    fireEvent.change(screen.getByLabelText('Sort findings'), { target: { value: 'line' } });

    expect(screen.getByLabelText('Sort findings')).toHaveValue('line');
  });
});
