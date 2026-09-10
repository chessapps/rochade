/**
 * A board number in its boxed frame, the way the hall finds a board: mono,
 * tabular, 32px square. The frame takes the board's colour when the board
 * needs a hand, so the column reads as a status strip on its own.
 */

import type { ReactNode } from "react";

import { cx } from "./ui";

export type BoardNumberTone = "neutral" | "claimed" | "disputed" | "dark" | "muted";

const TONE: Record<BoardNumberTone, string> = {
  neutral: "border-line bg-subtle text-ink",
  claimed: "border-amber-line bg-amber-soft text-amber-text",
  disputed: "border-state-disputed bg-state-disputed text-white",
  dark: "border-ink bg-ink text-on-ink",
  muted: "border-line bg-card text-ink-3",
};

export function BoardNumber({
  children,
  tone = "neutral",
  size = "md",
  className,
}: {
  children: ReactNode;
  tone?: BoardNumberTone;
  size?: "md" | "lg";
  className?: string;
}) {
  return (
    <span
      className={cx(
        "inline-flex shrink-0 items-center justify-center rounded border font-mono font-bold",
        size === "md" ? "size-8 text-xs" : "size-10 text-lg",
        TONE[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
