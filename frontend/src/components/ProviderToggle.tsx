import type { ScmProvider } from '../types';

const OPTIONS: { value: ScmProvider; label: string }[] = [
  { value: 'github', label: 'GitHub' },
  { value: 'gitlab', label: 'GitLab' },
];

interface ProviderToggleProps {
  value: ScmProvider;
  onChange: (provider: ScmProvider) => void;
}

export function ProviderToggle({ value, onChange }: ProviderToggleProps) {
  return (
    <div
      role="tablist"
      aria-label="Source provider"
      className="flex w-fit border border-white/[0.06] bg-surface-1 p-0.5"
    >
      {OPTIONS.map((option) => (
        <button
          key={option.value}
          type="button"
          role="tab"
          aria-selected={value === option.value}
          onClick={() => onChange(option.value)}
          className={`px-4 py-1.5 text-sm font-medium transition-colors duration-150 ${
            value === option.value
              ? 'bg-white/[0.06] text-accent-indigo'
              : 'text-slate-400 hover:text-white'
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}