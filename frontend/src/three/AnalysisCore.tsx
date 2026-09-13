import { useMemo, useRef } from 'react';
import * as THREE from 'three';
import { useFrame } from '@react-three/fiber';

const CHANNELS = 6;

/**
 * AnalysisCore — the AI code-analysis intelligence. A pulsing nucleus
 * surrounded by a channel ring (Gemini, Heuristics, Security, Complexity,
 * History, Feedback) with spoke links and orbiting node particles. All
 * channel facts are rendered as DOM labels layered above the canvas.
 */
export function AnalysisCore({ active }: { active: boolean }) {
  const root = useRef<THREE.Group>(null);
  const ring = useRef<THREE.Group>(null);

  const channels = useMemo(
    () =>
      Array.from({ length: CHANNELS }, (_, i) => {
        const a = (i / CHANNELS) * Math.PI * 2;
        return {
          x: Math.cos(a) * 3.1,
          z: Math.sin(a) * 3.1,
          r: 0.07 + (i % 3) * 0.018,
          tone: i % 2 === 0 ? '#a78bfa' : '#67e8f9',
        };
      }),
    [],
  );

  const spokes = useMemo(() => {
    const positions: number[] = [];
    for (const c of channels) positions.push(0, 0, 0, c.x, 0, c.z);
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(positions), 3));
    return geo;
  }, [channels]);

  useFrame((state, dt) => {
    if (!active) return;
    if (root.current) {
      root.current.rotation.y += dt * 0.14;
      root.current.scale.setScalar(1 + Math.sin(state.clock.elapsedTime * 0.8) * 0.04);
    }
    if (ring.current) ring.current.rotation.z += dt * 0.1;
  });

  if (!active) return null;

  return (
    <group position={[0, 0, -2.2]} ref={root}>
      <mesh>
        <icosahedronGeometry args={[0.82, 3]} />
        <meshPhysicalMaterial
          color="#0b0e1d"
          emissive="#8b5cf6"
          emissiveIntensity={1.9}
          roughness={0.2}
          metalness={0.3}
          transparent
          opacity={0.96}
        />
      </mesh>
      <mesh>
        <icosahedronGeometry args={[1.1, 1]} />
        <meshBasicMaterial color="#a5b4fc" wireframe transparent opacity={0.16} depthWrite={false} />
      </mesh>
      <group ref={ring} rotation={[Math.PI / 2.4, 0, 0]}>
        <mesh>
          <torusGeometry args={[3.1, 0.005, 8, 150]} />
          <meshBasicMaterial color="#818cf8" transparent opacity={0.32} depthWrite={false} blending={THREE.AdditiveBlending} />
        </mesh>
      </group>
      <lineSegments geometry={spokes}>
        <lineBasicMaterial color="#6366f1" transparent opacity={0.3} depthWrite={false} blending={THREE.AdditiveBlending} />
      </lineSegments>
      {channels.map((c, i) => (
        <mesh key={i} position={[c.x, 0, c.z]}>
          <sphereGeometry args={[c.r, 14, 14]} />
          <meshBasicMaterial color={c.tone} transparent opacity={0.9} depthWrite={false} blending={THREE.AdditiveBlending} />
        </mesh>
      ))}
    </group>
  );
}