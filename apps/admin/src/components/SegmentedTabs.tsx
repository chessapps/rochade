/**
 * A row of filter pills with counts. The active one is ink; the one that
 * means trouble turns rose as soon as its count is above zero, so the arbiter
 * sees it before reading it.
 */

import { cx } from "./ui";

export interface Segment<K extends string> {
  key: K;
  label: string;
  count: number;
  /** Rose when non-zero. */
  alert?: boolean;
}

export function SegmentedTabs<K extends string>({
  label,
  segments,
  value,
  onChange,
  className,
}: {
  label: string;
  segments: Segment<K>[];
  value: K;
  onChange: (key: K) => void;
  className?: string;
}) {
  return (
    <div role="tablist" aria-label={label} className={cx("flex gap-1 overflow-x-auto", className)}>
      {segments.map((segment) => {
        const active = value === segment.key;
        const alert = Boolean(segment.alert && segment.count > 0);
        return (
          <button
            key={segment.key}
            role="tab"
            type="button"
            aria-selected={active}
            onClick={() => onChange(segment.key)}
            className={cx(
              "inline-flex min-h-10 items-center gap-1.5 rounded border px-3 text-xs font-semibold whitespace-nowrap transition-colors lg:min-h-8",
              active
                ? alert
                  ? "border-state-disputed bg-state-disputed text-white"
                  : "border-ink bg-ink text-on-ink"
                : alert
                  ? "border-rose-line bg-rose-soft text-rose-text hover:bg-rose-soft/80"
                  : "border-transparent text-ink-2 hover:border-line hover:bg-card hover:text-ink",
            )}
          >
            {segment.label}{" "}
            <span
              className={cx(
                "rounded-full px-1.5 font-mono text-[10px] font-bold",
                active
                  ? "bg-on-ink/20"
                  : alert
                    ? "bg-state-disputed text-white"
                    : "text-ink-3",
              )}
            >
              {segment.count}
            </span>
          </button>
        );
      })}
    </div>
  );
}
