import { useEffect } from 'react';
import Lenis from 'lenis';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

import { useMotionPrefs } from '../hooks/useMotionPrefs';
import { isTestEnv } from '../lib/env';

gsap.registerPlugin(ScrollTrigger);

/**
 * Smooth, buttery page scrolling (lerped wheel) synced with GSAP's
 * ScrollTrigger driver. Skipped for reduced-motion, touch devices and tests.
 */
export function SmoothScroll() {
  const { reduced, coarse } = useMotionPrefs();

  useEffect(() => {
    if (isTestEnv() || reduced || coarse || typeof window === 'undefined') return;

    const lenis = new Lenis({ lerp: 0.1, smoothWheel: true });
    lenis.on('scroll', ScrollTrigger.update);

    const raf = (time: number) => {
      lenis.raf(time * 1000);
    };
    gsap.ticker.add(raf);
    gsap.ticker.lagSmoothing(0);

    return () => {
      gsap.ticker.remove(raf);
      lenis.destroy();
    };
  }, [reduced, coarse]);

  return null;
}