import type { Counts } from "../boards";
import { plural } from "../format";
import { STATE_BAR } from "./StateChip";
import { cx } from "./ui";

/**
 * How far the round is, and of what it is made: confirmed, entered, disputed,
 * empty, left to right. The fastest read of a round there is.
 */
export function ProgressBar({ counts, className }: { counts: Counts; className?: string }) {
  const total = Math.max(counts.boards, 1);
  const segments = (["confirmed", "claimed", "disputed", "empty"] as const).map((state) => ({
    state,
    width: (counts[state] / total) * 100,
  }));
  const done = counts.confirmed + counts.claimed;
  return (
    <div className={cx("flex flex-col gap-1", className)}>
      <div
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={counts.boards}
        aria-valuenow={done}
        aria-label={`${done} of ${plural(counts.boards, "board")} entered`}
        className="flex h-2 overflow-hidden rounded-full bg-slate-200"
      >
        {segments.map(
          (segment) =>
            segment.width > 0 && (
              <div
                key={segment.state}
                style={{ width: `${segment.width}%` }}
                className={cx("h-full transition-[width] duration-300", STATE_BAR[segment.state])}
              />
            ),
        )}
      </div>
      <p className="text-xs text-slate-500 tabular-nums">
        {done} of {plural(counts.boards, "board")} entered
        {counts.disputed > 0 && (
          <span className="text-rose-700"> · {counts.disputed} disputed</span>
        )}
        {counts.empty > 0 && <span> · {counts.empty} empty</span>}
      </p>
    </div>
  );
}
