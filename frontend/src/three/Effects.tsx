import { EffectComposer, Bloom, Vignette } from '@react-three/postprocessing';

/**
 * Post-processing: cinematic bloom for the emissive core + a soft vignette.
 * DepthOfField is intentionally avoided to keep the UI (DOM content layered
 * above) crisp and readable.
 */
export function Effects() {
  return (
    <EffectComposer multisampling={0} resolutionScale={0.6}>
      <Bloom
        mipmapBlur
        intensity={1.05}
        luminanceThreshold={0.16}
        luminanceSmoothing={0.14}
        radius={0.68}
      />
      <Vignette eskil={false} offset={0.28} darkness={0.52} />
    </EffectComposer>
  );
}