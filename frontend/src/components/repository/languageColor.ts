/**
 * Deterministic language colour ramp.
 *
 * Languages are not ranked by popularity (that would make a colour change every
 * time a repository adds a dependency), so the palette is hashed from the
 * language name. The same language therefore always gets the same colour across
 * pages, sessions and repositories.
 */
const RAMP = [
  '#8B5CF6',
  '#22D3EE',
  '#34D399',
  '#FBBF24',
  '#FB7185',
  '#60A5FA',
  '#F472B6',
  '#A3E635',
  '#FB923C',
  '#2DD4BF',
  '#C084FC',
  '#94A3B8',
] as const;

export function languageColor(name: string): string {
  // djb2-style string hash: stable across engines, cheap, and good enough to
  // spread the common languages across distinct hues.
  let hash = 5381;
  for (let index = 0; index < name.length; index += 1) {
    hash = (hash * 33) ^ name.charCodeAt(index);
  }
  return RAMP[Math.abs(hash) % RAMP.length];
}

export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const exponent = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / 1024 ** exponent;
  return `${value.toFixed(exponent === 0 ? 0 : value < 10 ? 1 : 0)} ${units[exponent]}`;
}
