import { useEffect, useRef } from 'react';

/**
 * Tracks the pointer in normalized device coordinates (-1..1, y up).
 * Uses a window listener so it works independently of any WebGL canvas
 * pointer capture. Shared by the 3D camera rig and cursor spotlight.
 */
export function useMouse() {
  const ref = useRef({ x: 0, y: 0 });

  useEffect(() => {
    const onMove = (e: PointerEvent) => {
      ref.current.x = (e.clientX / window.innerWidth) * 2 - 1;
      ref.current.y = -((e.clientY / window.innerHeight) * 2 - 1);
    };
    window.addEventListener('pointermove', onMove, { passive: true });
    return () => window.removeEventListener('pointermove', onMove);
  }, []);

  return ref;
}