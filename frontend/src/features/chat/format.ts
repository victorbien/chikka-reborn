/** Dates are shown in the browser's time zone and language. */

const time = new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" });
const full = new Intl.DateTimeFormat(undefined, { dateStyle: "full", timeStyle: "short" });
const dayFormat = new Intl.DateTimeFormat(undefined, {
  weekday: "long",
  month: "long",
  day: "numeric",
});
const dayWithYear = new Intl.DateTimeFormat(undefined, {
  weekday: "long",
  year: "numeric",
  month: "long",
  day: "numeric",
});
const shortDate = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" });

export function formatTime(iso: string): string {
  return time.format(new Date(iso));
}

export function formatFull(iso: string): string {
  return full.format(new Date(iso));
}

export function dayKey(iso: string): string {
  const date = new Date(iso);
  return `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;
}

/** "Today", "Yesterday", or the date, for separators between days. */
export function formatDay(iso: string, now: Date = new Date()): string {
  const date = new Date(iso);
  const startOf = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const days = Math.round((startOf(now) - startOf(date)) / 86_400_000);
  if (days === 0) return "Today";
  if (days === 1) return "Yesterday";
  return date.getFullYear() === now.getFullYear()
    ? dayFormat.format(date)
    : dayWithYear.format(date);
}

/** Conversation list: time today, otherwise a short date. */
export function formatListTime(iso: string | null, now: Date = new Date()): string {
  if (!iso) return "";
  return dayKey(iso) === dayKey(now.toISOString())
    ? formatTime(iso)
    : shortDate.format(new Date(iso));
}

export function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
