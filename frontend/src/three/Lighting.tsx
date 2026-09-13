export function Lighting() {
  return (
    <>
      <ambientLight intensity={0.32} color="#1e3a8a" />
      <hemisphereLight args={['#4f6bff', '#05060d', 0.85]} />
      {/* cool electric-blue key light */}
      <directionalLight position={[6, 8, 5]} intensity={1.7} color="#9db8ff" />
      {/* violet rim light from behind */}
      <directionalLight position={[-7, -2, -6]} intensity={1.15} color="#8b5cf6" />
      {/* cyan fill point */}
      <pointLight position={[0, 0.4, 2.6]} intensity={34} distance={30} color="#38bdf8" />
      <pointLight position={[-7, -3, -5]} intensity={18} distance={42} color="#22d3ee" />
    </>
  );
}