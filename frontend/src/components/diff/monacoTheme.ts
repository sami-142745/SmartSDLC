import type { editor } from 'monaco-editor';

/**
 * The single dark theme used by every Monaco surface in the app. Extracted so
 * the diff editor and the repository source viewer render identically instead
 * of drifting into two near-duplicates.
 */
export const MONACO_THEME = 'smartsdlc-dark';

export const MONACO_THEME_DEFINITION: editor.IStandaloneThemeData = {
  base: 'vs-dark',
  inherit: true,
  rules: [
    { token: 'comment', foreground: '52525B', fontStyle: 'italic' },
    { token: 'keyword', foreground: 'A78BFA' },
    { token: 'string', foreground: '86EFAC' },
    { token: 'number', foreground: 'FBBF24' },
    { token: 'type', foreground: '67E8F9' },
    { token: 'function', foreground: 'C4B5FD' },
    { token: 'variable', foreground: 'E4E4E7' },
  ],
  colors: {
    'editor.background': '#09090B',
    'editor.foreground': '#E4E4E7',
    'editorLineNumber.foreground': '#3F3F46',
    'editorLineNumber.activeForeground': '#A1A1AA',
    'editorGutter.background': '#0B0B0F',
    'editor.selectionBackground': 'rgba(139, 92, 246, 0.28)',
    'editor.lineHighlightBackground': 'rgba(255, 255, 255, 0.035)',
    'editorIndentGuide.background1': 'rgba(255, 255, 255, 0.06)',
    'editorWidget.background': '#131318',
    'editorWidget.border': 'rgba(255, 255, 255, 0.08)',
    'diffEditor.insertedTextBackground': 'rgba(52, 211, 153, 0.14)',
    'diffEditor.removedTextBackground': 'rgba(251, 113, 133, 0.14)',
    'diffEditor.insertedLineBackground': 'rgba(52, 211, 153, 0.07)',
    'diffEditor.removedLineBackground': 'rgba(251, 113, 133, 0.07)',
    'diffEditor.diagonalFill': 'rgba(255, 255, 255, 0.04)',
    'scrollbarSlider.background': 'rgba(255, 255, 255, 0.10)',
    'scrollbarSlider.hoverBackground': 'rgba(255, 255, 255, 0.18)',
    'scrollbarSlider.activeBackground': 'rgba(255, 255, 255, 0.26)',
  },
};

/**
 * Idempotently register the shared theme. Monaco throws if a theme is defined
 * twice, and both editors may mount in the same session, so registration is
 * tracked here rather than re-derived from the Monaco API (which exposes no
 * `getTheme`).
 */
let registered = false;

export function defineMonacoTheme(monaco: typeof import('monaco-editor')): void {
  if (registered) return;
  monaco.editor.defineTheme(MONACO_THEME, MONACO_THEME_DEFINITION);
  registered = true;
}
