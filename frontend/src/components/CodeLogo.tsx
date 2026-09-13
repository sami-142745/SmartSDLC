interface CodeLogoProps {
  className?: string;
  titleClassName?: string;
  taglineClassName?: string;
  showWordmark?: boolean;
}

export function CodeLogo({
  className = 'h-9 w-9 text-sm',
  titleClassName = 'text-sm',
  taglineClassName = 'text-[9px]',
  showWordmark = true,
}: CodeLogoProps) {
  return (
    <span className="inline-flex items-center gap-2.5">
      <span
        aria-hidden
        className={`relative inline-flex shrink-0 select-none items-center justify-center overflow-hidden rounded-lg bg-brand-gradient font-semibold text-white shadow-glow-sm ring-1 ring-accent-indigo/30 ${className}`}
      >
        <span className="tracking-[-0.02em]">SD</span>
        <span className="absolute inset-0 h-full w-full animate-scan-line bg-gradient-to-b from-transparent via-white/[0.08] to-transparent" />
        <span className="absolute -inset-px rounded-lg bg-white/[0.03]" />
      </span>
      {showWordmark && (
        <span className="inline-flex flex-col leading-none">
          <span className={`font-semibold tracking-[-0.015em] text-slate-100 ${titleClassName}`}>
            SmartSDLC
          </span>
          <span className={`mt-1 font-mono uppercase tracking-[0.22em] text-slate-500 ${taglineClassName}`}>
            AI Review
          </span>
        </span>
      )}
    </span>
  );
}
