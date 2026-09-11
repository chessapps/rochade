/**
 * One tournament. Section tabs when there is more than one; within a
 * section, pairings (any round), standings, and the player list. The choice
 * lives in the URL: ?s=<section>&v=pairings|standings|players&r=<round>.
 */

import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router";

import { ApiError, errorMessage, type Round as RoundDto, type Section } from "../api";
import { Calendar, ChevronLeft, ChevronRight, MapPin, Users } from "../components/icons";
import { PlayerName } from "../components/PlayerName";
import { Result } from "../components/Result";
import { Banner, Card, Chip, EmptyState, Skeleton, Tabs, cx } from "../components/ui";
import { WatchStrip } from "../components/WatchStrip";
import { dateRange, plural, points, relativeTime } from "../format";
import { useRound, useStandings, useTournament } from "../queries";

type View = "pairings" | "standings" | "players";
const VIEWS: View[] = ["pairings", "standings", "players"];

export function Tournament() {
  const { slug = "" } = useParams();
  const [params] = useSearchParams();
  const tournament = useTournament(slug, true);

  if (tournament.isPending) return <Skeleton rows={6} />;
  if (tournament.isError) {
    return tournament.error instanceof ApiError && tournament.error.status === 404 ? (
      <EmptyState title="No such tournament">
        It may not be published yet, or the link is out of date.
      </EmptyState>
    ) : (
      <Banner tone="error">Could not load the tournament: {errorMessage(tournament.error)}</Banner>
    );
  }

  const detail = tournament.data;
  const sections = detail.sections;
  const section = sections.find((s) => s.id === params.get("s")) ?? sections[0];
  const view = (VIEWS as string[]).includes(params.get("v") ?? "") ? (params.get("v") as View) : "pairings";
  const when = dateRange(detail.start_date, detail.end_date);
  const inPlay = sections.some((s) => s.rounds.some((r) => r.state === "open"));

  const href = (next: { s?: string; v?: View; r?: number }) => {
    const q = new URLSearchParams();
    const s = next.s ?? section?.id;
    const v = next.v ?? view;
    if (s && sections.length > 1) q.set("s", s);
    if (v !== "pairings") q.set("v", v);
    if (next.r) q.set("r", String(next.r));
    const text = q.toString();
    return `/${slug}${text ? `?${text}` : ""}`;
  };

  return (
    <div className="flex flex-col gap-5">
      <header className="flex flex-col gap-1.5">
        <div className="flex flex-wrap items-center gap-2">
          {detail.federation && <Chip tone="neutral">{detail.federation}</Chip>}
          {inPlay && (
            <Chip tone="blue">
              <span aria-hidden className="size-1.5 animate-pulse rounded-full bg-round-open" />
              in play
            </Chip>
          )}
        </div>
        <h1 className="text-headline-lg">{detail.name}</h1>
        <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-body-sm text-ink-2 [&_svg]:size-3.5 [&_svg]:text-ink-3">
          {detail.city && (
            <span className="flex items-center gap-1">
              <MapPin />
              {detail.city}
            </span>
          )}
          {when && (
            <span className="flex items-center gap-1">
              <Calendar />
              {when}
            </span>
          )}
          {section && (
            <span className="flex items-center gap-1">
              <Users />
              {plural(section.players, "player")}
            </span>
          )}
        </p>
      </header>

      <WatchStrip slug={slug} sections={sections} />

      {sections.length > 1 && (
        <Tabs
          ariaLabel="Section"
          items={sections.map((s) => ({ to: href({ s: s.id }), label: `Section ${s.name}` }))}
        />
      )}

      {!section ? (
        <EmptyState title="No sections yet">The arbiter has not imported a round yet.</EmptyState>
      ) : (
        <>
          <Tabs
            ariaLabel="View"
            items={[
              { to: href({ v: "pairings" }), label: "Pairings" },
              { to: href({ v: "standings" }), label: "Standings" },
              { to: href({ v: "players" }), label: "Players" },
            ]}
          />
          {view === "pairings" && (
            <Pairings slug={slug} section={section} wanted={Number(params.get("r")) || 0} href={href} />
          )}
          {view === "standings" && <Standings slug={slug} section={section} />}
          {view === "players" && <Players slug={slug} section={section} />}
        </>
      )}
    </div>
  );
}

