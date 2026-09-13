import { useEffect, useRef } from 'react';
import type { CSSProperties, ReactNode } from 'react';

import { useMotionControl } from '../../hooks/useMotionControl';

interface ParallaxProps {
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
  depth?: number;
}

/**
 * Subtle pointer-following parallax. `depth` scales how far the layer
 * translates (background ~0.4, midground ~1, foreground ~1.6). Only
 * pointer-type "mouse" events are tracked so touch devices never move.
 * GPU-friendly: transforms are applied inside requestAnimationFrame and
 * never touch layout-affecting properties. Disabled under
 * prefers-reduced-motion.
 */
export function Parallax({ children, className = '', style, depth = 1 }: ParallaxProps) {
  const ref = useRef<HTMLDivElement>(null);
  const { reduced } = useMotionControl();
  const enabled = !reduced;

  useEffect(() => {
    const el = ref.current;
    if (!el || !enabled) return;

    let raf = 0;
    let mx = 0;
    let my = 0;

    const apply = () => {
      raf = 0;
      const px = -mx * depth * 5;
      const py = -my * depth * 5;
      el.style.transform = `translate3d(${px.toFixed(2)}px, ${py.toFixed(2)}px, 0)`;
    };

    const onMove = (event: PointerEvent) => {
      if (event.pointerType !== 'mouse') return;
      mx = (event.clientX / window.innerWidth - 0.5) * 2;
      my = (event.clientY / window.innerHeight - 0.5) * 2;
      if (!raf) raf = requestAnimationFrame(apply);
    };

    const reset = () => {
      if (raf) cancelAnimationFrame(raf);
      raf = 0;
      el.style.transform = 'none';
    };

    window.addEventListener('pointermove', onMove, { passive: true });
    document.addEventListener('mouseleave', reset, { passive: true });
    return () => {
      window.removeEventListener('pointermove', onMove);
      document.removeEventListener('mouseleave', reset);
      reset();
    };
  }, [enabled, depth]);

  return (
    <div ref={ref} className={className} style={style} aria-hidden>
      {children}
    </div>
  );
}