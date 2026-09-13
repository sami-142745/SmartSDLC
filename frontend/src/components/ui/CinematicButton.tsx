import { useEffect, useRef, type ReactNode } from 'react';
import gsap from 'gsap';

import { useMotionPrefs } from '../../hooks/useMotionPrefs';
import { isTestEnv } from '../../lib/env';

interface CinematicButtonProps {
  href?: string;
  onClick?: () => void;
  type?: 'button' | 'submit';
  disabled?: boolean;
  className?: string;
  children: ReactNode;
  /** enable the magnetic hover pull (only on key CTAs) */
  magnetic?: boolean;
  strength?: number;
}

/**
 * CTA button with a magnetic hover pull and a click ripple. Renders a real
 * anchor (when `href`) or button, so navigation, form submit and keyboard
 * behavior stay fully intact. Motion effects self-disable for touch devices,
 * reduced-motion users and tests.
 */
export function CinematicButton({
  href,
  onClick,
  type = 'button',
  disabled,
  className = '',
  children,
  magnetic = true,
  strength = 0.28,
}: CinematicButtonProps) {
  const wrapRef = useRef<HTMLSpanElement>(null);
  const { reduced, coarse } = useMotionPrefs();

  useEffect(() => {
    if (!magnetic) return;
    const wrap = wrapRef.current;
    if (!wrap || isTestEnv() || reduced || coarse) return;

    const xTo = gsap.quickTo(wrap, 'x', { duration: 0.4, ease: 'power3.out' });
    const yTo = gsap.quickTo(wrap, 'y', { duration: 0.4, ease: 'power3.out' });

    const onMove = (e: PointerEvent) => {
      const r = wrap.getBoundingClientRect();
      xTo((e.clientX - (r.left + r.width / 2)) * strength);
      yTo((e.clientY - (r.top + r.height / 2)) * strength);
    };
    const onLeave = () => {
      xTo(0);
      yTo(0);
    };

    wrap.addEventListener('pointermove', onMove);
    wrap.addEventListener('pointerleave', onLeave);
    return () => {
      wrap.removeEventListener('pointermove', onMove);
      wrap.removeEventListener('pointerleave', onLeave);
    };
  }, [magnetic, reduced, coarse, strength]);

  const addRipple = (e: React.PointerEvent<HTMLElement>) => {
    if (reduced || isTestEnv()) return;
    const host = e.currentTarget as HTMLElement;
    const rect = host.getBoundingClientRect();
    const d = Math.max(rect.width, rect.height) * 2.1;
    const s = document.createElement('span');
    s.className = 'ripple-node';
    s.style.width = `${d}px`;
    s.style.height = `${d}px`;
    s.style.left = `${e.clientX - rect.left - d / 2}px`;
    s.style.top = `${e.clientY - rect.top - d / 2}px`;
    host.appendChild(s);
    s.addEventListener('animationend', () => s.remove());
  };

  const innerStyle = { position: 'relative', overflow: 'hidden' } as const;

  const content =
    href != null ? (
      <a href={href} onPointerDown={addRipple} style={innerStyle} className={className}>
        {children}
      </a>
    ) : (
      <button
        type={type}
        onClick={onClick}
        disabled={disabled}
        onPointerDown={addRipple}
        style={innerStyle}
        className={className}
      >
        {children}
      </button>
    );

  return (
    <span ref={wrapRef} className="cinematic-cta inline-block">
      {content}
    </span>
  );
}