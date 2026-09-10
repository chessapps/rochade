import type { RoundSummary } from "../api";
import { stepOf } from "../boards";
import { clockTime } from "../format";
import { Check } from "./icons";
import { cx } from "./ui";

const STEPS = ["Imported", "Entry open", "Released", "Exported"] as const;

/**
 * Where a round is in the loop. Four milestones in a row: the ones behind are
 * emerald, the one under way glows cobalt, the ones ahead are hairline frames.
 * The arbiter reads position, not prose; the clock times say when.
 */
export function RoundStepper({ round, className }: { round: RoundSummary; className?: string }) {
  const current = stepOf(round);
  const times = [round.imported_at, round.imported_at, round.released_at, round.exported_at];
  return (
    <ol className={cx("grid grid-cols-4 gap-2", className)} aria-label={`round ${round.number} progress`}>
      {STEPS.map((label, index) => {
        const done = index < current;
        const active = index === current;
        const future = !done && !active;
        return (
          <li key={label} className={cx("flex min-w-0 flex-col gap-1.5", future && "opacity-40")}>
            <div className="flex items-center gap-2">
              <span
                aria-current={active ? "step" : undefined}
                className={cx(
                  "flex size-6 shrink-0 items-center justify-center rounded-full font-mono text-[11px] font-bold transition-colors [&>svg]:size-3.5",
                  done && "bg-state-confirmed text-white",
                  active && "bg-accent text-white ring-4 ring-accent-soft",
                  future && "border border-line-strong bg-subtle text-ink-2",
                )}
              >
                {done ? <Check strokeWidth={3} /> : active ? (
                  <span aria-hidden className="size-2 animate-pulse rounded-full bg-white" />
                ) : (
                  index + 1
                )}
              </span>
              <span
                className={cx(
                  "truncate text-xs font-bold",
                  active ? "text-accent" : done ? "text-ink" : "text-ink-2",
                )}
              >
                {index + 1}. {label}
              </span>
            </div>
            <span
              className={cx(
                "pl-8 font-mono text-[11px]",
                active ? "font-semibold text-accent" : "text-ink-3",
              )}
            >
              {active
                ? `Active${times[index] ? ` (${clockTime(times[index])})` : ""}`
                : done
                  ? clockTime(times[index]) || "Done"
                  : "Pending"}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
