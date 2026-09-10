import { severityBadgeClasses, severityLabel } from '../utils/severity';

interface SeverityBadgeProps {
  severity: string | null | undefined;
}

export function SeverityBadge({ severity }: SeverityBadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${severityBadgeClasses(severity)}`}
    >
      {severityLabel(severity)}
    </span>
  );
}