import { NavLink } from 'react-router-dom';

import { cn } from '../../lib/cn';
import type { ScmProvider } from '../../types';

const TABS = [
  { key: 'overview', label: 'Overview', path: '' },
  { key: 'explorer', label: 'Explorer', path: '/explorer' },
  { key: 'dependencies', label: 'Dependencies', path: '/dependencies' },
  { key: 'readme', label: 'README', path: '/readme' },
] as const;

interface RepositorySubnavProps {
  owner: string;
  repository: string;
  provider?: ScmProvider;
  className?: string;
}

/**
 * Tab bar shared by every repository intelligence page. Keeping it in one place
 * means the four views stay reachable from each other and a new view only has
 * to be declared once in `TABS`.
 */
export function RepositorySubnav({ owner, repository, provider, className }: RepositorySubnavProps) {
  const base = `/repository-intelligence/${encodeURIComponent(owner)}/${encodeURIComponent(repository)}`;
  const suffix = provider === 'gitlab' ? '?provider=gitlab' : '';

  return (
    <nav
      aria-label="Repository intelligence views"
      className={cn(
        'flex w-fit max-w-full items-center gap-1 overflow-x-auto rounded-lg border border-white/[0.06] bg-surface-1 p-1',
        className,
      )}
    >
      {TABS.map((tab) => (
        <NavLink
          key={tab.key}
          to={`${base}${tab.path}${suffix}`}
          end
          className={({ isActive }) =>
            cn(
              'whitespace-nowrap rounded-md px-3.5 py-1.5 text-[13px] font-medium transition-colors duration-150',
              isActive
                ? 'bg-white/[0.07] text-ink'
                : 'text-ink-subtle hover:bg-white/[0.03] hover:text-ink-muted',
            )
          }
        >
          {tab.label}
        </NavLink>
      ))}
    </nav>
  );
}