function Pairings({
  slug,
  section,
  wanted,
  href,
}: {
  slug: string;
  section: Section;
  wanted: number;
  href: (next: { r?: number }) => string;
}) {
  const rounds = section.rounds;
  const newest = rounds.at(-1)?.number ?? 0;
  const number = rounds.some((r) => r.number === wanted) ? wanted : newest;
  const summary = rounds.find((r) => r.number === number);
  const live = summary?.state === "open";
  const round = useRound(slug, section.id, number, live);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 10_000);
    return () => clearInterval(timer);
  }, []);

  if (rounds.length === 0) {
    return <EmptyState title="Not paired yet">Round 1 appears here once the arbiter imports it.</EmptyState>;
  }

  return (
    <Card>
      <header className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-b border-line px-4 py-3 sm:px-5">
        <div className="flex items-center gap-2">
          <RoundStep to={href({ r: number - 1 })} disabled={number <= 1} label="Previous round">
            <ChevronLeft />
          </RoundStep>
          <h2 className="text-headline-sm">
            Round {number}
            {section.declared_rounds ? <span className="text-ink-3"> / {section.declared_rounds}</span> : null}
          </h2>
          <RoundStep to={href({ r: number + 1 })} disabled={number >= newest} label="Next round">
            <ChevronRight />
          </RoundStep>
        </div>
        {summary && (
          <p className="flex items-center gap-2 text-body-sm text-ink-2">
            {summary.state === "open" ? (
              <>
                <Chip tone="blue">
                  <span aria-hidden className="size-1.5 animate-pulse rounded-full bg-round-open" />
                  in play
                </Chip>
                <span>
                  {summary.results_in} of {plural(summary.boards, "result")} in
                </span>
              </>
            ) : (
              <Chip tone="emerald">confirmed</Chip>
            )}
            {summary.updated_at && summary.results_in > 0 && (
              <span className="text-ink-3">· updated {relativeTime(summary.updated_at, now)}</span>
            )}
          </p>
        )}
      </header>
      {round.isPending && <Skeleton rows={6} />}
      {round.isError && (
        <Banner tone="error" className="m-4">
          Could not load the round: {errorMessage(round.error)}
        </Banner>
      )}
      {round.data && <Boards slug={slug} round={round.data} />}
    </Card>
  );
}

function RoundStep({
  to,
  disabled,
  label,
  children,
}: {
  to: string;
  disabled: boolean;
  label: string;
  children: React.ReactNode;
}) {
  const base = "flex size-8 items-center justify-center rounded-md border [&>svg]:size-4";
  if (disabled) {
    return (
      <span aria-hidden className={cx(base, "border-transparent text-ink-3/50")}>
        {children}
      </span>
    );
  }
  return (
    <Link to={to} aria-label={label} className={cx(base, "border-line text-ink-2 hover:bg-subtle hover:text-ink")}>
      {children}
    </Link>
  );
}

function Boards({ slug, round }: { slug: string; round: RoundDto }) {
  if (round.boards.length === 0) {
    return <p className="p-4 text-body-sm text-ink-2">No boards in this round.</p>;
  }
  // On a phone the two players stack, with the result beside them; from sm
  // up the row reads white · result · black, the way a pairing list prints.
  return (
    <ol className="divide-y divide-line">
      {round.boards.map((board) => (
        <li
          key={board.board}
          className="grid grid-cols-[2rem_1fr_3.5rem] items-center gap-x-2 px-3 py-2 sm:grid-cols-[3rem_1fr_5rem_1fr] sm:px-5"
        >
          <span className="row-span-2 font-mono text-sm font-semibold text-ink-3 sm:row-span-1">
            {board.board}
          </span>
          <span className="flex min-w-0 items-center gap-2">
            <span aria-hidden className="size-3 shrink-0 rounded-full border border-disc-white-stroke bg-disc-white" />
            <PlayerName slug={slug} sectionId={round.section_id} side={board.white} rating />
          </span>
          <Result
            result={board.result}
            state={board.state}
            className="row-span-2 justify-self-center sm:row-span-1"
          />
          {board.black ? (
            <span className="col-start-2 flex min-w-0 items-center gap-2 sm:col-start-4 sm:flex-row-reverse sm:text-right">
              <span aria-hidden className="size-3 shrink-0 rounded-full border border-disc-black-stroke bg-disc-black" />
              <PlayerName slug={slug} sectionId={round.section_id} side={board.black} rating />
            </span>
          ) : (
            <span className="col-start-2 text-body-sm text-ink-3 sm:col-start-4 sm:text-right">bye</span>
          )}
        </li>
      ))}
    </ol>
  );
}

