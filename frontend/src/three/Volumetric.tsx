import { useMemo } from 'react';
import * as THREE from 'three';
import { Float } from '@react-three/drei';

function makeGlowTexture() {
  const canvas = document.createElement('canvas');
  canvas.width = 128;
  canvas.height = 128;
  const ctx = canvas.getContext('2d');
  if (ctx) {
    const gradient = ctx.createRadialGradient(64, 64, 0, 64, 64, 64);
    gradient.addColorStop(0, 'rgba(255,255,255,1)');
    gradient.addColorStop(0.25, 'rgba(255,255,255,0.45)');
    gradient.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, 128, 128);
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.needsUpdate = true;
  return texture;
}

function Glow({
  position,
  color,
  scale,
  opacity,
}: {
  position: [number, number, number];
  color: string;
  scale: number;
  opacity: number;
}) {
  const texture = useMemo(() => makeGlowTexture(), []);

  return (
    <Float speed={1.6} rotationIntensity={0} floatIntensity={0.5}>
      <sprite position={position} scale={[scale, scale, 1]}>
        <spriteMaterial
          map={texture}
          color={color}
          transparent
          opacity={opacity}
          depthWrite={false}
          blending={THREE.AdditiveBlending}
        />
      </sprite>
    </Float>
  );
}

/** Soft volumetric glows (additive sprites) layered behind the scene. */
export function Volumetric({
  variant,
}: {
  variant: 'core' | 'aura' | 'pipeline' | 'network' | 'analysis' | 'scan';
}) {
  return (
    <group>
      <Glow position={[0, 0.35, -0.6]} color="#6366f1" scale={7.5} opacity={variant === 'core' || variant === 'network' ? 0.3 : 0.18} />
      <Glow position={[8, -4, -9]} color="#22d3ee" scale={6} opacity={variant === 'network' || variant === 'scan' ? 0.16 : 0.12} />
      <Glow position={[-9, -3, -11]} color="#8b5cf6" scale={6.5} opacity={variant === 'network' || variant === 'analysis' ? 0.18 : 0.12} />
      {(variant === 'pipeline' || variant === 'analysis') && <Glow position={[0, 0.4, -0.8]} color="#a78bfa" scale={4} opacity={0.24} />}
      {variant === 'scan' && <Glow position={[0, 0.4, -0.8]} color="#67e8f9" scale={4} opacity={0.22} />}
    </group>
  );
}