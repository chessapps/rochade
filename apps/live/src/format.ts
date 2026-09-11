export function plural(count: number, one: string, many = `${one}s`): string {
  return `${count} ${count === 1 ? one : many}`;
}

export function dateLabel(iso: string | null | undefined): string {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString([], { day: "numeric", month: "short", year: "numeric" });
}

export function dateRange(start: string | null | undefined, end: string | null | undefined): string {
  if (!start && !end) return "";
  if (start && end && start !== end) return `${dateLabel(start)} – ${dateLabel(end)}`;
  return dateLabel(start ?? end);
}

/** "just now", "12s ago", "4 min ago", then the clock time. */
export function relativeTime(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  const seconds = Math.max(0, Math.round((now - then) / 1000));
  if (seconds < 5) return "just now";
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

/** 2.5 -> "2½", 1 -> "1", 0.5 -> "½". */
export function points(value: number | null | undefined): string {
  if (value === null || value === undefined) return "";
  const whole = Math.floor(value);
  const half = value - whole >= 0.5;
  if (whole === 0 && half) return "½";
  return `${whole}${half ? "½" : ""}`;
}

export function joinNonEmpty(parts: (string | null | undefined | false)[], sep = " · "): string {
  return parts.filter(Boolean).join(sep);
}
