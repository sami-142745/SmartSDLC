import { useRef } from 'react';
import * as THREE from 'three';
import { useFrame } from '@react-three/fiber';

export interface FadeHandle {
  /** current fade factor 0..1 */
  readonly ref: React.MutableRefObject<number>;
  /** apply the fade to every transparent material under a root object */
  apply: (root: THREE.Object3D | null) => void;
}

/**
 * Drives a 0..1 fade factor toward a target and applies it to the opacity of
 * every transparent material under a root object. Materials opt in via
 * `userData.base` (their resting opacity at full strength).
 */
export function useFadeTo(active: boolean, speed = 3): FadeHandle {
  const ref = useRef(0);
  const current = ref;

  useFrame((_, dt) => {
    const target = active ? 1 : 0;
    const next = THREE.MathUtils.damp(current.current, target, speed, dt);
    if (Math.abs(next - current.current) > 0.0001 || target === 0) {
      current.current = next;
    } else {
      current.current = next;
    }
  });

  const apply = (root: THREE.Object3D | null) => {
    const fade = current.current;
    if (!root) return;
    root.visible = fade > 0.03;
    if (fade < 0.001) return;
    root.traverse((obj) => {
      const mesh = obj as THREE.Mesh;
      const material = mesh.material as THREE.Material | THREE.Material[] | undefined;
      if (!material) return;
      const list = Array.isArray(material) ? material : [material];
      for (const m of list) {
        if (m.transparent && m.userData) {
          const base = (m.userData.base as number) ?? 1;
          if (base > 0) m.opacity = base * fade;
        }
      }
    });
  };

  return { ref: current, apply };
}