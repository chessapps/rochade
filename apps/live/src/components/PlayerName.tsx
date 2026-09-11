/**
 * A player's name, always a link to their page. Title before the name in a
 * small mono chip, the way pairing lists print it.
 */

import { Link } from "react-router";

import type { Side } from "../api";
import { cx } from "./ui";

export function playerPath(slug: string, sectionId: string, startRank: number): string {
  return `/${slug}/s/${sectionId}/p/${startRank}`;
}

export function PlayerName({
  slug,
  sectionId,
  side,
  className,
  rating = false,
}: {
  slug: string;
  sectionId: string;
  side: Side;
  className?: string;
  /** Show the rating after the name, dimmed. */
  rating?: boolean;
}) {
  return (
    <Link
      to={playerPath(slug, sectionId, side.start_rank)}
      className={cx("inline-flex min-w-0 items-baseline gap-1.5 hover:underline", className)}
    >
      {side.title && (
        <span className="shrink-0 rounded-sm bg-subtle px-1 font-mono text-[11px] font-semibold text-ink-2">
          {side.title}
        </span>
      )}
      <span className="truncate font-medium text-ink">{side.name}</span>
      {rating && side.rating != null && (
        <span className="hidden shrink-0 font-mono text-xs text-ink-3 sm:inline">{side.rating}</span>
      )}
    </Link>
  );
}
