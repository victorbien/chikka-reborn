const FORMAT = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });

/** A date and time in the viewer's locale, for lists and history. */
export function formatDateTime(iso: string): string {
  return FORMAT.format(new Date(iso));
}
