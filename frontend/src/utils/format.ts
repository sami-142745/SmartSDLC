export function formatDate(value: string | null | undefined): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function formatShortDate(value: string | null | undefined): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export function formatCount(value: number | null | undefined): string {
  return (value ?? 0).toLocaleString();
}

export function formatPercent(value: number | null | undefined): string {
  const number = Number(value ?? 0);
  return `${Math.round(number * 100)}%`;
}

export function truncate(text: string | null | undefined, max = 80): string {
  if (!text) return '';
  return text.length <= max ? text : `${text.slice(0, max - 1)}…`;
}

export function initials(login: string | null | undefined): string {
  return (login || '?').slice(0, 2).toUpperCase();
}