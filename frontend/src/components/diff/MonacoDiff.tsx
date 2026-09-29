import { useCallback, useMemo, useRef } from 'react';
import { DiffEditor } from '@monaco-editor/react';
import type { editor } from 'monaco-editor';

import { MONACO_THEME, defineMonacoTheme } from './monacoTheme';


/**
 * First line index where the two documents diverge, or 1 when they match.
 * Computed in plain JS rather than through a Monaco API so it works on both
 * the original and modified models without depending on editor internals.
 */
function firstChangedLine(original: string, modified: string) {
  const before = original.split('\n');
  const after = modified.split('\n');
  const limit = Math.min(before.length, after.length);
  for (let i = 0; i < limit; i += 1) {
    if (before[i] !== after[i]) return i + 1;
  }
  return Math.min(before.length, after.length) + 1;
}

interface MonacoDiffProps {
  original: string;
  modified: string;
  language: string;
  /** Display path, used for the editor's model label and aria description. */
  path: string;
  height?: number;
}

/**
 * Split-view diff on top of Monaco. Loaded lazily so the ~2MB editor payload
 * only downloads when a reviewer actually switches to side-by-side mode.
 *
 * The documents arrive pre-reconstructed from the unified diff (see
 * `lib/diff/unifiedDiff`), so the editor never has to parse a patch itself.
 */
export function MonacoDiff({ original, modified, language, path, height = 560 }: MonacoDiffProps) {
  const editorRef = useRef<editor.IStandaloneDiffEditor | null>(null);

  const options = useMemo<editor.IDiffEditorConstructionOptions>(
    () => ({
      automaticLayout: true,
      renderSideBySide: true,
      readOnly: true,
      originalEditable: false,
      fontSize: 12,
      fontFamily: 'JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, monospace',
      lineHeight: 18,
      minimap: { enabled: false },
      scrollBeyondLastLine: false,
      renderOverviewRuler: false,
      renderIndicators: true,
      folding: true,
      wordWrap: 'off',
      tabSize: 2,
      contextmenu: false,
      scrollbar: { verticalScrollbarSize: 10, horizontalScrollbarSize: 10 },
      overviewRulerBorder: false,
      hideUnchangedRegions: { enabled: true, minimumLineCount: 8 },
    }),
    [],
  );

  // Start the reader at the first real change rather than the top of the file.
  const reveal = useCallback(
    (instance: editor.IStandaloneDiffEditor) => {
      editorRef.current = instance;
      instance.revealLineInCenter(firstChangedLine(original, modified));
    },
    [original, modified],
  );

  return (
    <div
      className="overflow-hidden rounded-xl border border-white/[0.07] bg-surface-0"
      style={{ height }}
      role="group"
      aria-label={`Side-by-side diff for ${path}`}
    >
      <DiffEditor
        original={original}
        modified={modified}
        language={language}
        theme={MONACO_THEME}
        beforeMount={defineMonacoTheme}
        onMount={reveal}
        options={options}
        loading={
          <div
            className="flex h-full items-center justify-center text-[12px] text-ink-faint"
            style={{ height }}
          >
            Loading editor…
          </div>
        }
      />
    </div>
  );
}

export default MonacoDiff;
