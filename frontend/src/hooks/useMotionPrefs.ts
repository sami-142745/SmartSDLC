import { useEffect, useState } from 'react';

import { isTestEnv } from '../lib/env';

export type DeviceTier = 'mobile' | 'tablet' | 'desktop';

export interface MotionPrefs {
  /** prefers-reduced-motion: reduce */
  reduced: boolean;
  /** coarse pointer (touch) */
  coarse: boolean;
  /** approximate device class */
  tier: DeviceTier;
}

function match(query: string): boolean {
  if (isTestEnv() || typeof window.matchMedia !== 'function') return false;
  return window.matchMedia(query).matches;
}

function readPrefs(): MotionPrefs {
  return {
    reduced: match('(prefers-reduced-motion: reduce)'),
    coarse: match('(pointer: coarse)'),
    tier: match('(min-width: 1024px)')
      ? 'desktop'
      : match('(min-width: 768px)')
        ? 'tablet'
        : 'mobile',
  };
}

export function useMotionPrefs(): MotionPrefs {
  const [prefs, setPrefs] = useState<MotionPrefs>(readPrefs);

  useEffect(() => {
    if (isTestEnv() || typeof window.matchMedia !== 'function') return;

    const queries = [
      '(prefers-reduced-motion: reduce)',
      '(pointer: coarse)',
      '(min-width: 1024px)',
      '(min-width: 768px)',
    ];
    const mqls = queries.map((q) => window.matchMedia(q));
    const update = () => setPrefs(readPrefs());

    mqls.forEach((mql) => {
      if (typeof mql.addEventListener === 'function') mql.addEventListener('change', update);
    });
    return () => {
      mqls.forEach((mql) => {
        if (typeof mql.removeEventListener === 'function') mql.removeEventListener('change', update);
      });
    };
  }, []);

  return prefs;
}