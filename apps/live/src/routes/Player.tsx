/**
 * One player: who they are, where they stand, and every game so far. The
 * Watch button keeps them one tap away on the tournament page.
 */

import { useParams } from "react-router";

import { ApiError, errorMessage, type Player as PlayerDto } from "../api";
import { Star } from "../components/icons";
import { PlayerName } from "../components/PlayerName";
import { Result } from "../components/Result";
import { BackLink, Banner, Card, Chip, EmptyState, Skeleton, cx } from "../components/ui";
import { points } from "../format";
import { usePlayer, useTournament } from "../queries";
import { toggleWatch, useWatchList } from "../watch";

export function Player() {
  const { slug = "", sectionId = "", startRank = "" } = useParams();
  const rank = Number(startRank) || 0;
  const tournament = useTournament(slug);
  const section = tournament.data?.sections.find((s) => s.id === sectionId);
  const live = section?.rounds.some((r) => r.state === "open") ?? false;
  const player = usePlayer(slug, sectionId, rank, live);
  const watching = useWatchList().some(
    (w) => w.slug === slug && w.sectionId === sectionId && w.startRank === rank,
  );

  const back = <BackLink to={`/${slug}${tournament.data && tournament.data.sections.length > 1 ? `?s=${sectionId}` : ""}`}>{tournament.data?.name ?? "Tournament"}</BackLink>;

  if (player.isPending) return <Skeleton rows={6} />;
  if (player.isError) {
    const gone = player.error instanceof ApiError && player.error.status === 404;
    return (
      <div className="flex flex-col gap-4">
        {back}
        {gone ? (
          <EmptyState title="No longer in this section">
            The player list changed since this link was made. Find the player again on the
            tournament page.
          </EmptyState>
        ) : (
          <Banner tone="error">Could not load the player: {errorMessage(player.error)}</Banner>
        )}
      </div>
    );
  }

  const p = player.data;
  const watch = () => toggleWatch({ slug, sectionId, startRank: rank, name: p.name });

  return (
    <div className="flex flex-col gap-5">
      {back}
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1.5">
          <div className="flex flex-wrap items-center gap-2">
            {p.title && <Chip tone="neutral">{p.title}</Chip>}
            {p.federation && <Chip tone="neutral">{p.federation}</Chip>}
            {tournament.data && tournament.data.sections.length > 1 && (
              <Chip tone="neutral">Section {p.section_name}</Chip>
            )}
            {p.withdrawn_from_round != null && (
              <Chip tone="amber">withdrawn from round {p.withdrawn_from_round}</Chip>
            )}
          </div>
          <h1 className="text-headline-lg">{p.name}</h1>
          <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-body-sm text-ink-2">
            <span>
              No. <span className="font-mono">{p.start_rank}</span>
            </span>
            {p.rating != null && (
              <span>
                Rating <span className="font-mono">{p.rating}</span>
              </span>
            )}
          </p>
        </div>
        <button
          type="button"
          onClick={watch}
          aria-pressed={watching}
          className={cx(
            "inline-flex min-h-10 items-center gap-1.5 rounded border px-3 text-sm font-semibold transition-colors [&>svg]:size-4",
            watching
              ? "border-amber-line bg-amber-soft text-amber-text"
              : "border-line bg-card text-ink hover:border-line-strong hover:bg-subtle",
          )}
        >
          <Star className={watching ? "fill-current" : undefined} />
          {watching ? "Watching" : "Watch"}
        </button>
      </header>

      <Standing player={p} />

      <Card>
        <header className="border-b border-line px-4 py-3 sm:px-5">
          <h2 className="text-headline-sm">Games</h2>
        </header>
        {p.games.length === 0 ? (
          <p className="p-4 text-body-sm text-ink-2">No games yet.</p>
        ) : (
          <ol className="divide-y divide-line">
            {p.games.map((game) => (
              <li
                key={game.round_number}
                className="grid grid-cols-[3rem_1.25rem_1fr_auto] items-center gap-x-3 px-3 py-2 sm:grid-cols-[4rem_1.25rem_1fr_5rem_4rem] sm:px-5"
              >
                <span className="font-mono text-sm text-ink-3">R{game.round_number}</span>
                {game.colour ? (
                  <span className="flex items-center">
                    <span
                      aria-hidden
                      className={cx(
                        "size-3 rounded-full border",
                        game.colour === "white"
                          ? "border-disc-white-stroke bg-disc-white"
                          : "border-disc-black-stroke bg-disc-black",
                      )}
                    />
                    <span className="sr-only">{game.colour}</span>
                  </span>
                ) : (
                  <span aria-hidden />
                )}
                {game.opponent ? (
                  <PlayerName slug={slug} sectionId={sectionId} side={game.opponent} rating />
                ) : (
                  <span className="text-body-sm text-ink-2">bye</span>
                )}
                <Result result={game.result} state={game.state} className="justify-self-end sm:justify-self-center" />
                <span className="hidden text-right font-mono text-sm font-semibold text-ink-2 sm:block">
                  {game.score == null ? "" : points(game.score)}
                </span>
              </li>
            ))}
          </ol>
        )}
      </Card>
    </div>
  );
}

function Standing({ player }: { player: PlayerDto }) {
  if (player.rank == null || player.points == null) return null;
  const names = player.tiebreak_names.filter((n) => n !== "PTS");
  return (
    <Card as="div" className="flex flex-wrap items-baseline gap-x-6 gap-y-2 px-4 py-3 sm:px-5">
      <span className="flex items-baseline gap-2">
        <span className="text-label-sm text-ink-3">Rank</span>
        <span className="font-mono text-2xl font-semibold">{player.rank}</span>
      </span>
      <span className="flex items-baseline gap-2">
        <span className="text-label-sm text-ink-3">Points</span>
        <span className="font-mono text-2xl font-semibold">{points(player.points)}</span>
      </span>
      {player.tiebreaks.map((value, i) => (
        <span key={i} className="flex items-baseline gap-2">
          <span className="text-label-sm text-ink-3">{names[i] ?? `TB${i + 1}`}</span>
          <span className="font-mono text-lg text-ink-2">{value ?? ""}</span>
        </span>
      ))}
      {Boolean(player.standings_after_round) && (
        <span className="ml-auto text-body-sm text-ink-3">after round {player.standings_after_round}</span>
      )}
    </Card>
  );
}
