/**
 * Ambient background: a fixed stack of CSS-only radial washes over the
 * #09090B canvas. Deliberately no WebGL, no canvas loop and no scroll-linked
 * work — it must cost nothing on low-power devices and respect
 * `prefers-reduced-motion`.
 */
export function Ambient() {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      {/* Brand wash, top-left. */}
      <div
        className="absolute -left-[10%] -top-[15%] h-[60vh] w-[60vw] rounded-full opacity-60 blur-[120px]"
        style={{
          background:
            'radial-gradient(circle at center, rgba(139,92,246,0.20) 0%, rgba(99,102,241,0.08) 45%, transparent 70%)',
        }}
      />
      {/* Cyan counter-wash, bottom-right. */}
      <div
        className="absolute -bottom-[20%] -right-[8%] h-[55vh] w-[50vw] rounded-full opacity-50 blur-[130px]"
        style={{
          background:
            'radial-gradient(circle at center, rgba(34,211,238,0.16) 0%, rgba(45,212,191,0.05) 48%, transparent 72%)',
        }}
      />
      {/* Faint engineering grid for depth. */}
      <div
        className="absolute inset-0 opacity-[0.5]"
        style={{
          backgroundImage:
            'linear-gradient(to right, rgba(255,255,255,0.018) 1px, transparent 1px), linear-gradient(to bottom, rgba(255,255,255,0.018) 1px, transparent 1px)',
          backgroundSize: '64px 64px',
          maskImage: 'radial-gradient(ellipse 90% 70% at 50% 0%, black 20%, transparent 78%)',
          WebkitMaskImage: 'radial-gradient(ellipse 90% 70% at 50% 0%, black 20%, transparent 78%)',
        }}
      />
      {/* Vignette to keep content legible over the washes. */}
      <div
        className="absolute inset-0"
        style={{
          background:
            'radial-gradient(ellipse 120% 100% at 50% 50%, transparent 35%, rgba(9,9,11,0.72) 100%)',
        }}
      />
    </div>
  );
}
