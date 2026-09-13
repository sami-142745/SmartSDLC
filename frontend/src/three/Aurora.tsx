import { useRef } from 'react';
import * as THREE from 'three';
import { useFrame } from '@react-three/fiber';

const VERTEX = /* glsl */ `
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const FRAGMENT = /* glsl */ `
  uniform float uTime;
  varying vec2 vUv;
  void main() {
    float t = uTime * 0.05;
    float n1 = sin(vUv.x * 4.0 + t) * sin(vUv.y * 3.0 - t * 0.6);
    float band = sin(vUv.x * 6.0 - t * 1.4 + n1 * 2.0) * 0.5 + 0.5;
    float sweep = smoothstep(0.0, 1.0, vUv.y + sin(vUv.x * 2.5 + t * 0.8) * 0.15);
    vec3 cA = vec3(0.16, 0.2, 0.95);
    vec3 cB = vec3(0.45, 0.24, 0.98);
    vec3 cC = vec3(0.12, 0.78, 0.96);
    vec3 col = mix(cA, cB, band);
    col = mix(col, cC, band * 0.3);
    float alpha = sweep * (0.17 + 0.12 * band);
    gl_FragColor = vec4(col * alpha, alpha);
  }
`;

function AuroraLayer({
  position,
  rotation,
  scale,
}: {
  position: [number, number, number];
  rotation: [number, number, number];
  scale: [number, number, number];
}) {
  const mat = useRef<THREE.ShaderMaterial>(null);

  useFrame((state) => {
    if (mat.current) mat.current.uniforms.uTime.value = state.clock.elapsedTime;
  });

  return (
    <mesh position={position} rotation={rotation} scale={scale}>
      <planeGeometry args={[1, 1, 1]} />
      <shaderMaterial
        ref={mat}
        vertexShader={VERTEX}
        fragmentShader={FRAGMENT}
        uniforms={{ uTime: { value: 0 } }}
        transparent
        depthWrite={false}
        blending={THREE.AdditiveBlending}
        side={THREE.DoubleSide}
      />
    </mesh>
  );
}

export function Aurora() {
  return (
    <group>
      <AuroraLayer position={[0, 2, -11]} rotation={[-0.25, 0, 0]} scale={[22, 9, 1]} />
      <AuroraLayer position={[-4.5, -3, -14]} rotation={[-0.4, 0.3, 0]} scale={[26, 10, 1]} />
      <AuroraLayer position={[5.5, -2, -16]} rotation={[-0.35, -0.4, 0]} scale={[24, 9, 1]} />
    </group>
  );
}