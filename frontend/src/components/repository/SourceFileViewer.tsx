import { lazy, Suspense } from 'react';

import { Card, CardBody, CardHeader } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { formatBytes } from './languageColor';
import { MONACO_THEME, defineMonacoTheme } from '../diff/monacoTheme';
import type { RepositoryFileContent } from '../../types';

/**
 * Monaco is ~2MB, so the editor is code-split and only fetched once a file is
 * actually opened. A plain `<pre>` renders in the meantime, which keeps the
 * panel readable for anyone whose network is slow or whose test environment
 * stubs the editor.
 */
const MonacoViewer = lazy(() =>
  import('@monaco-editor/react').then((module) => ({ default: module.Editor })),
);

function EditorFallback({ content }: { content: string }) {
  return (
    <pre className="max-h-[32rem] overflow-auto whitespace-pre font-mono text-[12px] leading-relaxed text-ink-muted">
      {content}
    </pre>
  );
}

export function SourceFileViewer({
  file,
  onClose,
  className,
}: {
  file: RepositoryFileContent;
  onClose?: () => void;
  className?: string;
}) {
  if (file.binary) {
    return (
      <Card className={className}>
        <CardHeader
          title={file.path}
          actions={<Badge tone="warning">Binary file</Badge>}
        />
        <CardBody>
          <p className="text-[13px] text-ink-subtle">
            This file is binary, so there is no readable source to display. Size:{' '}
            <span className="font-mono tabular-nums text-ink">{formatBytes(file.size)}</span>.
          </p>
        </CardBody>
      </Card>
    );
  }

  return (
    <Card className={className}>
      <CardHeader
        title={file.path}
        actions={
          <div className="flex items-center gap-1.5">
            {file.language ? <Badge tone="info">{file.language}</Badge> : null}
            <Badge tone="neutral">{formatBytes(file.size)}</Badge>
            {file.truncated ? <Badge tone="warning">Truncated</Badge> : null}
            {onClose ? (
              <button
                type="button"
                onClick={onClose}
                className="rounded-md px-2 py-1 text-[12px] text-ink-subtle transition-colors hover:text-ink"
              >
                Close
              </button>
            ) : null}
          </div>
        }
      />
      <CardBody>
        {file.truncated ? (
          <p className="mb-3 text-[12px] text-amber-300">
            The provider returned only part of this file because it is large.
          </p>
        ) : null}
        <div className="overflow-hidden rounded-lg border border-white/[0.07] bg-surface-0">
          <Suspense fallback={<EditorFallback content={file.content} />}>
            <MonacoViewer
              value={file.content}
              language={file.language ?? 'plaintext'}
              theme={MONACO_THEME}
              beforeMount={defineMonacoTheme}
              options={{
                readOnly: true,
                fontSize: 12,
                fontFamily: 'JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, monospace',
                lineHeight: 18,
                minimap: { enabled: false },
                scrollBeyondLastLine: false,
                automaticLayout: true,
                folding: true,
                wordWrap: 'off',
                tabSize: 2,
                scrollbar: { verticalScrollbarSize: 10, horizontalScrollbarSize: 10 },
              }}
              loading={<EditorFallback content={file.content} />}
            />
          </Suspense>
        </div>
      </CardBody>
    </Card>
  );
}
