import { Canvas } from '@react-three/fiber';
import { useLocation } from 'react-router-dom';
import * as THREE from 'three';

import { useMotionPrefs } from '../hooks/useMotionPrefs';
import { AISecurityCore } from './AISecurityCore';
import { AnalysisCore } from './AnalysisCore';
import { Aurora } from './Aurora';
import { CameraRig, type CameraProfile } from './CameraRig';
import { CodeScanner } from './CodeScanner';
import { Effects } from './Effects';
import { Lighting } from './Lighting';
import { NetworkRosette } from './NetworkRosette';
import { ParticleField } from './ParticleField';
import { RepositoryGalaxy } from './RepositoryGalaxy';
import { Volumetric } from './Volumetric';

export type SceneVariant = 'core' | 'aura' | 'pipeline' | 'network' | 'analysis' | 'scan';

const PARTICLE_COUNT = {
  mobile: 200,
  tablet: 450,
  desktop: 950,
} as const;

const CAMERA_PROFILE: Record<SceneVariant, CameraProfile> = {
  core: 'orbit',
  network: 'drift',
  pipeline: 'drift',
  analysis: 'push',
  scan: 'drift',
  aura: 'drift',
};

/**
 * CyberWorld — the single lazy-loaded WebGL environment rendered behind the
 * app. Variants compose different hero objects (AI security core on login /
 * dashboard, repository galaxy on repositories, analysis core on review,
 * code scanner on PR detail). Everything is decorative and sits behind the
 * DOM UI, which carries the real data.
 */
export function CyberScene({ variant = 'aura' }: { variant?: SceneVariant }) {
  const { tier, reduced } = useMotionPrefs();
  const location = useLocation();
  const isDashboard = location.pathname.startsWith('/dashboard');

  const coreActive = variant === 'core' || variant === 'network';
  const analysisActive = variant === 'analysis' || variant === 'pipeline';
  const galaxyActive = variant === 'network';
  const scanActive = variant === 'scan';

  // The dashboard is the command-center hero: the AI core is the dominant
  // object, filling the center-right of the first viewport. Everything else
  // (login included) keeps the smaller, balanced composition.
  const coreScale =
    variant === 'core'
      ? isDashboard
        ? tier === 'desktop'
          ? 1.6
          : tier === 'tablet'
            ? 1.5
            : 1.2
        : 1.38
      : 0.95;
  const corePosition: [number, number, number] =
    variant === 'core'
      ? isDashboard
        ? tier === 'desktop'
          ? [2.1, 0.0, -1.9]
          : tier === 'tablet'
            ? [1.5, 0.05, -1.8]
            : [0, 0.18, -1.5]
        : [1.32, 0.12, -2.1]
      : [0, 0.1, -1.9];

  return (
    <Canvas
      style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}
      dpr={[1, reduced ? 1 : tier === 'mobile' ? 1.25 : 1.75]}
      camera={{ position: [0, 0, 10], fov: 42, near: 0.1, far: 70 }}
      gl={{
        antialias: false,
        alpha: true,
        powerPreference: 'high-performance',
        stencil: false,
        depth: true,
      }}
      frameloop={reduced ? 'demand' : 'always'}
      onCreated={({ scene }) => {
        scene.fog = new THREE.FogExp2(0x03050b, 0.04);
        scene.background = null;
      }}
    >
      <Lighting />
      <Aurora />
      <ParticleField count={PARTICLE_COUNT[tier]} />
      {coreActive && !scanActive && (
        <AISecurityCore active scale={coreScale} position={corePosition} />
      )}
      <AnalysisCore active={analysisActive} />
      <RepositoryGalaxy active={galaxyActive} count={variant === 'network' ? 9 : 6} />
      <CodeScanner active={scanActive} />
      <NetworkRosette active={variant === 'pipeline'} />
      <Volumetric variant={variant} />
      {!reduced && <CameraRig profile={CAMERA_PROFILE[variant]} />}
      {!reduced && <Effects />}
    </Canvas>
  );
}