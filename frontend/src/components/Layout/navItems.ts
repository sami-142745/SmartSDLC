/**
 * Single source of truth for application navigation. The desktop rail, the
 * mobile drawer, the command palette and the breadcrumb all read from here so
 * a new route only has to be declared once.
 */

export interface NavItem {
  to: string;
  label: string;
  /** 24x24 path data, filled with currentColor. */
  icon: string;
  /** Longer routes also match this prefix for active-state purposes. */
  matchPrefixes?: string[];
  description: string;
  /** Optional keyboard shortcut hint shown in the command palette. */
  shortcut?: string;
}

export interface NavGroup {
  id: string;
  label: string;
  items: NavItem[];
}

export const NAV_GROUPS: NavGroup[] = [
  {
    id: 'overview',
    label: 'Overview',
    items: [
      {
        to: '/dashboard',
        label: 'Command Center',
        description: 'Review throughput, risk and acceptance across every repository.',
        icon: 'M3 13h8V3H3v10Zm0 8h8v-6H3v6Zm10 0h8V11h-8v10Zm0-18v6h8V3h-8Z',
      },
      {
        to: '/pull-requests',
        label: 'Pull Requests',
        description: 'Live feed of open change requests with diffs and review state.',
        icon: 'M7 21a2 2 0 1 0 0-4 2 2 0 0 0 0 4Zm10-12a2 2 0 1 0 0-4 2 2 0 0 0 0 4ZM7 3a2 2 0 1 0 0 4 2 2 0 0 0 0-4Zm10 12a2 2 0 1 0 0 4 2 2 0 0 0 0-4Z',
      },
    ],
  },
  {
    id: 'codebase',
    label: 'Codebase',
    items: [
      {
        to: '/repositories',
        label: 'Repositories',
        matchPrefixes: ['/repositories'],
        description: 'Connected repositories, languages and branch health.',
        icon: 'M2 5a3 3 0 0 1 3-3h4l2 2h8a3 3 0 0 1 3 3v10a3 3 0 0 1-3 3H5a3 3 0 0 1-3-3V5Z',
      },
      {
        to: '/security',
        label: 'Security',
        description: 'Posture, severity distribution and recurring vulnerability themes.',
        icon: 'M12 1 3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4Zm0 10.99h7c-.53 4.12-3.28 7.79-7 8.94V12H5V6.3l7-3.11v8.8Z',
      },
      {
        to: '/architecture',
        label: 'Architecture',
        description: 'Service topology, dependency edges and change hotspots.',
        icon: 'M4 4h6v6H4V4Zm10 0h6v6h-6V4ZM4 14h6v6H4v-6Zm10 0h6v6h-6v-6ZM10 7h4v3h-4V7Zm0 7h4v3h-4v-3Z',
      },
      {
        to: '/documentation-coverage',
        label: 'Doc Coverage',
        description: 'Documentation completeness measured from the repository itself: canonical files, README structure and docstring coverage.',
        icon: 'M6 2h9l5 5v15H6V2Zm8 1.5V8h4.5M9 12h7v-1.5H9V12Zm0 3.5h7V14H9v1.5Zm0 3.5h4.5v-1.5H9V19Z',
      },
{
        to: '/test-generator',
        label: 'Test Generator',
        description: 'Proposed tests for public symbols no test file references. Targets are chosen by measurement; only each test body is model-written, and nothing is applied.',
        icon: 'M9 3h6v2h3a2 2 0 0 1 2 2v3h-2V7H6v3H4V7a2 2 0 0 1 2-2h3V3Zm-3 9h2v2h2v2H8v2H6v-2H4v-2h2v-2Zm9 1a2 2 0 1 1 0 4 2 2 0 0 1 0-4Zm2-2h2v2h2v2h-2v2h-2v-2h-2v-2h2v-2Z',
      },
      {
        to: '/supply-chain',
        label: 'Supply Chain',
        description: 'Dependency inventory, licence posture and reproducibility from the repository itself — no registry or advisory feed is consulted.',
        icon: 'M12 4a8 8 0 1 1 0 16 8 8 0 0 1 0-16Zm0 2a6 6 0 1 0 0 12 6 6 0 0 0 0-12Zm-4 0h8v4H8v-4Zm-1 6h6v2H7v-2Z',
      },
      {
        to: '/repository-intelligence',
        matchPrefixes: ['/repository-intelligence'],
        label: 'Repo Intelligence',
        description: 'Health scoring, language mix, dependency risk, README structure and source explorer.',
        icon: 'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm1 5v5.2l3.6 2.1-1 1.7L11 13.4V7h2Z',
      },
    ],
  },
  {
    id: 'intelligence',
    label: 'Intelligence',
    items: [
      {
        to: '/insights',
        label: 'Insights',
        description: 'Generated repository-level risk reports and recommended actions.',
        icon: 'M3 3h2v14h14v2H3V3Zm4 12a2 2 0 1 1 4 0 2 2 0 0 1-4 0Zm6-6a2 2 0 1 1 4 0 2 2 0 0 1-4 0ZM4 5h6v2H4V5Zm2-2h8v2H6V3Z',
      },
      {
        to: '/documents',
        label: 'Documentation',
        description: 'AI-generated documentation with section navigation.',
        icon: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6Zm-1 1.5V8h4.5M8 13h8v-2H8v2Zm0 4h5v-2H8v2Z',
      },
      {
        to: '/chat',
        label: 'AI Chat',
        description: 'Ask questions about findings, reviews and repository context.',
        icon: 'M20 2H4a2 2 0 0 0-2 2v18l4-4h14a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2ZM7 9h10v2H7V9Zm0-3h10v2H7V6Zm0 6h6v2H7v-2Z',
      },
    ],
  },
  {
    id: 'operations',
    label: 'Operations',
    items: [
      {
        to: '/history',
        label: 'Review History',
        description: 'Every completed review, with filters and drill-down.',
        icon: 'M12 4a8 8 0 1 1 0 16 8 8 0 0 1 0-16Zm0 2a6 6 0 1 0 0 12 6 6 0 0 0 0-12Zm-1 2h1.5v4.6l2.7 1.6-.8 1.3-3.4-2V8Z',
      },
      {
        to: '/workflows',
        matchPrefixes: ['/workflows'],
        label: 'Workflows',
        description: 'Webhook-driven pipeline runs and per-stage timings.',
        icon: 'M4 4h5v5H4V4Zm2 2v1h1V6H6Zm9-2h5v5h-5V4Zm2 2v1h1V6h-1ZM4 15h5v5H4v-5Zm2 2v1h1v-1H6Zm9-2h5v5h-5v-5Zm2 2v1h1v-1h-1ZM12 7a1 1 0 1 1 0 2 1 1 0 0 1 0-2Zm0 8a1 1 0 1 1 0 2 1 1 0 0 1 0-2Zm-4 0h8v-4H8v4Z',
      },
      {
        to: '/feedback',
        label: 'Feedback Loop',
        description: 'Reviewer accept/dismiss signals and adaptive weighting.',
        icon: 'M4 4h16a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H8l-4 4V4Zm3 5v2h10V9H7Zm0 4v2h6v-2H7Z',
      },
      {
        to: '/settings',
        label: 'Settings',
        description: 'Account, token scope and webhook delivery log.',
        icon: 'M8.1 2h7.8l1 2.6a6.3 6.3 0 0 1 2 1.2l2.7-.2 2.6 4.6-2 1.6a6.3 6.3 0 0 1 0 2.4l2 1.6-2.6 4.6-2.7-.2a6.3 6.3 0 0 1-2 1.2l-1 2.6H8.1l-1-2.6a6.3 6.3 0 0 1-2-1.2l-2.7.2-2.6-4.6 2-1.6a6.3 6.3 0 0 1 0-2.4l-2-1.6L2.4 7l2.7.2a6.3 6.3 0 0 1 2-1.2L8.1 2Zm1.5 2-.8 2a4.8 4.8 0 0 0-3 1.8l-2-.2-1 1.8 1.6 1.2a4.8 4.8 0 0 0 0 3.6L2.8 15l1 1.8 2-.2a4.8 4.8 0 0 0 3 1.8l.8 2h1.8l.8-2a4.8 4.8 0 0 0 3-1.8l2 .2 1-1.8-1.6-1.2a4.8 4.8 0 0 0 0-3.6L17 9l-1-1.8-2 .2a4.8 4.8 0 0 0-3-1.8l-.8-2H9.6ZM12 9a3 3 0 1 1 0 6 3 3 0 0 1 0-6Zm0 2a1 1 0 1 0 0 2 1 1 0 0 0 0-2Z',
      },
    ],
  },
];

export const NAV_ITEMS: NavItem[] = NAV_GROUPS.flatMap((group) => group.items);

/** Human-readable label for a pathname, falling back to the app name. */
export function navLabelForPath(pathname: string): string | null {
  const exact = NAV_ITEMS.find((item) => item.to === pathname);
  if (exact) return exact.label;
  const prefixed = NAV_ITEMS.find(
    (item) => item.matchPrefixes?.some((prefix) => pathname.startsWith(prefix)),
  );
  if (prefixed) return prefixed.label;
  return null;
}
