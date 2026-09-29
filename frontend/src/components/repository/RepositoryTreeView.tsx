import { Card, CardBody, CardHeader } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { EmptyState } from '../EmptyState';
import { cn } from '../../lib/cn';
import { formatBytes } from './languageColor';
import type { RepositoryTree, RepositoryTreeEntry } from '../../types';

const TYPE_GLYPH: Record<RepositoryTreeEntry['type'], string> = {
  directory: 'M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z',
  file: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6Zm0 2.5V8h3.5',
  submodule: 'M4 4h6v6H4V4Zm10 10h6v6h-6v-6Z',
  commit: 'M12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10Z',
};

/**
 * Flat, hierarchical file listing.
 *
 * The backend already returns entries in depth-first order, so the tree is
 * rendered as an indented list rather than a nested widget — it stays readable
 * at depth, scales to a few thousand rows, and is trivially keyboard-navigable.
 */
export function RepositoryTreeView({
  tree,
  onSelect,
  selectedPath,
  className,
}: {
  tree: RepositoryTree;
  onSelect?: (entry: RepositoryTreeEntry) => void;
  selectedPath?: string | null;
  className?: string;
}) {
  return (
    <Card className={className}>
      <CardHeader
        title="File tree"
        description={
          tree.ref ? `ref ${tree.ref}` : 'default branch'
        }
        actions={
          <div className="flex items-center gap-1.5">
            <Badge tone="neutral">{tree.total_files} files</Badge>
            <Badge tone="neutral">{tree.total_directories} dirs</Badge>
          </div>
        }
      />
      <CardBody>
        {tree.entries.length === 0 ? (
          <EmptyState
            title="No files returned"
            description="The provider returned an empty tree for this ref."
          />
        ) : (
          <>
            <ul className="max-h-[34rem] space-y-px overflow-auto" aria-label="Repository files">
              {tree.entries.map((entry) => {
                const selectable = entry.type === 'file';
                const selected = selectedPath === entry.path;
                return (
                  <li key={entry.path}>
                    <button
                      type="button"
                      disabled={!selectable}
                      onClick={() => onSelect?.(entry)}
                      aria-current={selected ? 'true' : undefined}
                      className={cn(
                        'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-[12px] transition-colors duration-150',
                        selectable
                          ? 'cursor-pointer hover:bg-white/[0.04]'
                          : 'cursor-default',
                        selected && 'bg-accent-violet/12 text-ink',
                      )}
                      style={{ paddingLeft: `${8 + entry.depth * 14}px` }}
                    >
                      <svg
                        viewBox="0 0 24 24"
                        className={cn(
                          'h-3.5 w-3.5 shrink-0',
                          entry.type === 'directory' ? 'text-accent-cyan' : 'text-ink-faint',
                        )}
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.6"
                        aria-hidden="true"
                      >
                        <path d={TYPE_GLYPH[entry.type]} strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                      <span
                        className={cn(
                          'min-w-0 flex-1 truncate font-mono',
                          entry.type === 'directory' ? 'text-ink-muted' : 'text-ink',
                        )}
                      >
                        {entry.name}
                      </span>
                      {entry.type === 'file' && entry.size > 0 ? (
                        <span className="shrink-0 font-mono text-[11px] tabular-nums text-ink-faint">
                          {formatBytes(entry.size)}
                        </span>
                      ) : null}
                    </button>
                  </li>
                );
              })}
            </ul>

            <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-white/[0.06] pt-3.5 text-[12px] text-ink-faint">
              <span className="font-mono tabular-nums">{formatBytes(tree.total_bytes)}</span>
              <span aria-hidden>&middot;</span>
              <span>{tree.entries.length} entries</span>
              {tree.truncated ? (
                <>
                  <span aria-hidden>&middot;</span>
                  <span className="text-amber-300">
                    Partial listing — the provider truncated the tree
                  </span>
                </>
              ) : null}
            </div>
          </>
        )}
      </CardBody>
    </Card>
  );
}
