import { useMemo, useRef } from 'react';
import * as THREE from 'three';
import { useFrame } from '@react-three/fiber';

import { useFadeTo } from './fade';

const INNER_COUNT = 220;

/**
 * Holographic "AI core" — layered shells, wireframe cage, scanning rings
 * and orbiting data dots. Fully decorative; fades in/out per scene variant.
 */
export function AIOrb({ active }: { active: boolean }) {
  const group = useRef<THREE.Group>(null);
  const { ref: fade, apply } = useFadeTo(active, 3.2);
  const inner = useRef<THREE.Points>(null);
  const orbitGroup = useRef<THREE.Group>(null);
  const ringA = useRef<THREE.Mesh>(null);
  const ringB = useRef<THREE.Mesh>(null);

  const innerPoints = useMemo(() => {
    const positions = new Float32Array(INNER_COUNT * 3);
    for (let i = 0; i < INNER_COUNT; i++) {
      const r = Math.cbrt(Math.random()) * 1.2;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(Math.random() * 2 - 1);
      positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      positions[i * 3 + 2] = r * Math.cos(phi);
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    return geo;
  }, []);

  const orbitDots = useMemo(() => {
    const items: { x: number; y: number; z: number; p: number; s: number }[] = [];
    const count = 7;
    for (let i = 0; i < count; i++) {
      const angle = (i / count) * Math.PI * 2;
      items.push({
        x: Math.cos(angle) * 2.0,
        y: Math.sin(angle) * 0.35,
        z: Math.sin(angle) * 2.0,
        p: angle,
        s: 0.045 + (i % 3) * 0.012,
      });
    }
    return items;
  }, []);

  useFrame((state, dt) => {
    apply(group.current);
    const t = state.clock.elapsedTime;
    if (group.current) {
      group.current.rotation.y += dt * 0.12;
      group.current.rotation.x = Math.sin(t * 0.22) * 0.14;
      const scale = 1 + Math.sin(t * 1.05) * 0.028;
      group.current.scale.setScalar(scale);
    }
    if (inner.current) inner.current.rotation.x += dt * 0.18;
    if (orbitGroup.current) orbitGroup.current.rotation.y += dt * 0.4;
    if (ringA.current) ringA.current.rotation.z += dt * 0.25;
    if (ringB.current) ringB.current.rotation.x += dt * 0.18;
    void t;
  });

  return (
    <group position={[0, 0.35, -1.2]}>
      <group ref={group}>
        {/* outer shell */}
        <mesh>
          <icosahedronGeometry args={[1.62, 3]} />
          <meshStandardMaterial
            color="#3b82f6"
            transparent
            opacity={0.16}
            roughness={0.4}
            metalness={0.2}
            emissive="#1d4ed8"
            emissiveIntensity={0.55}
            depthWrite={false}
            userData={{ base: 0.16 }}
          />
        </mesh>
        {/* wireframe cage */}
        <mesh>
          <icosahedronGeometry args={[1.74, 1]} />
          <meshBasicMaterial
            color="#60a5fa"
            wireframe
            transparent
            opacity={0.16}
            depthWrite={false}
            userData={{ base: 0.16 }}
          />
        </mesh>
        {/* inner particle cloud */}
        <points ref={inner} geometry={innerPoints}>
          <pointsMaterial
            color="#a5b4fc"
            size={0.05}
            sizeAttenuation
            transparent
            opacity={0.5}
            depthWrite={false}
            blending={THREE.AdditiveBlending}
            userData={{ base: 0.5 }}
          />
        </points>
        {/* luminous nucleus */}
        <mesh>
          <sphereGeometry args={[0.3, 32, 32]} />
          <meshStandardMaterial
            color="#0b0e1d"
            emissive="#a78bfa"
            emissiveIntensity={2.4}
            transparent
            opacity={0.95}
            userData={{ base: 0.95 }}
          />
        </mesh>
        {/* scanning rings */}
        <mesh ref={ringA}>
          <torusGeometry args={[1.92, 0.0045, 8, 120]} />
          <meshBasicMaterial
            color="#818cf8"
            transparent
            opacity={0.4}
            depthWrite={false}
            blending={THREE.AdditiveBlending}
            userData={{ base: 0.4 }}
          />
        </mesh>
        <mesh ref={ringB}>
          <torusGeometry args={[2.18, 0.0035, 8, 120]} />
          <meshBasicMaterial
            color="#22d3ee"
            transparent
            opacity={0.28}
            depthWrite={false}
            blending={THREE.AdditiveBlending}
            userData={{ base: 0.28 }}
          />
        </mesh>
      </group>
      {/* orbiting data dots (always subtle, survives fades) */}
      <group ref={orbitGroup}>
        {orbitDots.map((dot, i) => (
          <mesh key={i} position={[dot.x, dot.y, dot.z]}>
            <sphereGeometry args={[dot.s, 12, 12]} />
            <meshBasicMaterial
              color="#a5b4fc"
              transparent
              opacity={0.7}
              depthWrite={false}
              blending={THREE.AdditiveBlending}
            />
          </mesh>
        ))}
      </group>
    </group>
  );
}