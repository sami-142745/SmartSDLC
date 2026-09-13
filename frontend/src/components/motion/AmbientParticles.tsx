import { useEffect, useRef } from 'react';

import { useMotionControl } from '../../hooks/useMotionControl';

interface Particle {
  x: number;
  y: number;
  r: number;
  sp: number;
  ph: number;
  sw: number;
  alpha: number;
}

interface AmbientParticlesProps {
  className?: string;
  count?: number;
  color?: string;
  maxAlpha?: number;
  speed?: number;
}

/**
 * Lightweight canvas particle drift used as 3D-ambience. Small particle
 * counts only, DPR-capped, paused when the tab is hidden, static single
 * frame when the platform prefers reduced motion or has no fine pointer.
 * No WebGL, no dependencies.
 */
export function AmbientParticles({
  className = '',
  count = 36,
  color = '#818cf8',
  maxAlpha = 0.5,
  speed = 0.14,
}: AmbientParticlesProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const { animate } = useMotionControl();

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    let ctx: CanvasRenderingContext2D | null = null;
    try {
      ctx = canvas.getContext('2d');
    } catch {
      ctx = null;
    }
    if (!ctx) return;

    let raf = 0;
    let width = 0;
    let height = 0;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    let parts: Particle[] = [];

    const spawn = (): Particle => ({
      x: Math.random() * width,
      y: Math.random() * height,
      r: 0.6 + Math.random() * 1.6,
      sp: speed * (0.5 + Math.random()),
      ph: Math.random() * Math.PI * 2,
      sw: 0.3 + Math.random() * 0.9,
      alpha: 0.4 + Math.random() * 0.6,
    });

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      width = Math.max(1, rect.width);
      height = Math.max(1, rect.height);
      canvas.width = Math.max(1, Math.round(width * dpr));
      canvas.height = Math.max(1, Math.round(height * dpr));
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      parts = Array.from({ length: count }, () => spawn());
    };

    const drawStatic = () => {
      ctx.clearRect(0, 0, width, height);
      for (const p of parts) {
        ctx.globalAlpha = maxAlpha * 0.6 * p.alpha;
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.globalAlpha = 1;
    };

    const draw = (t: number) => {
      ctx.clearRect(0, 0, width, height);
      for (const p of parts) {
        p.y -= p.sp;
        if (p.y < -8) {
          p.y = height + 8;
          p.x = Math.random() * width;
        }
        const twinkle = 0.55 + 0.45 * Math.sin(t * 0.0012 * p.sw + p.ph);
        ctx.globalAlpha = maxAlpha * twinkle * p.alpha;
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.globalAlpha = 1;
      raf = requestAnimationFrame(draw);
    };

    resize();
    if (animate) {
      raf = requestAnimationFrame(draw);
    } else {
      drawStatic();
    }

    const supportsResizeObserver =
      typeof ResizeObserver !== 'undefined' && typeof window.ResizeObserver !== 'undefined';
    let observer: ResizeObserver | null = null;
    if (supportsResizeObserver) {
      observer = new ResizeObserver(() => {
        resize();
        if (!animate) drawStatic();
      });
      observer.observe(canvas);
    }

    const onVisibility = () => {
      if (!raf) return;
      cancelAnimationFrame(raf);
      if (!document.hidden) raf = requestAnimationFrame(draw);
    };
    document.addEventListener('visibilitychange', onVisibility);

    return () => {
      if (raf) cancelAnimationFrame(raf);
      observer?.disconnect();
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [animate, color, count, maxAlpha, speed]);

  return <canvas ref={canvasRef} className={`pointer-events-none ${className}`} aria-hidden />;
}