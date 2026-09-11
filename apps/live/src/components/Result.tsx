/**
 * A result cell: the score as printed, and how far it can be trusted. A
 * preliminary result is amber with a dot; a confirmed one is plain ink; a
 * pending one is a dash.
 */

import type { Shown } from "../api";
import { cx } from "./ui";

export const SHOWN_LABEL: Record<Shown, string> = {
  pending: "no result yet",
  preliminary: "preliminary, not yet confirmed by the arbiter",
  confirmed: "confirmed",
};

export function Result({
  result,
  state,
  className,
}: {
  result: string;
  state: Shown;
  className?: string;
}) {
  if (state === "pending" || !result) {
    return (
      <span className={cx("font-mono text-ink-3", className)} aria-label="no result yet">
        –
      </span>
    );
  }
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1.5 font-mono font-semibold whitespace-nowrap",
        state === "preliminary" ? "text-amber-text" : "text-ink",
        className,
      )}
      title={SHOWN_LABEL[state]}
    >
      {state === "preliminary" && (
        <span aria-hidden className="size-1.5 rounded-full bg-state-claimed" />
      )}
      <span>{result}</span>
      {state === "preliminary" && <span className="sr-only">(preliminary)</span>}
    </span>
  );
}
