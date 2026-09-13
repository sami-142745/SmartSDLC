import { useMemo, useRef } from 'react';
import * as THREE from 'three';
import { useFrame, useThree } from '@react-three/fiber';

import { useMouse } from '../hooks/useMouse';

export type CameraProfile = 'orbit' | 'push' | 'drift';

/**
 * Cinematic camera — part of the composition.
 * - 'orbit': slow revolution around the hero object (login / dashboard)
 * - 'push': gentle dolly forward toward the scene (analysis)
 * - 'drift': pointer parallax (default)
 *
 * Kept intentionally slow — like a product film, not a UI widget.
 */
export function CameraRig({ profile = 'drift' }: { profile?: CameraProfile }) {
  const { camera } = useThree();
  const mouse = useMouse();
  const target = useMemo(() => new THREE.Vector3(0, 0.12, 10), []);

  useFrame((state, dt) => {
    const t = state.clock.elapsedTime;

    let tx = 0;
    let ty = 0.18;
    let tz = 10;

    if (profile === 'orbit') {
      tx = Math.sin(t * 0.09) * 1.15;
      ty = 0.18 + Math.sin(t * 0.07) * 0.42;
      tz = 9.7 - Math.cos(t * 0.09) * 0.52;
    } else if (profile === 'push') {
      const depth = 1 - Math.min(0.35, t * 0.02);
      tz = 10 - (1 - depth) * 3.4;
      ty = 0.22;
    }

    tx += mouse.current.x * 0.55;
    ty += mouse.current.y * 0.26;

    const k = Math.min(1, dt * 2.2);
    target.x += (tx - target.x) * k;
    target.y += (ty - target.y) * k;
    target.z += (tz - target.z) * k;

    camera.position.set(target.x, target.y, target.z);
    camera.lookAt(0, 0.12, 0);
  });

  return null;
}
