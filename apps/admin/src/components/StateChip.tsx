import type { ResultState, RoundState } from "../api";
import { RESULT_STATE_LABEL, ROUND_STATE_LABEL } from "../format";
import { cx } from "./ui";

/** slate: nothing yet · amber: entered · rose: disputed · emerald: confirmed. Same as the hall app. */
export const STATE_STYLE: Record<ResultState, string> = {
  empty: "bg-slate-100 text-slate-600",
  claimed: "bg-amber-100 text-amber-900",
  disputed: "bg-rose-100 text-rose-800",
  confirmed: "bg-emerald-100 text-emerald-800",
};

export const STATE_BAR: Record<ResultState, string> = {
  empty: "bg-slate-200",
  claimed: "bg-amber-400",
  disputed: "bg-rose-500",
  confirmed: "bg-emerald-500",
};

export function StateChip({ state, className }: { state: ResultState; className?: string }) {
  return (
    <span
      className={cx(
        "inline-block rounded-md px-2 py-0.5 text-xs font-medium whitespace-nowrap",
        STATE_STYLE[state],
        className,
      )}
    >
      {RESULT_STATE_LABEL[state]}
    </span>
  );
}

const ROUND_STYLE: Record<RoundState, string> = {
  open: "bg-accent-soft text-blue-900",
  confirmed: "bg-amber-100 text-amber-900",
  exported: "bg-slate-100 text-slate-600",
};

export function RoundChip({ state, className }: { state: RoundState; className?: string }) {
  return (
    <span
      className={cx(
        "inline-block rounded-md px-2 py-0.5 text-xs font-medium whitespace-nowrap",
        ROUND_STYLE[state],
        className,
      )}
    >
      {ROUND_STATE_LABEL[state]}
    </span>
  );
}

export function DeviceChip({ state }: { state: "active" | "expired" | "revoked" }) {
  const style = {
    active: "bg-emerald-100 text-emerald-800",
    expired: "bg-slate-100 text-slate-600",
    revoked: "bg-rose-100 text-rose-800",
  }[state];
  return (
    <span className={cx("inline-block rounded-md px-2 py-0.5 text-xs font-medium", style)}>
      {state}
    </span>
  );
}
