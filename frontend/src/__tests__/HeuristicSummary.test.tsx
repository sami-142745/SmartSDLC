import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';

import { HeuristicSummary } from '../components/HeuristicSummary';
import { makeFinding } from '../test/fixtures';

describe('HeuristicSummary', () => {
  it('renders nothing when there are no heuristic findings', () => {
    const { container } = render(<HeuristicSummary findings={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('summarizes category counts and pattern severities', () => {
    const findings = [
      makeFinding('a', { category: 'security', heuristic_severity: 'critical', heuristic_confidence: 0.95 }),
      makeFinding('b', { category: 'security', heuristic_severity: 'high', heuristic_confidence: 0.85 }),
      makeFinding('c', { category: 'bug', heuristic_severity: 'high', heuristic_confidence: 0.8 }),
    ];

    render(<HeuristicSummary findings={findings} />);

    expect(screen.getByText('Automated scans')).toBeInTheDocument();
    expect(screen.getByText('3 rule matches')).toBeInTheDocument();
    expect(screen.getByText('Security · 2')).toBeInTheDocument();
    expect(screen.getByText('Bug · 1')).toBeInTheDocument();
    expect(screen.getByText('1 critical pattern')).toBeInTheDocument();
    expect(screen.getByText('2 high patterns')).toBeInTheDocument();
  });

  it('uses the singular form for a single match', () => {
    render(<HeuristicSummary findings={[makeFinding('a')]} />);
    expect(screen.getByText('1 rule match')).toBeInTheDocument();
    expect(screen.getByText('Security · 1')).toBeInTheDocument();
  });
});