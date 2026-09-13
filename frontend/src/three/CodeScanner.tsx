import { useMemo, useRef } from 'react';
import * as THREE from 'three';
import { useFrame } from '@react-three/fiber';

/**
 * CodeScanner — a vertical scan plane sweeping over floating code-fragment
 * bars, used in the pull-request analysis chamber. Purely decorative;
 * changed-file contents are rendered as real DOM panels.
 */
export function CodeScanner({ active }: { active: boolean }) {
  const root = useRef<THREE.Group>(null);
  const beam = useRef<THREE.Mesh>(null);
  const beamY = useRef(-3.6);

  const fragments = useMemo(() => {
    const geo = new THREE.BoxGeometry(0.06, 0.9, 0.06);
    const mat = new THREE.MeshBasicMaterial({
      color: '#67e8f9',
      transparent: true,
      opacity: 0.22,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const items = Array.from({ length: 7 }, (_, i) => ({
      mesh: new THREE.Mesh(geo, mat),
      seed: i * 0.37,
    }));
    for (let i = 0; i < items.length; i++) {
      const a = (i / items.length) * Math.PI * 2;
      items[i].mesh.position.set(Math.cos(a) * 1.8, (i - items.length / 2) * 0.85, Math.sin(a) * 1.8);
      items[i].mesh.rotation.y = a;
    }
    return items;
  }, []);

  useFrame((state, dt) => {
    if (!active) return;
    if (beam.current) {
      const t = Math.sin(state.clock.elapsedTime * 1.4);
      beam.current.position.y = t * 3.0;
      const material = beam.current.material as THREE.MeshBasicMaterial;
      material.opacity = 0.55 + t * 0.15;
      beamY.current = beam.current.position.y;
    }
    if (root.current) root.current.rotation.y += dt * 0.1;
    for (let i = 0; i < fragments.length; i++) {
      const f = fragments[i];
      const off = beamY.current - f.mesh.position.y;
      const glow = Math.max(0, 1 - Math.abs(off) / 1.4);
      f.mesh.scale.set(1, 1 + glow * 1.6, 1);
      (f.mesh.material as THREE.MeshBasicMaterial).opacity = 0.1 + glow * 0.5;
    }
  });

  if (!active) return null;

  return (
    <group position={[0, 0, -2.4]} ref={root}>
      {fragments.map((f, i) => (
        <primitive key={i} object={f.mesh} />
      ))}
      <mesh ref={beam}>
        <boxGeometry args={[7.5, 0.45, 7.5]} />
        <meshBasicMaterial
          color="#22d3ee"
          transparent
          opacity={0.4}
          depthWrite={false}
          blending={THREE.AdditiveBlending}
        />
      </mesh>
    </group>
  );
}