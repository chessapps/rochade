/**
 * The compact state tokens of DESIGN.md: a dot or glyph and one word in
 * label-sm. Colour never carries the meaning alone; the word and the shape do
 * too. slate: nothing yet · amber: entered · rose: disputed · emerald:
 * confirmed. Same as the hall app.
 */

import type { ReactNode } from "react";

import type { ResultState, RoundState } from "../api";
import { ROUND_STATE_LABEL } from "../format";
import { Check, TriangleAlert } from "./icons";
import { cx } from "./ui";

export function Chip({
  tone,
  children,
  className,
  title,
}: {
  tone: "neutral" | "amber" | "rose" | "emerald" | "blue" | "dark";
  children: ReactNode;
  className?: string;
  title?: string;
}) {
  const style = {
    neutral: "border-line bg-subtle text-ink-2",
    amber: "border-amber-200 bg-amber-50 text-amber-800",
    rose: "border-rose-200 bg-rose-50 text-rose-700",
    emerald: "border-emerald-200 bg-emerald-50 text-emerald-700",
    blue: "border-blue-200 bg-blue-50 text-blue-700",
    dark: "border-ink bg-ink text-white",
  }[tone];
  return (
    <span
      title={title}
      className={cx(
        "inline-flex items-center gap-1 rounded-sm border px-1.5 py-0.5 text-label-sm whitespace-nowrap [&>svg]:size-3",
        style,
        className,
      )}
    >
      {children}
    </span>
  );
}

function Dot({ className }: { className: string }) {
  return <span aria-hidden className={cx("inline-block size-1.5 rounded-full", className)} />;
}

const STATE: Record<ResultState, { tone: "neutral" | "amber" | "rose" | "emerald"; word: string; mark: ReactNode }> = {
  empty: { tone: "neutral", word: "Awaiting", mark: <Dot className="bg-state-empty" /> },
  claimed: { tone: "amber", word: "Entered", mark: <Dot className="animate-pulse bg-state-claimed" /> },
  disputed: { tone: "rose", word: "Dispute", mark: <TriangleAlert /> },
  confirmed: { tone: "emerald", word: "Confirmed", mark: <Check /> },
};

/** Bar segments and the same hues on a swatch. */
export const STATE_BAR: Record<ResultState, string> = {
  empty: "bg-slate-200",
  claimed: "bg-state-claimed",
  disputed: "bg-state-disputed",
  confirmed: "bg-state-confirmed",
};

export const STATE_TEXT: Record<ResultState, string> = {
  empty: "text-ink-2",
  claimed: "text-amber-600",
  disputed: "text-rose-600",
  confirmed: "text-emerald-600",
};

export function StateChip({ state, className }: { state: ResultState; className?: string }) {
  const spec = STATE[state];
  return (
    <Chip tone={spec.tone} className={className}>
      {spec.mark}
      {spec.word}
    </Chip>
  );
}

const ROUND: Record<RoundState, { tone: "blue" | "amber" | "neutral"; dot: string }> = {
  open: { tone: "blue", dot: "animate-pulse bg-round-open" },
  confirmed: { tone: "amber", dot: "bg-round-released" },
  exported: { tone: "neutral", dot: "bg-round-exported" },
};

/** Where a round is: cobalt while open for entry, amber once released, slate when frozen. */
export function RoundChip({
  state,
  className,
  children,
}: {
  state: RoundState;
  className?: string;
  /** Anything to say after the state, e.g. how often it polls. */
  children?: ReactNode;
}) {
  const spec = ROUND[state];
  return (
    <Chip tone={spec.tone} className={className}>
      <Dot className={spec.dot} />
      {ROUND_STATE_LABEL[state]}
      {children}
    </Chip>
  );
}

export function DeviceChip({ state }: { state: "active" | "revoked" }) {
  return (
    <Chip tone={state === "active" ? "emerald" : "rose"}>
      <Dot className={state === "active" ? "bg-state-confirmed" : "bg-state-disputed"} />
      {state}
    </Chip>
  );
}
