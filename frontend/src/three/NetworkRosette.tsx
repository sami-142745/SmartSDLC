import { useMemo, useRef } from 'react';
import * as THREE from 'three';
import { useFrame } from '@react-three/fiber';

import { useFadeTo } from './fade';

const OUTER_NODES = 8;
const OUTER_RADIUS = 2.6;
const INNER_NODES = 6;
const INNER_RADIUS = 1.7;

function ringPoints(count: number, radius: number, yMax: number) {
  const points: THREE.Vector3[] = [];
  for (let i = 0; i < count; i++) {
    const a = (i / count) * Math.PI * 2;
    points.push(
      new THREE.Vector3(
        Math.cos(a) * radius,
        Math.sin(i * 1.7) * yMax,
        Math.sin(a) * radius,
      ),
    );
  }
  return points;
}

/**
 * Decorative "analysis pipeline" rosette — a core hub with layered orbits,
 * spoke links and travelling energy pulses. Used behind the AI review pages.
 */
export function NetworkRosette({ active }: { active: boolean }) {
  const group = useRef<THREE.Group>(null);
  const pulses = useRef<THREE.Group>(null);
  const spinners = useRef<THREE.Group>(null);
  const { ref: fade, apply } = useFadeTo(active, 3);

  const outer = useMemo(() => ringPoints(OUTER_NODES, OUTER_RADIUS, 0.5), []);
  const inner = useMemo(() => ringPoints(INNER_NODES, INNER_RADIUS, 0.4), []);

  const spokeGeometry = useMemo(() => {
    const positions: number[] = [];
    const linkPositions: number[] = [];
    for (const node of outer) {
      positions.push(0, 0.15, 0, node.x, node.y, node.z);
      linkPositions.push(0, 0.1, 0, node.x * 0.55, node.y * 0.55, node.z * 0.55);
    }
    for (const node of inner) {
      linkPositions.push(0, 0.1, 0, node.x * 0.3, node.y * 0.3, node.z * 0.3);
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute(
      'position',
      new THREE.BufferAttribute(new Float32Array(positions), 3),
    );
    const links = new THREE.BufferGeometry();
    links.setAttribute(
      'position',
      new THREE.BufferAttribute(new Float32Array(linkPositions), 3),
    );
    return { geo, links };
  }, [outer, inner]);

  const pulseTracks = useMemo(
    () =>
      Array.from({ length: 4 }, (_, i) => {
        const target = outer[(i * 2) % outer.length];
        return {
          from: new THREE.Vector3(0, 0.15, 0),
          to: target.clone(),
          phase: i * 0.25,
        };
      }),
    [outer],
  );

  const pulseRefs = useMemo(() => Array.from({ length: 4 }, () => null) as (THREE.Mesh | null)[], []);

  useFrame((state, dt) => {
    apply(group.current);
    const t = state.clock.elapsedTime;
    if (group.current) group.current.rotation.z += dt * 0.05;
    if (spinners.current) {
      spinners.current.rotation.y += dt * 0.22;
      spinners.current.rotation.x = Math.sin(t * 0.2) * 0.1;
    }
    if (pulses.current) {
      for (let i = 0; i < pulseTracks.length; i++) {
        const mesh = pulseRefs[i];
        if (!mesh) continue;
        const track = pulseTracks[i];
        const p = (t * 0.55 + track.phase) % 1;
        mesh.position.lerpVectors(track.from, track.to, p);
        mesh.visible = fade.current > 0.05;
      }
    }
  });

  return (
    <group ref={group} position={[0, 0.4, -2.2]} scale={0.92}>
      {/* hub */}
      <mesh>
        <icosahedronGeometry args={[0.22, 1]} />
        <meshStandardMaterial
          color="#0b0e1d"
          emissive="#8b5cf6"
          emissiveIntensity={2.6}
          transparent
          opacity={0.95}
          userData={{ base: 0.95 }}
        />
      </mesh>

      {/* spokes */}
      <lineSegments geometry={spokeGeometry.geo}>
        <lineBasicMaterial color="#6366f1" transparent opacity={0.4} blending={THREE.AdditiveBlending} depthWrite={false} userData={{ base: 0.4 }} />
      </lineSegments>
      <lineSegments geometry={spokeGeometry.links}>
        <lineBasicMaterial color="#22d3ee" transparent opacity={0.3} blending={THREE.AdditiveBlending} depthWrite={false} userData={{ base: 0.3 }} />
      </lineSegments>

      {/* orbit rings */}
      <mesh rotation={[Math.PI / 2.4, 0, 0]} scale={0.96}>
        <torusGeometry args={[OUTER_RADIUS, 0.0035, 6, 140]} />
        <meshBasicMaterial color="#818cf8" transparent opacity={0.25} depthWrite={false} blending={THREE.AdditiveBlending} userData={{ base: 0.25 }} />
      </mesh>
      <mesh rotation={[Math.PI / 2, 0.2, 0]}>
        <torusGeometry args={[INNER_RADIUS, 0.0035, 6, 120]} />
        <meshBasicMaterial color="#60a5fa" transparent opacity={0.3} depthWrite={false} blending={THREE.AdditiveBlending} userData={{ base: 0.3 }} />
      </mesh>

      <group ref={spinners}>
        {outer.map((node, i) => (
          <mesh key={`o-${i}`} position={node}>
            <sphereGeometry args={[0.05, 12, 12]} />
            <meshBasicMaterial color="#a5b4fc" transparent opacity={0.85} depthWrite={false} blending={THREE.AdditiveBlending} userData={{ base: 0.85 }} />
          </mesh>
        ))}
        {inner.map((node, i) => (
          <mesh key={`i-${i}`} position={node}>
            <sphereGeometry args={[0.038, 12, 12]} />
            <meshBasicMaterial color="#22d3ee" transparent opacity={0.7} depthWrite={false} blending={THREE.AdditiveBlending} userData={{ base: 0.7 }} />
          </mesh>
        ))}
      </group>

      {/* travelling energy pulses */}
      <group ref={pulses}>
        {pulseTracks.map((_, i) => (
          <mesh key={i} ref={(m) => { pulseRefs[i] = m; }}>
            <sphereGeometry args={[0.035, 8, 8]} />
            <meshBasicMaterial color="#f5b4ff" transparent opacity={0.95} depthWrite={false} blending={THREE.AdditiveBlending} />
          </mesh>
        ))}
      </group>
    </group>
  );
}