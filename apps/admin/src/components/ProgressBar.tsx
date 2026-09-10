import type { Counts } from "../boards";
import { plural } from "../format";
import { STATE_BAR, STATE_TEXT } from "./StateChip";
import { cx } from "./ui";

const ORDER = ["confirmed", "claimed", "disputed", "empty"] as const;
const WORD = { confirmed: "Confirmed", claimed: "Entered", disputed: "Dispute", empty: "Awaiting" } as const;

/**
 * How far the round is, and of what it is made: confirmed, entered, disputed,
 * empty, left to right. The fastest read of a round there is.
 */
export function ProgressBar({
  counts,
  className,
  size = "md",
  caption = true,
  legend = false,
}: {
  counts: Counts;
  className?: string;
  size?: "sm" | "md";
  /** The sentence under the bar. */
  caption?: boolean;
  /** Swatches with the four counts, above the bar. */
  legend?: boolean;
}) {
  const total = Math.max(counts.boards, 1);
  const segments = ORDER.map((state) => ({ state, width: (counts[state] / total) * 100 }));
  const done = counts.confirmed + counts.claimed;
  return (
    <div className={cx("flex flex-col gap-1.5", className)}>
      {legend && (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[11px]">
          {ORDER.map((state) =>
            counts[state] > 0 || state === "confirmed" ? (
              <span
                key={state}
                className={cx(
                  "flex items-center gap-1.5",
                  state === "disputed" ? "font-bold text-rose-text" : "text-ink-2",
                  state === "empty" && "text-ink-3",
                )}
              >
                <span aria-hidden className={cx("size-2.5 rounded-sm", STATE_BAR[state])} />
                {counts[state]} {WORD[state]}
              </span>
            ) : null,
          )}
        </div>
      )}
      <div
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={counts.boards}
        aria-valuenow={done}
        aria-label={`${done} of ${plural(counts.boards, "board")} entered`}
        className={cx("flex overflow-hidden rounded-full bg-subtle", size === "sm" ? "h-2" : "h-2.5")}
      >
        {segments.map(
          (segment) =>
            segment.width > 0 && (
              <div
                key={segment.state}
                style={{ width: `${segment.width}%` }}
                title={`${counts[segment.state]} ${WORD[segment.state]}`}
                className={cx(
                  "h-full transition-[width] duration-300",
                  STATE_BAR[segment.state],
                  segment.state === "disputed" && "animate-pulse",
                )}
              />
            ),
        )}
      </div>
      {caption && (
        <p className="text-body-sm text-ink-2">
          {done} of {plural(counts.boards, "board")} entered
          {counts.disputed > 0 && (
            <span className={STATE_TEXT.disputed}> · {counts.disputed} disputed</span>
          )}
          {counts.empty > 0 && <span> · {counts.empty} empty</span>}
        </p>
      )}
    </div>
  );
}
