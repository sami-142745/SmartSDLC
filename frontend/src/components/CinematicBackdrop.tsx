import { lazy, Suspense } from 'react';
import { useLocation } from 'react-router-dom';

import { useMotionPrefs } from '../hooks/useMotionPrefs';
import { isTestEnv } from '../lib/env';
import type { SceneVariant } from '../three/CyberScene';

const CyberScene = lazy(() =>
  import('../three/CyberScene').then((m) => ({ default: m.CyberScene })),
);

function variantFor(pathname: string): SceneVariant {
  if (pathname.startsWith('/reviews/')) return 'analysis';
  if (pathname.startsWith('/repositories/')) return 'network';
  if (pathname.startsWith('/pull-requests/')) return 'scan';
  if (pathname === '/repositories' || pathname === '/pull-requests') return 'network';
  if (pathname === '/dashboard' || pathname === '/login') return 'core';
  return 'aura';
}

/**
 * Global cinematic WebGL layer rendered behind the application UI. Purely
 * decorative: aria-hidden, pointer-events-none. Skipped entirely under
 * prefers-reduced-motion and in test environments.
 */
export function CinematicBackdrop({
  variant,
  className = '',
}: {
  variant?: SceneVariant;
  className?: string;
}) {
  const { reduced } = useMotionPrefs();
  const location = useLocation();
  const resolved = variant ?? variantFor(location.pathname);

  if (isTestEnv() || reduced) return null;

  return (
    <div
      aria-hidden
      className={`pointer-events-none fixed inset-0 z-0 overflow-hidden ${className}`}
    >
      <Suspense fallback={null}>
        <CyberScene variant={resolved} />
      </Suspense>
    </div>
  );
}