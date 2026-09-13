import { useMemo, useRef } from 'react';
import * as THREE from 'three';
import { useFrame } from '@react-three/fiber';

import { useFadeTo } from './fade';

const PARTICLE_COUNT = 420;
const ORBIT_NODES = 9;
const FLOAT_SPHERES = 6;

interface FloatSphere {
  x: number;
  baseY: number;
  z: number;
  size: number;
  speed: number;
  phase: number;
  color: string;
}

/**
 * AISecurityCore — the dominant 3D intelligence core that anchors the
 * cinematic hero. Layered so it reads clearly against the dark scene:
 * luminous nucleus, crystalline shells, geodesic wireframe cages, bright
 * scanning rings and arcs, an inner particle cloud, neural orbit nodes and
 * floating data spheres, all lit from within. Purely decorative.
 */
export function AISecurityCore({
  active,
  scale = 1,
  position = [0, 0, -1.5],
}: {
  active: boolean;
  scale?: number;
  position?: [number, number, number];
}) {
  const fadeGroup = useRef<THREE.Group>(null);
  const spin = useRef<THREE.Group>(null);
  const cage = useRef<THREE.Mesh>(null);
  const cageInner = useRef<THREE.Mesh>(null);
  const nucleus = useRef<THREE.Points>(null);
  const ringA = useRef<THREE.Mesh>(null);
  const ringB = useRef<THREE.Mesh>(null);
  const arcA = useRef<THREE.Mesh>(null);
  const arcB = useRef<THREE.Mesh>(null);
  const sphereRefs = useRef<(THREE.Mesh | null)[]>([]);
  const { apply } = useFadeTo(active, 3.4);

  const innerPoints = useMemo(() => {
    const positions = new Float32Array(PARTICLE_COUNT * 3);
    for (let i = 0; i < PARTICLE_COUNT; i++) {
      const r = Math.cbrt(Math.random()) * 1.12;
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

  const orbitNodes = useMemo(
    () =>
      Array.from({ length: ORBIT_NODES }, (_, i) => {
        const a = (i / ORBIT_NODES) * Math.PI * 2 + i * 0.4;
        return {
          x: Math.cos(a) * 2.7,
          y: Math.sin(a * 1.6) * 0.42,
          z: Math.sin(a) * 2.7,
          speed: 0.12 + (i % 3) * 0.05,
        };
      }),
    [],
  );

  const orbitLines = useMemo(() => {
    const positions: number[] = [];
    for (const node of orbitNodes) {
      positions.push(0, 0.15, 0, node.x, node.y, node.z);
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(positions), 3));
    return geo;
  }, [orbitNodes]);

  const floats = useMemo<FloatSphere[]>(
    () =>
      Array.from({ length: FLOAT_SPHERES }, (_, i) => ({
        x: 2.6 + (i % 3) * 0.55,
        baseY: -0.9 + i * 0.6,
        z: 0.4 + (i % 2) * 1.5,
        size: 0.11 + (i % 3) * 0.045,
        speed: 0.5 + i * 0.16,
        phase: i * 1.7,
        color: i % 2 === 0 ? '#7dd3fc' : '#c4b5fd',
      })),
    [],
  );

  useFrame((state, dt) => {
    apply(fadeGroup.current);
    const t = state.clock.elapsedTime;
    if (spin.current) {
      spin.current.rotation.y += dt * 0.2;
      spin.current.rotation.x = Math.sin(t * 0.2) * 0.18;
      spin.current.rotation.z = Math.cos(t * 0.24) * 0.12;
      const breathe = 1 + Math.sin(t * 0.9) * 0.03;
      spin.current.scale.setScalar(breathe);
    }
    if (cage.current) cage.current.rotation.y -= dt * 0.26;
    if (cageInner.current) cageInner.current.rotation.y += dt * 0.16;
    if (nucleus.current) {
      nucleus.current.rotation.x += dt * 0.16;
      nucleus.current.rotation.z -= dt * 0.11;
    }
    if (ringA.current) ringA.current.rotation.z += dt * 0.42;
    if (ringB.current) ringB.current.rotation.x += dt * 0.26;
    if (arcA.current) arcA.current.rotation.z -= dt * 0.95;
    if (arcB.current) arcB.current.rotation.y += dt * 0.72;

    sphereRefs.current.forEach((mesh, i) => {
      const f = floats[i];
      if (!mesh || !f) return;
      mesh.position.y = f.baseY + Math.sin(t * f.speed + f.phase) * 0.38;
      mesh.position.x = f.x + Math.cos(t * f.speed * 0.5 + f.phase) * 0.34;
      const mat = mesh.material as THREE.MeshBasicMaterial;
      mat.opacity = 0.65 + Math.sin(t * f.speed * 1.3 + f.phase) * 0.3;
    });
    void t;
  });

  return (
    <group position={position} scale={scale}>
      <group ref={fadeGroup}>
        {/* inner volumetric light so the shells and cage catch real edges */}
        <pointLight position={[0, 0, 0]} intensity={40} distance={16} decay={2} color="#a5b4fc" />

        <group ref={spin}>
          {/* luminous white-cyan nucleus */}
          <mesh>
            <sphereGeometry args={[0.5, 56, 56]} />
            <meshPhysicalMaterial
              color="#e0f2fe"
              emissive="#bae6fd"
              emissiveIntensity={2.75}
              roughness={0.15}
              metalness={0.05}
              transparent
              opacity={0.9}
              userData={{ base: 0.9 }}
            />
          </mesh>
          {/* inner glowing crystal */}
          <mesh>
            <icosahedronGeometry args={[0.98, 4]} />
            <meshPhysicalMaterial
              color="#3b82f6"
              emissive="#2563eb"
              emissiveIntensity={1.5}
              roughness={0.22}
              metalness={0.4}
              transparent
              opacity={0.34}
              depthWrite={false}
              userData={{ base: 0.34 }}
            />
          </mesh>
          {/* inner energy particle cloud */}
          <points ref={nucleus} geometry={innerPoints}>
            <pointsMaterial
              color="#dbeafe"
              size={0.06}
              sizeAttenuation
              transparent
              opacity={0.8}
              depthWrite={false}
              blending={THREE.AdditiveBlending}
              userData={{ base: 0.8 }}
            />
          </points>
          {/* translucent crystalline mid shell */}
          <mesh>
            <icosahedronGeometry args={[1.72, 4]} />
            <meshPhysicalMaterial
              color="#60a5fa"
              emissive="#1d4ed8"
              emissiveIntensity={0.55}
              transparent
              opacity={0.16}
              roughness={0.15}
              metalness={0.45}
              depthWrite={false}
              side={THREE.DoubleSide}
              userData={{ base: 0.16 }}
            />
          </mesh>
          {/* outer crystalline shell */}
          <mesh>
            <icosahedronGeometry args={[1.98, 5]} />
            <meshPhysicalMaterial
              color="#818cf8"
              emissive="#4338ca"
              emissiveIntensity={0.4}
              transparent
              opacity={0.11}
              roughness={0.1}
              metalness={0.6}
              depthWrite={false}
              side={THREE.DoubleSide}
              userData={{ base: 0.11 }}
            />
          </mesh>
          {/* geodesic wireframe cage */}
          <mesh ref={cage}>
            <icosahedronGeometry args={[2.12, 1]} />
            <meshBasicMaterial
              color="#a5b4fc"
              wireframe
              transparent
              opacity={0.42}
              depthWrite={false}
              userData={{ base: 0.42 }}
            />
          </mesh>
          {/* inner counter-rotating wireframe */}
          <mesh ref={cageInner}>
            <icosahedronGeometry args={[1.42, 1]} />
            <meshBasicMaterial
              color="#67e8f9"
              wireframe
              transparent
              opacity={0.22}
              depthWrite={false}
              userData={{ base: 0.22 }}
            />
          </mesh>

          {/* bright scanning rings */}
          <mesh ref={ringA}>
            <torusGeometry args={[2.45, 0.008, 8, 180]} />
            <meshBasicMaterial
              color="#22d3ee"
              transparent
              opacity={0.85}
              depthWrite={false}
              blending={THREE.AdditiveBlending}
              userData={{ base: 0.85 }}
            />
          </mesh>
          <mesh ref={ringB}>
            <torusGeometry args={[2.88, 0.005, 8, 180]} />
            <meshBasicMaterial
              color="#8b5cf6"
              transparent
              opacity={0.6}
              depthWrite={false}
              blending={THREE.AdditiveBlending}
              userData={{ base: 0.6 }}
            />
          </mesh>
          {/* thin sweeping scan arcs */}
          <mesh ref={arcA}>
            <torusGeometry args={[2.64, 0.014, 10, 120, Math.PI * 0.62]} />
            <meshBasicMaterial
              color="#7dd3fc"
              transparent
              opacity={0.95}
              depthWrite={false}
              blending={THREE.AdditiveBlending}
              userData={{ base: 0.95 }}
            />
          </mesh>
          <mesh ref={arcB}>
            <torusGeometry args={[3.04, 0.01, 10, 140, Math.PI * 0.5]} />
            <meshBasicMaterial
              color="#c4b5fd"
              transparent
              opacity={0.85}
              depthWrite={false}
              blending={THREE.AdditiveBlending}
              userData={{ base: 0.85 }}
            />
          </mesh>
        </group>

        {/* orbiting data nodes + spokes */}
        <group>
          <lineSegments geometry={orbitLines}>
            <lineBasicMaterial
              color="#6366f1"
              transparent
              opacity={0.3}
              depthWrite={false}
              blending={THREE.AdditiveBlending}
              userData={{ base: 0.3 }}
            />
          </lineSegments>
          {orbitNodes.map((node, i) => (
            <group key={i}>
              <mesh position={[node.x, node.y, node.z]}>
                <sphereGeometry args={[0.05 + (i % 3) * 0.015, 12, 12]} />
                <meshBasicMaterial
                  color={i % 2 === 0 ? '#a5b4fc' : '#22d3ee'}
                  transparent
                  opacity={0.9}
                  depthWrite={false}
                  blending={THREE.AdditiveBlending}
                  userData={{ base: 0.9 }}
                />
              </mesh>
              <mesh position={[node.x, node.y, node.z]}>
                <sphereGeometry args={[0.13, 12, 12]} />
                <meshBasicMaterial
                  color={i % 2 === 0 ? '#a5b4fc' : '#22d3ee'}
                  transparent
                  opacity={0.16}
                  depthWrite={false}
                  blending={THREE.AdditiveBlending}
                  userData={{ base: 0.16 }}
                />
              </mesh>
            </group>
          ))}
        </group>

        {/* floating data spheres drifting around the core */}
        {floats.map((f, i) => (
          <mesh
            key={i}
            position={[f.x, f.baseY, f.z]}
            ref={(el) => {
              sphereRefs.current[i] = el;
            }}
          >
            <sphereGeometry args={[f.size, 20, 20]} />
            <meshBasicMaterial
              color={f.color}
              transparent
              opacity={0.9}
              depthWrite={false}
              blending={THREE.AdditiveBlending}
              userData={{ base: 0.9 }}
            />
          </mesh>
        ))}
      </group>
    </group>
  );
}