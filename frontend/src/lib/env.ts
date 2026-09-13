export function isTestEnv(): boolean {
  return typeof import.meta !== 'undefined' && import.meta.env?.MODE === 'test';
}

export function hasDOM(): boolean {
  return typeof window !== 'undefined' && typeof document !== 'undefined';
}