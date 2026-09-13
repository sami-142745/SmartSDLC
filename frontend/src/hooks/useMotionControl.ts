import { useEffect, useState } from 'react';

interface MotionControl {
  reduced: boolean;
  fine: boolean;
  animate: boolean;
}

function read(): MotionControl {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return { reduced: false, fine: true, animate: true };
  }
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const fine = window.matchMedia('(pointer: fine)').matches;
  return { reduced, fine, animate: !reduced && fine };
}

/**
 * Live motion preferences: honors prefers-reduced-motion and coarse
 * (touch) pointers so continuous 3D animation can be switched off.
 */
export function useMotionControl(): MotionControl {
  const [state, setState] = useState<MotionControl>(read);

  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return;

    const reducedQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    const fineQuery = window.matchMedia('(pointer: fine)');
    const onChange = () => setState(read());
    reducedQuery.addEventListener?.('change', onChange);
    fineQuery.addEventListener?.('change', onChange);
    return () => {
      reducedQuery.removeEventListener?.('change', onChange);
      fineQuery.removeEventListener?.('change', onChange);
    };
  }, []);

  return state;
}