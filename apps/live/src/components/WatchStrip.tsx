/**
 * The watched players of this tournament, as a strip of links at the top of
 * its page. Empty means nothing is rendered: the strip earns its place only
 * once somebody pressed Watch.
 */

import type { Section } from "../api";
import { useWatchList } from "../watch";
import { Star } from "./icons";
import { playerPath } from "./PlayerName";
import { Card } from "./ui";
import { Link } from "react-router";

export function WatchStrip({ slug, sections }: { slug: string; sections: Section[] }) {
  const watched = useWatchList().filter((w) => w.slug === slug);
  if (watched.length === 0) return null;
  const nameOf = (sectionId: string) => sections.find((s) => s.id === sectionId)?.name;
  return (
    <Card as="div" className="flex flex-wrap items-center gap-2 px-3 py-2 sm:px-4">
      <span className="flex items-center gap-1 text-label-sm text-ink-3 [&>svg]:size-3.5">
        <Star />
        Watching
      </span>
      {watched.map((w) => (
        <Link
          key={`${w.sectionId}:${w.startRank}`}
          to={playerPath(slug, w.sectionId, w.startRank)}
          className="rounded-md border border-line bg-subtle px-2.5 py-1 text-sm font-medium text-ink hover:border-line-strong hover:bg-card"
        >
          {w.name}
          {sections.length > 1 && nameOf(w.sectionId) && (
            <span className="ml-1 text-ink-3">{nameOf(w.sectionId)}</span>
          )}
        </Link>
      ))}
    </Card>
  );
}
