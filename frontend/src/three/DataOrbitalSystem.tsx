import { useMemo, useRef } from 'react';
import * as THREE from 'three';
import { useFrame } from '@react-three/fiber';

const SATELLITES = 12;

/**
 * DataOrbitalSystem — three tilted orbital rings with instanced satellite
 * nodes drifting around a shared center. Decorative support for the command
 * center; metric values live in DOM HUD meters layered above.
 */
export function DataOrbitalSystem({ active }: { active: boolean }) {
  const root = useRef<THREE.Group>(null);
  const inner = useRef<THREE.Group>(null);
  const outer = useRef<THREE.Group>(null);

  const satellites = useMemo(() => {
    const positions = new Float32Array(SATELLITES * 3);
    const colors = new Float32Array(SATELLITES * 3);
    for (let i = 0; i < SATELLITES; i++) {
      const a = (i / SATELLITES) * Math.PI * 2;
      positions[i * 3] = Math.cos(a) * 2.9;
      positions[i * 3 + 1] = Math.sin(a * 1.3) * 0.35;
      positions[i * 3 + 2] = Math.sin(a) * 2.9;
      const c = i % 2 === 0 ? [0.65, 0.72, 1] : [0.4, 0.9, 1];
      colors[i * 3] = c[0];
      colors[i * 3 + 1] = c[1];
      colors[i * 3 + 2] = c[2];
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    return geo;
  }, []);

  useFrame((_, dt) => {
    if (!active) return;
    if (root.current) root.current.rotation.y -= dt * 0.05;
    if (inner.current) inner.current.rotation.y += dt * 0.22;
    if (outer.current) outer.current.rotation.y -= dt * 0.13;
  });

  if (!active) return null;

  return (
    <group position={[0, -0.2, -3]} ref={root}>
      <group rotation={[0.9, 0, 0.4]}>
        <mesh>
          <torusGeometry args={[2.9, 0.004, 8, 150]} />
          <meshBasicMaterial color="#6366f1" transparent opacity={0.16} depthWrite={false} blending={THREE.AdditiveBlending} />
        </mesh>
        <group ref={outer}>
          <points geometry={satellites}>
            <pointsMaterial
              size={0.12}
              sizeAttenuation
              vertexColors
              transparent
              opacity={0.75}
              depthWrite={false}
              blending={THREE.AdditiveBlending}
            />
          </points>
        </group>
      </group>
      <group rotation={[1.2, 0.4, 0]}>
        <mesh>
          <torusGeometry args={[2.15, 0.003, 8, 130]} />
          <meshBasicMaterial color="#22d3ee" transparent opacity={0.12} depthWrite={false} blending={THREE.AdditiveBlending} />
        </mesh>
        <group ref={inner}>
          <points geometry={satellites}>
            <pointsMaterial
              size={0.09}
              sizeAttenuation
              vertexColors
              transparent
              opacity={0.6}
              depthWrite={false}
              blending={THREE.AdditiveBlending}
            />
          </points>
        </group>
      </group>
      <group rotation={[0.2, 0.85, 0.6]}>
        <mesh>
          <torusGeometry args={[3.5, 0.003, 8, 160]} />
          <meshBasicMaterial color="#8b5cf6" transparent opacity={0.1} depthWrite={false} blending={THREE.AdditiveBlending} />
        </mesh>
      </group>
    </group>
  );
}