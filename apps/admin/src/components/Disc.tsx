/**
 * The colour a player has, as a 14px disc: white with a slate hairline, black
 * with a lighter one. The only chess pictogram the design allows.
 */

import { cx } from "./ui";

export function Disc({ side, className }: { side: "white" | "black"; className?: string }) {
  return (
    <span
      aria-hidden
      className={cx(
        "inline-block size-3.5 shrink-0 rounded-full border",
        side === "white"
          ? "border-disc-white-stroke bg-disc-white"
          : "border-disc-black-stroke bg-disc-black",
        className,
      )}
    />
  );
}
