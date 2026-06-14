export function formatDate(dateString?: string): string {
  if (!dateString) return '-';
  try {
    return new Date(dateString).toLocaleString();
  } catch {
    return dateString;
  }
}

export function formatNumber(num?: number): string {
  if (num === undefined || num === null) return '-';
  return new Intl.NumberFormat().format(num);
}
