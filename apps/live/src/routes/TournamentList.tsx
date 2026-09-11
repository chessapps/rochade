/** The front door: every published tournament, the current ones first. */

import { Link } from "react-router";

import { errorMessage, type TournamentSummary } from "../api";
import { Calendar, MapPin } from "../components/icons";
import { Banner, Chip, EmptyState, Skeleton } from "../components/ui";
import { dateRange, joinNonEmpty } from "../format";
import { useTournaments } from "../queries";

export function TournamentList() {
  const tournaments = useTournaments();

  if (tournaments.isPending) return <Skeleton rows={3} />;
  if (tournaments.isError) {
    return <Banner tone="error">Could not load the tournaments: {errorMessage(tournaments.error)}</Banner>;
  }

  const list = tournaments.data;
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <h1 className="text-headline-md">Tournaments</h1>
        <p className="max-w-2xl text-body-sm text-ink-2">
          Pairings, results as they come in, standings, and every game of a player. Results are
          preliminary until the arbiter confirms them.
        </p>
      </div>

      {list.length === 0 ? (
        <EmptyState title="Nothing published yet">
          A tournament appears here once its arbiter publishes it.
        </EmptyState>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {list.map((tournament) => (
            <li key={tournament.slug}>
              <TournamentCard tournament={tournament} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function TournamentCard({ tournament }: { tournament: TournamentSummary }) {
  const when = dateRange(tournament.start_date, tournament.end_date);
  const inPlay = tournament.sections.some((section) => section.in_play);
  return (
    <Link
      to={`/${tournament.slug}`}
      className="flex h-full flex-col gap-3 rounded-lg border border-line bg-card p-4 transition-colors hover:border-line-strong hover:bg-subtle/40"
    >
      <div className="flex items-start justify-between gap-2">
        <p className="text-headline-sm">{tournament.name}</p>
        {inPlay && (
          <Chip tone="blue">
            <span aria-hidden className="size-1.5 animate-pulse rounded-full bg-round-open" />
            in play
          </Chip>
        )}
      </div>
      <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-body-sm text-ink-2 [&_svg]:size-3.5 [&_svg]:text-ink-3">
        {tournament.city && (
          <span className="flex items-center gap-1">
            <MapPin />
            {tournament.city}
          </span>
        )}
        {when && (
          <span className="flex items-center gap-1">
            <Calendar />
            {when}
          </span>
        )}
      </p>
      <p className="mt-auto text-label-sm text-ink-3">
        {joinNonEmpty(
          tournament.sections.map((section) =>
            section.rounds_held === 0
              ? `${section.name}: not paired yet`
              : `${section.name}: round ${section.rounds_held}${section.declared_rounds ? ` of ${section.declared_rounds}` : ""}`,
          ),
        )}
      </p>
    </Link>
  );
}