function Standings({ slug, section }: { slug: string; section: Section }) {
  const live = section.rounds.some((r) => r.state === "open");
  const standings = useStandings(slug, section.id, live);
  if (standings.isPending) return <Skeleton rows={8} />;
  if (standings.isError) {
    return <Banner tone="error">Could not load the standings: {errorMessage(standings.error)}</Banner>;
  }
  const table = standings.data;
  if (table.rows.length === 0) {
    return (
      <EmptyState title="No standings yet">
        They appear once the arbiter brings them over from the pairing program.
      </EmptyState>
    );
  }
  const columns = Math.max(table.tiebreak_columns, table.tiebreak_names.length);
  const names = Array.from({ length: columns }, (_, i) => table.tiebreak_names[i] || `TB${i + 1}`);
  return (
    <Card>
      <header className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-b border-line px-4 py-3 sm:px-5">
        <h2 className="text-headline-sm">Standings</h2>
        <p className="text-body-sm text-ink-2">
          {table.after_round === 0 ? "starting order" : `after round ${table.after_round}`}
          {table.rounds_held > table.after_round && (
            <span className="text-ink-3"> · round {table.rounds_held} in play</span>
          )}
        </p>
      </header>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line bg-subtle/90 text-left text-label-sm text-ink-2">
              <th className="w-10 px-3 py-2 text-right sm:px-4">#</th>
              <th className="px-2 py-2">Name</th>
              <th className="hidden px-2 py-2 sm:table-cell">Fed</th>
              <th className="hidden px-2 py-2 text-right sm:table-cell">Rating</th>
              <th className="px-2 py-2 text-right">Pts</th>
              {names.map((name) => (
                <th key={name} className="px-2 py-2 text-right whitespace-nowrap">
                  {name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {table.rows.map((row) => (
              <tr key={row.start_rank} className="border-b border-line hover:bg-subtle/60">
                <td className="px-3 py-1.5 text-right font-mono font-semibold text-ink-2 sm:px-4">{row.rank}</td>
                <td className="px-2 py-1.5">
                  <PlayerName
                    slug={slug}
                    sectionId={section.id}
                    side={{ start_rank: row.start_rank, name: row.name, title: row.title, rating: row.rating, federation: row.federation }}
                  />
                </td>
                <td className="hidden px-2 py-1.5 text-ink-2 sm:table-cell">{row.federation}</td>
                <td className="hidden px-2 py-1.5 text-right font-mono text-ink-2 sm:table-cell">{row.rating ?? ""}</td>
                <td className="px-2 py-1.5 text-right font-mono font-semibold">{points(row.points)}</td>
                {names.map((name, i) => (
                  <td key={name} className="px-2 py-1.5 text-right font-mono text-ink-2">
                    {row.tiebreaks[i] ?? ""}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function Players({ slug, section }: { slug: string; section: Section }) {
  // The standings row carries every player once standings exist; before
  // that, the newest round's boards name them. Either way, one list.
  const live = section.rounds.some((r) => r.state === "open");
  const standings = useStandings(slug, section.id, false);
  const newest = section.rounds.at(-1)?.number ?? 0;
  const round = useRound(slug, section.id, newest, live);
  if (standings.isPending || (newest > 0 && round.isPending)) return <Skeleton rows={8} />;

  const fromStandings = standings.data?.rows.map((row) => ({
    start_rank: row.start_rank,
    name: row.name,
    title: row.title,
    rating: row.rating,
    federation: row.federation,
  }));
  const fromBoards = round.data?.boards.flatMap((b) => (b.black ? [b.white, b.black] : [b.white]));
  const players = (fromStandings?.length ? fromStandings : (fromBoards ?? [])).slice().sort((a, b) => a.start_rank - b.start_rank);

  if (players.length === 0) {
    return <EmptyState title="No players yet">The list appears with the first round.</EmptyState>;
  }
  return (
    <Card>
      <ol className="divide-y divide-line">
        {players.map((side) => (
          <li key={side.start_rank} className="flex items-center gap-3 px-3 py-2 sm:px-5">
            <span className="w-8 text-right font-mono text-sm text-ink-3">{side.start_rank}</span>
            <PlayerName slug={slug} sectionId={section.id} side={side} className="flex-1" />
            <span className="text-body-sm text-ink-2">{side.federation}</span>
            <span className="w-12 text-right font-mono text-sm text-ink-2">{side.rating ?? ""}</span>
          </li>
        ))}
      </ol>
    </Card>
  );
}

