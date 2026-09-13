import { useMemo, useRef } from 'react';
import * as THREE from 'three';
import { useFrame } from '@react-three/fiber';

const VERTEX = /* glsl */ `
  uniform float uTime;
  attribute float aOffset;
  attribute float aSize;
  varying float vAlpha;
  void main() {
    vec3 p = position;
    float phase = aOffset * 6.28318;
    p.x += sin(uTime * 0.15 + phase) * 0.9;
    p.y += sin(uTime * 0.1 + phase * 1.7) * 0.7;
    vec4 mv = modelViewMatrix * vec4(p, 1.0);
    float d = -mv.z;
    vec4 clip = projectionMatrix * mv;
    gl_Position = clip;
    float size = aSize * (0.85 + 0.3 * sin(uTime * 0.8 + phase));
    gl_PointSize = size * (24.0 / d);
    vAlpha = smoothstep(28.0, 6.0, d) * (0.3 + 0.7 * aOffset);
  }
`;

const FRAGMENT = /* glsl */ `
  varying float vAlpha;
  void main() {
    float d = length(gl_PointCoord - vec2(0.5));
    float a = smoothstep(0.5, 0.06, d) * vAlpha;
    if (a < 0.015) discard;
    gl_FragColor = vec4(vec3(0.68, 0.76, 1.0) * a, a);
  }
`;

function mulberry32(seed: number) {
  let a = seed;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function ParticleField({ count = 800 }: { count?: number }) {
  const mat = useRef<THREE.ShaderMaterial>(null);
  const points = useRef<THREE.Points>(null);

  const data = useMemo(() => {
    const rnd = mulberry32(9917);
    const positions = new Float32Array(count * 3);
    const offsets = new Float32Array(count);
    const sizes = new Float32Array(count);
    for (let i = 0; i < count; i++) {
      positions[i * 3] = (rnd() * 2 - 1) * 16;
      positions[i * 3 + 1] = (rnd() * 2 - 1) * 9;
      positions[i * 3 + 2] = -8 - rnd() * 5;
      offsets[i] = rnd();
      sizes[i] = 0.5 + rnd() * 1.4;
    }
    return { positions, offsets, sizes };
  }, [count]);

  useFrame((state) => {
    if (mat.current) mat.current.uniforms.uTime.value = state.clock.elapsedTime;
    if (points.current) points.current.rotation.y += 0.0004;
  });

  return (
    <points ref={points}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[data.positions, 3]} />
        <bufferAttribute attach="attributes-aOffset" args={[data.offsets, 1]} />
        <bufferAttribute attach="attributes-aSize" args={[data.sizes, 1]} />
      </bufferGeometry>
      <shaderMaterial
        ref={mat}
        vertexShader={VERTEX}
        fragmentShader={FRAGMENT}
        uniforms={{ uTime: { value: 0 } }}
        transparent
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  );
}