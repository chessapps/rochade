import type { RoundSummary } from "../api";
import { stepOf } from "../boards";
import { clockTime } from "../format";
import { cx } from "./ui";

const STEPS = ["Imported", "Entry open", "Released", "Exported"] as const;

/**
 * Where a round is in the loop. Four dots, the current one lit: the arbiter
 * reads position, not prose.
 */
export function RoundStepper({ round, className }: { round: RoundSummary; className?: string }) {
  const current = stepOf(round);
  const times = [round.imported_at, round.imported_at, round.released_at, round.exported_at];
  return (
    <ol className={cx("flex items-start", className)} aria-label={`round ${round.number} progress`}>
      {STEPS.map((label, index) => {
        const done = index < current;
        const active = index === current;
        return (
          <li key={label} className="flex min-w-0 flex-1 flex-col items-start">
            <div className="flex w-full items-center">
              <span
                aria-current={active ? "step" : undefined}
                className={cx(
                  "flex size-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold transition-colors",
                  done && "bg-emerald-600 text-white",
                  active && "bg-accent text-white ring-4 ring-accent-soft",
                  !done && !active && "border-2 border-slate-300 bg-white text-slate-400",
                )}
              >
                {done ? "✓" : index + 1}
              </span>
              {index < STEPS.length - 1 && (
                <span
                  className={cx("mx-1 h-0.5 flex-1", index < current ? "bg-emerald-600" : "bg-slate-200")}
                />
              )}
            </div>
            <span
              className={cx(
                "mt-1.5 pr-2 text-xs leading-tight",
                active ? "font-semibold text-ink" : "text-slate-500",
              )}
            >
              {label}
              {(done || active) && times[index] && (
                <span className="block text-[11px] font-normal text-slate-400 tabular-nums">
                  {clockTime(times[index])}
                </span>
              )}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
