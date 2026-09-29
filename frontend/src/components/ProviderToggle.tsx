import type { ScmProvider } from '../types';
import { Tabs } from './ui/Tabs';

const OPTIONS: { value: ScmProvider; label: string }[] = [
  { value: 'github', label: 'GitHub' },
  { value: 'gitlab', label: 'GitLab' },
];

interface ProviderToggleProps {
  value: ScmProvider;
  onChange: (provider: ScmProvider) => void;
}

/**
 * SCM provider selector. Backed by the shared `Tabs` primitive so it inherits
 * the roving-focus keyboard behaviour for free.
 */
export function ProviderToggle({ value, onChange }: ProviderToggleProps) {
  return (
    <Tabs
      aria-label="Source provider"
      items={OPTIONS}
      value={value}
      onChange={onChange}
      size="sm"
    />
  );
}
