import { useMemo, useRef } from 'react';
import * as THREE from 'three';
import { useFrame } from '@react-three/fiber';

/**
 * RepositoryGalaxy — a decorative spiral node network. Accepts a node count
 * (derived from real repository data) and scatters them across a 3D spiral
 * with hub spokes. Repository details live in DOM panels; nodes carry no
 * per-repo meaning.
 */
export function RepositoryGalaxy({ active, count = 8 }: { active: boolean; count?: number }) {
  const root = useRef<THREE.Group>(null);
  const nodes = useRef<THREE.Points>(null);

  const n = Math.max(3, count);
  const scaffold = useMemo(() => {
    const nodePos = new Float32Array(n * 3);
    const nodeCol = new Float32Array(n * 3);
    const hub = new Float32Array(n * 6);
    const arms = 2;
    for (let i = 0; i < n; i++) {
      const arm = i % arms;
      const idx = Math.floor(i / arms);
      const spin = arm * Math.PI + idx * 0.6;
      const r = 1.4 + (idx / Math.max(1, Math.ceil(n / arms))) * 2.6;
      const x = Math.cos(spin) * r;
      const z = Math.sin(spin) * r;
      const y = Math.sin(idx * 1.3) * 0.5;
      nodePos[i * 3] = x;
      nodePos[i * 3 + 1] = y;
      nodePos[i * 3 + 2] = z;
      const c = arm === 0 ? [0.62, 0.72, 1] : [0.4, 0.85, 1];
      nodeCol[i * 3] = c[0];
      nodeCol[i * 3 + 1] = c[1];
      nodeCol[i * 3 + 2] = c[2];
      hub[i * 6] = 0;
      hub[i * 6 + 1] = 0;
      hub[i * 6 + 2] = 0;
      hub[i * 6 + 3] = x;
      hub[i * 6 + 4] = y;
      hub[i * 6 + 5] = z;
    }
    const nodeGeo = new THREE.BufferGeometry();
    nodeGeo.setAttribute('position', new THREE.BufferAttribute(nodePos, 3));
    nodeGeo.setAttribute('color', new THREE.BufferAttribute(nodeCol, 3));
    const hubGeo = new THREE.BufferGeometry();
    hubGeo.setAttribute('position', new THREE.BufferAttribute(hub, 3));
    return { nodeGeo, hubGeo };
  }, [n]);

  useFrame((state, dt) => {
    if (!active) return;
    if (root.current) {
      root.current.rotation.y += dt * 0.08;
      root.current.rotation.x = Math.sin(state.clock.elapsedTime * 0.12) * 0.08;
    }
    if (nodes.current) nodes.current.rotation.y -= dt * 0.02;
  });

  if (!active) return null;

  return (
    <group position={[0.4, 0, -2.5]} ref={root}>
      <mesh>
        <sphereGeometry args={[0.4, 24, 24]} />
        <meshBasicMaterial
          color="#a5b4fc"
          transparent
          opacity={0.9}
          depthWrite={false}
          blending={THREE.AdditiveBlending}
        />
      </mesh>
      <mesh>
        <sphereGeometry args={[0.85, 24, 24]} />
        <meshBasicMaterial
          color="#6366f1"
          transparent
          opacity={0.14}
          depthWrite={false}
          blending={THREE.AdditiveBlending}
        />
      </mesh>
      <lineSegments geometry={scaffold.hubGeo}>
        <lineBasicMaterial color="#6366f1" transparent opacity={0.24} depthWrite={false} blending={THREE.AdditiveBlending} />
      </lineSegments>
      <points ref={nodes} geometry={scaffold.nodeGeo}>
        <pointsMaterial
          size={0.22}
          sizeAttenuation
          vertexColors
          transparent
          opacity={0.85}
          depthWrite={false}
          blending={THREE.AdditiveBlending}
        />
      </points>
    </group>
  );
}