/**
 * One number the arbiter glances at: a mono label, the figure, and a line of
 * context. The rose variant is for the count that must be zero.
 */

import type { ReactNode } from "react";

import { cx } from "./ui";

export function Metric({
  label,
  value,
  unit,
  caption,
  badge,
  tone = "neutral",
  children,
}: {
  label: string;
  value: ReactNode;
  unit?: ReactNode;
  caption?: ReactNode;
  /** Top-right: a percentage, a chip, a pulsing dot. */
  badge?: ReactNode;
  tone?: "neutral" | "danger";
  children?: ReactNode;
}) {
  const danger = tone === "danger";
  return (
    <section
      className={cx(
        "flex flex-col justify-between gap-3 rounded-lg border p-4 sm:p-5",
        danger ? "border-rose-line bg-rose-soft/70" : "border-line bg-card",
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <h2 className={cx("text-label-sm", danger ? "text-rose-text" : "text-ink-2")}>{label}</h2>
        {badge}
      </div>
      <div>
        <div className="flex items-baseline gap-2">
          <span
            className={cx(
              "font-mono text-2xl font-bold tracking-tight",
              danger ? "text-rose-text" : "text-ink",
            )}
          >
            {value}
          </span>
          {unit && (
            <span className={cx("text-body-sm", danger ? "font-semibold text-rose-text" : "text-ink-2")}>
              {unit}
            </span>
          )}
        </div>
        {caption && (
          <p className={cx("mt-1 text-body-sm", danger ? "text-rose-text" : "text-ink-2")}>{caption}</p>
        )}
        {children}
      </div>
    </section>
  );
}
