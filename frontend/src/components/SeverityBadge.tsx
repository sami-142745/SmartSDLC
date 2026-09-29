import { severityBadgeClasses, severityDotColor, severityLabel } from '../utils/severity';
import { cn } from '../lib/cn';

interface SeverityBadgeProps {
  severity: string | null | undefined;
  className?: string;
  /** Show the label text. Set false for a dot-only indicator in dense tables. */
  labelled?: boolean;
}

export function SeverityBadge({ severity, className, labelled = true }: SeverityBadgeProps) {
  const color = severityDotColor(severity);
  return (
    <span
      className={cn('chip', severityBadgeClasses(severity), className)}
      // The text label is the accessible name; the dot is decorative only.
      title={severityLabel(severity)}
    >
      <span
        aria-hidden
        className="h-1.5 w-1.5 shrink-0 rounded-full"
        style={{ backgroundColor: color, boxShadow: `0 0 6px ${color}` }}
      />
      {labelled ? severityLabel(severity) : <span className="sr-only">{severityLabel(severity)}</span>}
    </span>
  );
}
