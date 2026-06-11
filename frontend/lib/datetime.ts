// Match kickoff helpers. The API gives the date ("2026-06-15") and time in UTC
// ("20:00"); these convert to the viewer's local timezone for display.
//
// Safe to format in local time without hydration concerns: the fixture is
// fetched client-side (see fixture-section.tsx), so match times never appear in
// the server-rendered HTML.

/** Builds a UTC Date from the API's date + time fields. Returns null if invalid. */
export function matchKickoff(date: string, timeUtc: string): Date | null {
  if (!date) return null;
  const time = /^\d{1,2}:\d{2}$/.test(timeUtc) ? timeUtc : "00:00";
  const d = new Date(`${date}T${time}:00Z`);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** "17:00" — kickoff time in the viewer's local timezone (24h). */
export function formatLocalTime(
  date: string,
  timeUtc: string,
  locale: string
): string {
  const d = matchKickoff(date, timeUtc);
  if (!d || !timeUtc) return "";
  return new Intl.DateTimeFormat(locale, {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(d);
}

/** "GMT-3" / "ART" — short name of the viewer's local timezone. */
export function localTimeZoneName(date: string, locale: string): string {
  const d = matchKickoff(date, "12:00");
  if (!d) return "";
  const parts = new Intl.DateTimeFormat(locale, {
    timeZoneName: "short",
    hour: "2-digit",
  }).formatToParts(d);
  return parts.find((p) => p.type === "timeZoneName")?.value ?? "";
}

/**
 * "2026-06-14" — the viewer's local calendar date for a given kickoff.
 * Falls back to the UTC date when time_utc is absent (so grouping stays stable).
 */
export function localDateString(date: string, timeUtc: string): string {
  const d = matchKickoff(date, timeUtc);
  if (!d || !timeUtc) return date;
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}
