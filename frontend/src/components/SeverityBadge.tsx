import { severityBadgeClasses, severityDotColor, severityLabel } from '../utils/severity';

interface SeverityBadgeProps {
  severity: string | null | undefined;
}

export function SeverityBadge({ severity }: SeverityBadgeProps) {
  return (
    <span className={`chip relative inline-flex items-center gap-1.5 ${severityBadgeClasses(severity)}`}>
      <span
        aria-hidden
        className="relative h-1.5 w-1.5 rounded-full"
        style={{ backgroundColor: severityDotColor(severity), boxShadow: `0 0 6px ${severityDotColor(severity)}` }}
      />
      {severityLabel(severity)}
    </span>
  );
}
