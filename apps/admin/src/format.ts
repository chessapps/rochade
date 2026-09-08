/**
 * Labels. All of them in one place so the same thing reads the same on every
 * screen -- a result is "½:½" everywhere, a board with nothing on it is
 * "no result" everywhere.
 */

import type { ResultState, RoundState } from "./api";

export const RESULT_STATE_LABEL: Record<ResultState, string> = {
  empty: "no result",
  claimed: "entered",
  disputed: "disputed",
  confirmed: "confirmed",
};

export const ROUND_STATE_LABEL: Record<RoundState, string> = {
  open: "open for entry",
  confirmed: "released — ready to export",
  exported: "exported — frozen",
};

const CODE: Record<string, string> = { "1": "1", "=": "½", "0": "0", "+": "+", "-": "−" };
const BYE: Record<string, string> = {
  U: "1 · bye",
  F: "1 · bye",
  "1": "1 · bye",
  H: "½ · bye",
  "=": "½ · bye",
  Z: "0 · absent",
};

/**
 * A game's result as printed on a pairing list. A bye has one side only, and
 * its code says how many points it was worth.
 */
export function resultLabel(white: string, black: string, isBye = false): string {
  if (white === " ") return "";
  if (isBye) return BYE[white] ?? `${CODE[white] ?? white} · bye`;
  const w = CODE[white] ?? white;
  const b = CODE[black] ?? black;
  return `${w}:${b}`;
}

export function plural(count: number, one: string, many = `${one}s`): string {
  return `${count} ${count === 1 ? one : many}`;
}

/** "just now", "12s ago", "4 min ago", then the clock time. */
export function relativeTime(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return "never";
  const then = new Date(iso).getTime();
  const seconds = Math.max(0, Math.round((now - then) / 1000));
  if (seconds < 5) return "just now";
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  return clockTime(iso);
}

export function clockTime(iso: string | null | undefined): string {
  if (!iso) return "";
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
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

export function joinNonEmpty(parts: (string | null | undefined | false)[], sep = " · "): string {
  return parts.filter(Boolean).join(sep);
}
