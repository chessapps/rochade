/**
 * The watched players of this tournament, as a strip of links at the top of
 * its page, each with their latest result. Empty means nothing is rendered:
 * the strip earns its place only once somebody pressed Watch.
 */

import { Link } from "react-router";

import type { Section } from "../api";
import { usePlayer } from "../queries";
import { useWatchList, type Watched } from "../watch";
import { Star } from "./icons";
import { playerPath } from "./PlayerName";
import { Result } from "./Result";
import { Card } from "./ui";

export function WatchStrip({ slug, sections }: { slug: string; sections: Section[] }) {
  const watched = useWatchList().filter((w) => w.slug === slug);
  if (watched.length === 0) return null;
  return (
    <Card as="div" className="flex flex-wrap items-center gap-2 px-3 py-2 sm:px-4">
      <span className="flex items-center gap-1 text-label-sm text-ink-3 [&>svg]:size-3.5">
        <Star />
        Watching
      </span>
      {watched.map((w) => (
        <WatchedPlayer
          key={`${w.sectionId}:${w.startRank}`}
          entry={w}
          section={sections.find((s) => s.id === w.sectionId)}
          showSection={sections.length > 1}
        />
      ))}
    </Card>
  );
}

function WatchedPlayer({
  entry,
  section,
  showSection,
}: {
  entry: Watched;
  section: Section | undefined;
  showSection: boolean;
}) {
  const live = section?.rounds.some((r) => r.state === "open") ?? false;
  const player = usePlayer(entry.slug, entry.sectionId, entry.startRank, live);
  const latest = player.data?.games.at(-1);
  return (
    <Link
      to={playerPath(entry.slug, entry.sectionId, entry.startRank)}
      className="inline-flex items-center gap-2 rounded-md border border-line bg-subtle px-2.5 py-1 text-sm font-medium text-ink hover:border-line-strong hover:bg-card"
    >
      <span>
        {player.data?.name ?? entry.name}
        {showSection && section && <span className="ml-1 text-ink-3">{section.name}</span>}
      </span>
      {latest && (
        <span className="flex items-center gap-1 text-xs text-ink-3">
          R{latest.round_number}
          <Result result={latest.result} state={latest.state} className="text-xs" />
        </span>
      )}
    </Link>
  );
}
