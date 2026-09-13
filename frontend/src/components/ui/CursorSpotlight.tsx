import { useEffect, useRef } from 'react';
import gsap from 'gsap';

import { useMotionPrefs } from '../../hooks/useMotionPrefs';
import { isTestEnv } from '../../lib/env';

/**
 * A soft radial glow that trails the cursor at very low intensity. Purely
 * decorative; disabled on touch devices, reduced-motion and tests. Renders
 * nothing in those cases (no pointer-events side effects either).
 */
export function CursorSpotlight() {
  const ref = useRef<HTMLDivElement>(null);
  const { reduced, coarse } = useMotionPrefs();

  useEffect(() => {
    if (isTestEnv() || reduced || coarse || !ref.current) return;
    const el = ref.current;
    const xTo = gsap.quickTo(el, 'x', { duration: 0.55, ease: 'power3.out' });
    const yTo = gsap.quickTo(el, 'y', { duration: 0.55, ease: 'power3.out' });
    const onMove = (e: PointerEvent) => {
      xTo(e.clientX);
      yTo(e.clientY);
    };
    window.addEventListener('pointermove', onMove, { passive: true });
    return () => window.removeEventListener('pointermove', onMove);
  }, [reduced, coarse]);

  if (isTestEnv() || reduced || coarse) return null;

  return <div ref={ref} aria-hidden className="cursor-spotlight" />;
}