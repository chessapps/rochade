/**
 * The tournament at a glance, the way the desk mockup lays it out: what the
 * tournament is, three numbers that matter now, one card per section with
 * its round's position and the one thing to do next, and beside them the
 * hall's live feed and the drop zone for the next round file.
 *
 * Everything here is fed by the API as it is: no clocks, no kiosks, no
 * countdowns. A widget without a data source is not on this page.
 */

import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";

import { errorMessage, type RoundSummary, type SectionSummary } from "../api";
import { countsOfRound, currentRound, nextAction, readyToRelease, type NextAction } from "../boards";
import { BoardNumber } from "../components/BoardNumber";
import { DeleteTournamentDialog } from "../components/DeleteTournamentDialog";
import { DropZone } from "../components/DropZone";
import {
  ArrowRight,
  Calendar,
  ChevronRight,
  Download,
  MapPin,
  Plus,
  QrCode,
  RefreshCw,
  Trash2,
  TriangleAlert,
  Upload,
  Users,
} from "../components/icons";
import { Metric } from "../components/Metric";
import { PairDialog } from "../components/PairDialog";
import { ProgressBar } from "../components/ProgressBar";
import { download, ExportDialog, ReleaseDialog } from "../components/RoundDialogs";
import { RoundStepper } from "../components/RoundStepper";
import { Chip, RoundChip } from "../components/StateChip";
import { Banner, Button, Card, EmptyState, Skeleton, cx } from "../components/ui";
import { clockTime, dateRange, joinNonEmpty, plural, relativeTime, resultLabel } from "../format";
import { readText, sniff, type PickedFile } from "../importFiles";
import {
  useDevices,
  useExportFile,
  useLiveFeed,
  useTournament,
  useTournaments,
  type FeedEvent,
} from "../queries";
import { useNow } from "../useNow";

export function TournamentHome() {
  const { tournamentId = "" } = useParams();
  const tournament = useTournament(tournamentId, true);
  const devices = useDevices(tournamentId);
  // The list is where the account's role on this tournament lives; only an
  // owner gets to see the delete button at all.
  const tournaments = useTournaments();
  const [deleting, setDeleting] = useState(false);
  // Once a minute, so "last entry 4 min ago" stays true between fetches.
  const now = useNow(60_000);

  const sections = tournament.data?.sections ?? [];
  const current = useMemo(
    () =>
      sections
        .map((section) => ({ section, round: currentRound(section) }))
        .filter((pair): pair is { section: SectionSummary; round: RoundSummary } => pair.round !== null),
    [sections],
  );
  const feed = useLiveFeed(current.map((pair) => pair.round));

  if (tournament.isPending) return <Skeleton rows={4} />;
  if (tournament.isError) {
    return <Banner tone="error">Could not load the tournament: {errorMessage(tournament.error)}</Banner>;
  }

  const detail = tournament.data;
  const owner = tournaments.data?.some((t) => t.id === tournamentId && t.role === "owner") ?? false;
  const rounds = current.map((pair) => pair.round);
  const boards = rounds.reduce((n, r) => n + r.boards, 0);
  const entered = rounds.reduce((n, r) => n + r.claimed + r.confirmed, 0);
  const disputed = rounds.reduce((n, r) => n + r.disputed, 0);
  const firstDispute = current.find((pair) => pair.round.disputed > 0);
  const players = sections.reduce((n, s) => n + s.players, 0);
  const active = (devices.data ?? []).filter((d) => d.active);
  const lastSeen = (devices.data ?? [])
    .map((d) => d.last_seen_at)
    .filter((t): t is string => Boolean(t))
    .sort()
    .at(-1);
  const percent = boards > 0 ? Math.round((entered / boards) * 1000) / 10 : 0;
  const sectionOf = new Map(current.map((pair) => [pair.round.id, pair.section]));
  const lastEntry = new Map<string, string>();
  for (const event of feed.events) {
    const roundId = current.find((pair) => pair.round.id === event.round_id)?.round.id;
    if (roundId && !lastEntry.has(roundId)) lastEntry.set(roundId, event.at);
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Command bar */}
      <Card className="flex flex-col justify-between gap-5 p-4 sm:p-6 lg:flex-row lg:items-center">
        <div className="flex flex-col gap-1.5">
          <div className="flex flex-wrap items-center gap-2">
            {detail.federation && <Chip tone="neutral">{detail.federation}</Chip>}
            <Chip tone="emerald">
              <RefreshCw />
              {detail.manager_label}
            </Chip>
          </div>
          <h1 className="text-headline-lg">{detail.name}</h1>
          <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-body-sm text-ink-2 [&_svg]:size-3.5 [&_svg]:text-ink-3">
            {detail.city && (
              <span className="flex items-center gap-1 font-medium">
                <MapPin />
                {detail.city}
              </span>
            )}
            {dateRange(detail.start_date, detail.end_date) && (
              <span className="flex items-center gap-1 font-medium">
                <Calendar />
                {dateRange(detail.start_date, detail.end_date)}
              </span>
            )}
            {players > 0 && (
              <span className="flex items-center gap-1 font-mono font-semibold text-ink">
                <Users />
                {plural(players, "player")}
                {boards > 0 && ` (${plural(boards, "board")} this round)`}
              </span>
            )}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" to={`/t/${tournamentId}/devices`} icon={<QrCode />}>
            Hall QR posters
          </Button>
          <Button size="sm" to={`/t/${tournamentId}/players`} icon={<Users />}>
            Players
          </Button>
          {detail.native ? (
            <Button size="sm" tone="dark" to={`/t/${tournamentId}/sections/new`} icon={<Plus />}>
              New section…
            </Button>
          ) : (
            <Button size="sm" tone="dark" to={`/t/${tournamentId}/import`} icon={<Upload />}>
              Import a round…
            </Button>
          )}
          {owner && (
            <Button
              size="sm"
              tone="ghost"
              onClick={() => setDeleting(true)}
              icon={<Trash2 />}
              className="text-ink-3 hover:text-rose-text"
              title="Delete this tournament"
            >
              Delete…
            </Button>
          )}
        </div>
      </Card>
      {owner && (
        <DeleteTournamentDialog
          open={deleting}
          onClose={() => setDeleting(false)}
          tournament={{ id: detail.id, name: detail.name }}
        />
      )}

      {/* Metrics */}
      {sections.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Metric
            label="Results this round"
            value={entered}
            unit={`/ ${plural(boards, "board")}`}
            badge={
              <span className="rounded-full border border-emerald-line bg-emerald-soft px-2 py-0.5 font-mono text-[11px] font-bold text-emerald-text">
                {percent}%
              </span>
            }
          >
            <ProgressBar
              counts={{
                boards,
                byes: 0,
                empty: rounds.reduce((n, r) => n + r.empty, 0),
                claimed: rounds.reduce((n, r) => n + r.claimed, 0),
                disputed,
                confirmed: rounds.reduce((n, r) => n + r.confirmed, 0),
              }}
              size="sm"
              caption={false}
              className="mt-3"
            />
          </Metric>
          <Metric
            label="Active disputes"
            tone={disputed > 0 ? "danger" : "neutral"}
            value={disputed}
            unit={firstDispute ? `Section ${firstDispute.section.name}` : undefined}
            badge={
              disputed > 0 ? (
                <span aria-hidden className="relative flex size-2">
                  <span className="absolute inline-flex size-full animate-ping rounded-full bg-state-disputed opacity-75" />
                  <span className="relative inline-flex size-2 rounded-full bg-state-disputed" />
                </span>
              ) : undefined
            }
            caption={
              firstDispute ? (
                <Link
                  to={`/t/${tournamentId}/rounds/${firstDispute.round.id}?filter=attention`}
                  className="inline-flex items-center gap-1 font-semibold hover:underline [&>svg]:size-3.5"
                >
                  <TriangleAlert />
                  Two phones disagree · resolve at the desk
                </Link>
              ) : (
                "Every entered board agrees."
              )
            }
          />
          <Metric
            label="Phones admitted"
            value={active.length}
            unit={active.length === 1 ? "phone" : "phones"}
            caption={lastSeen ? `Last entry ${relativeTime(lastSeen, now)}` : "No entries yet"}
            badge={
              <Link
                to={`/t/${tournamentId}/devices`}
                className="text-label-sm text-ink-3 hover:text-ink"
              >
                Manage
              </Link>
            }
          />
        </div>
      )}

      {sections.length === 0 ? (
        detail.native ? (
          <EmptyState
            title="No sections yet"
            action={
              <Button tone="primary" to={`/t/${tournamentId}/sections/new`} icon={<Plus />}>
                Open the first section
              </Button>
            }
          >
            A section is one field paired on its own: an Open, a U12, a B group. Open one, enter
            its players, and pair round 1 from here.
          </EmptyState>
        ) : (
          <EmptyState
            title="No sections yet"
            action={
              <Button tone="primary" to={`/t/${tournamentId}/import`} icon={<Upload />}>
                Import the paired round
              </Button>
            }
          >
            Pair round 1 in your tournament manager, export it, and import the file here. Each
            file becomes a section; a tournament can hold several.
          </EmptyState>
        )
      ) : (
        <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-12">
          <div className="flex flex-col gap-6 lg:col-span-8">
            {sections.map((section, index) => {
              const round = currentRound(section);
              return (
                <SectionCard
                  key={section.id}
                  section={section}
                  tournamentId={tournamentId}
                  first={index === 0}
                  lastEntryAt={round ? lastEntry.get(round.id) : undefined}
                  now={now}
                />
              );
            })}
          </div>
          <div className="flex flex-col gap-6 lg:col-span-4">
            <LiveFeed
              events={feed.events}
              pending={feed.isPending && current.length > 0}
              sectionOf={sectionOf}
              tournamentId={tournamentId}
              now={now}
            />
            {!detail.native && (
              <RoundFileSync
                tournamentId={tournamentId}
                sections={sections}
                manager={detail.manager}
                managerLabel={detail.manager_label}
              />
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function SectionCard({
  section,
  tournamentId,
  first,
  lastEntryAt,
  now,
}: {
  section: SectionSummary;
  tournamentId: string;
  first: boolean;
  lastEntryAt: string | undefined;
  now: number;
}) {
  const navigate = useNavigate();
  const [dialog, setDialog] = useState<"release" | "export" | "pair" | null>(null);
  const round = currentRound(section);
  const action = nextAction(section);
  const native = section.native;
  const past = (section.rounds ?? [])
    .filter((r) => r.id !== round?.id)
    .sort((a, b) => b.number - a.number);
  const roundUrl = round ? `/t/${tournamentId}/rounds/${round.id}` : "";

  const go = () => {
    switch (action.kind) {
      case "import":
        return navigate(`/t/${tournamentId}/import?section=${encodeURIComponent(section.name)}`);
      case "fix":
        return navigate(`${roundUrl}?filter=attention`);
      case "release":
        return setDialog("release");
      case "export":
        return setDialog("export");
      case "players":
        return navigate(`/t/${tournamentId}/players?section=${encodeURIComponent(section.id)}`);
      case "pair":
        return setDialog("pair");
      case "finished":
        return navigate(`/t/${tournamentId}/standings`);
    }
  };

  const counts = round ? countsOfRound(round) : null;
  const unresolved = round ? round.empty + round.disputed : 0;
  const percent = round && round.boards > 0 ? Math.round((round.confirmed / round.boards) * 1000) / 10 : 0;

  return (
    <Card className="flex flex-col overflow-hidden">
      <header className="flex flex-col justify-between gap-4 border-b border-line p-4 sm:flex-row sm:items-center sm:p-6">
        <div className="flex items-center gap-3.5">
          <BoardNumber size="lg" tone={first ? "dark" : "neutral"}>
            {section.name}
          </BoardNumber>
          <div>
            <div className="flex flex-wrap items-center gap-2.5">
              <h2 className="text-headline-sm">Section {section.name}</h2>
              {section.manager_label && <Chip tone="blue">{section.manager_label}</Chip>}
            </div>
            <p className="mt-0.5 text-body-sm font-medium text-ink-2">
              {joinNonEmpty([
                plural(section.players, "player"),
                section.declared_rounds ? `${section.declared_rounds} rounds` : null,
                round ? plural(round.boards, "board") : null,
              ])}
            </p>
          </div>
        </div>
        {round && (
          <div className="flex items-center gap-2">
            <Link to={roundUrl} className="font-mono text-sm font-semibold hover:underline">
              Round {round.number}
            </Link>
            <RoundChip state={round.state} native={native} />
          </div>
        )}
      </header>

      {round && round.disputed > 0 && (
        <div className="mx-4 mt-4 flex flex-col justify-between gap-3 rounded-lg border border-rose-line bg-rose-soft p-3.5 text-xs sm:mx-6 sm:mt-6 sm:flex-row sm:items-center">
          <p className="flex items-center gap-2.5 font-medium text-rose-text [&>svg]:size-4 [&>svg]:shrink-0 [&>svg]:text-rose-text">
            <TriangleAlert />
            <span>
              <strong>{plural(round.disputed, "board")}:</strong> two phones disagree — desk review
              required
            </span>
          </p>
          <Button
            size="sm"
            to={`${roundUrl}?filter=attention`}
            className="shrink-0 border-rose-line text-rose-text hover:bg-rose-soft hover:text-rose-text"
          >
            Resolve
            <ArrowRight />
          </Button>
        </div>
      )}

      <div className="flex flex-1 flex-col gap-4 p-4 sm:p-6">
        {round && counts ? (
          <>
            <RoundStepper round={round} native={native} />
            <div className="flex flex-col gap-2 border-t border-line pt-4 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <p className="flex flex-wrap items-baseline gap-2">
                  <span className="font-mono text-xl font-bold text-ink">
                    {round.confirmed} of {round.boards}
                  </span>
                  <span className="text-sm font-medium text-ink-2">boards confirmed</span>
                  <span className="font-mono text-xs text-ink-3">({percent}%)</span>
                </p>
                <p className="text-body-sm text-ink-2">
                  {round.state === "exported"
                    ? native
                      ? `Closed ${clockTime(round.exported_at)}: round ${round.number + 1} is paired on it`
                      : `Exported ${clockTime(round.exported_at)} and frozen`
                    : joinNonEmpty([
                        unresolved > 0 ? `${plural(unresolved, "board")} unresolved` : "every board has a result",
                        round.disputed > 0 && `${plural(round.disputed, "dispute")} pending resolution`,
                      ])}
                </p>
              </div>
            </div>
            <ProgressBar counts={counts} legend caption={false} />
          </>
        ) : (
          <p className="text-body-sm text-ink-2">
            {native
              ? section.players < 2
                ? "Enter the players, then pair round 1."
                : `${plural(section.players, "player")} entered. Round 1 is ready to pair.`
              : "Nothing imported yet."}
          </p>
        )}

        <div className="mt-auto flex flex-col items-stretch justify-between gap-3 pt-2 sm:flex-row sm:items-center">
          <div className="flex flex-wrap items-center gap-2.5">
            <Button tone={toneOf(action)} size="lg" onClick={() => void go()}>
              {labelOf(action, section.manager_label)}
              {action.kind !== "export" && action.kind !== "finished" && <ArrowRight />}
            </Button>
            {round && action.kind !== "fix" && (
              <Button size="lg" to={roundUrl}>
                View boards
              </Button>
            )}
          </div>
          {round && (
            <span className="font-mono text-[11px] text-ink-3 sm:text-right">
              {lastEntryAt
                ? `Last entry ${relativeTime(lastEntryAt, now)}`
                : `${native ? "Paired" : "Imported"} ${clockTime(round.imported_at)}`}
            </span>
          )}
        </div>
      </div>

      {past.length > 0 && (
        <details className="group border-t border-line bg-subtle/70 px-4 py-3 sm:px-6">
          <summary className="flex cursor-pointer list-none items-center justify-between text-xs font-medium text-ink-2 select-none hover:text-ink [&::-webkit-details-marker]:hidden">
            <span className="flex items-center gap-2 [&>svg]:size-4 [&>svg]:text-ink-3 [&>svg]:transition-transform group-open:[&>svg]:rotate-90">
              <ChevronRight />
              <span className="font-semibold">
                Earlier rounds ({past.length}
                {section.declared_rounds ? ` of ${section.declared_rounds}` : ""})
              </span>
            </span>
          </summary>
          <div className="mt-3 flex flex-col gap-2 pb-2 pl-6 text-xs">
            {past.map((r) => (
              <EarlierRound key={r.id} round={r} tournamentId={tournamentId} native={native} />
            ))}
          </div>
        </details>
      )}

      {round && (
        <ReleaseDialog
          round={round}
          tournamentId={tournamentId}
          native={native}
          open={dialog === "release"}
          onClose={() => setDialog(null)}
        />
      )}
      {round && !native && (
        <ExportDialog
          round={round}
          tournamentId={tournamentId}
          managerLabel={section.manager_label}
          open={dialog === "export"}
          onClose={() => setDialog(null)}
        />
      )}
      {native && action.kind === "pair" && (
        <PairDialog
          section={section}
          tournamentId={tournamentId}
          roundNumber={action.round_number}
          open={dialog === "pair"}
          onClose={() => setDialog(null)}
        />
      )}
    </Card>
  );
}

function EarlierRound({
  round,
  tournamentId,
  native,
}: {
  round: RoundSummary;
  tournamentId: string;
  native: boolean;
}) {
  const [wanted, setWanted] = useState(false);
  const file = useExportFile(round.id, wanted && !native);
  useEffect(() => {
    if (wanted && file.data) {
      download(file.data);
      setWanted(false);
    }
  }, [wanted, file.data]);
  const exported = round.state === "exported";
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-line bg-card p-2.5">
      <div className="flex flex-wrap items-center gap-3">
        <Link to={`/t/${tournamentId}/rounds/${round.id}`} className="font-mono font-bold text-ink hover:underline">
          Round {round.number}
        </Link>
        <span className="text-ink-2">
          {round.confirmed}/{round.boards} boards confirmed
        </span>
        {exported ? (
          <Chip tone="emerald">
            {native ? "Closed" : "Exported"} {clockTime(round.exported_at)}
          </Chip>
        ) : (
          <RoundChip state={round.state} native={native} />
        )}
      </div>
      {exported && !native && (
        <button
          type="button"
          onClick={() => setWanted(true)}
          disabled={wanted && file.isPending}
          className="flex items-center gap-1 font-medium text-accent hover:text-accent-strong disabled:opacity-50 [&>svg]:size-3.5"
        >
          <Download />
          {readyToRelease(round) ? "Download the file" : "Download the file (blanks)"}
        </button>
      )}
    </div>
  );
}

const FEED_TONE: Record<string, string> = {
  round_imported: "bg-round-open",
  result_claimed: "bg-state-claimed",
  result_corrected: "bg-state-claimed",
  result_disputed: "bg-state-disputed",
  result_set: "bg-state-confirmed",
  result_confirmed: "bg-state-confirmed",
  dispute_resolved: "bg-state-confirmed",
};

function describe(event: FeedEvent): string {
  const p = event.payload as Record<string, unknown>;
  const claim = (key: string) =>
    ({ white_win: "1:0", draw: "½:½", black_win: "0:1" })[String(p[key])] ?? String(p[key] ?? "");
  const who = event.device_label ? `“${event.device_label}”` : "a phone";
  switch (event.action) {
    case "result_claimed":
      return `${claim("claimed")} entered by ${who}.`;
    case "result_corrected":
      return `Corrected to ${claim("claimed")} by ${who}.`;
    case "result_disputed":
      return `${who} says ${claim("claimed")}; the other phone disagrees. Desk review required.`;
    case "result_set":
      return `Set to ${resultLabel(String(p.white_result ?? " "), String(p.black_result ?? " "))} at the desk.`;
    case "result_confirmed":
      return "Confirmed at the desk.";
    case "dispute_resolved":
      return `Dispute resolved: ${claim("chosen")}.`;
    default:
      return `${String(event.action).replace(/_/g, " ")}${p.filename ? ` from ${String(p.filename)}` : ""}.`;
  }
}

function LiveFeed({
  events,
  pending,
  sectionOf,
  tournamentId,
  now,
}: {
  events: FeedEvent[];
  pending: boolean;
  sectionOf: Map<string, SectionSummary>;
  tournamentId: string;
  now: number;
}) {
  const shown = events.slice(0, 8);
  return (
    <Card className="flex flex-col gap-4 p-4 sm:p-6">
      <div className="flex items-center justify-between border-b border-line pb-3">
        <h2 className="flex items-center gap-2 text-sm font-bold">
          <span aria-hidden className="relative flex size-2">
            <span className="absolute inline-flex size-full animate-ping rounded-full bg-state-confirmed opacity-75" />
            <span className="relative inline-flex size-2 rounded-full bg-state-confirmed" />
          </span>
          Live hall feed
        </h2>
        <span className="font-mono text-[11px] text-ink-3">Auto-refresh 10s</span>
      </div>
      {pending ? (
        <Skeleton rows={3} className="p-0" />
      ) : shown.length === 0 ? (
        <p className="text-body-sm text-ink-2">Nothing entered from the hall yet.</p>
      ) : (
        <ol className="flex flex-col divide-y divide-line">
          {shown.map((event) => {
            const section = sectionOf.get(event.round_id);
            const disputed = event.action === "result_disputed";
            return (
              <li
                key={event.id}
                className={cx(
                  "flex flex-col gap-1 py-3",
                  disputed && "-mx-3 my-1 rounded-lg border border-rose-line bg-rose-soft/70 px-3",
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="flex items-center gap-2">
                    {disputed ? (
                      <span className="rounded-sm bg-state-disputed px-1.5 py-0.5 font-mono text-[10px] font-bold text-white">
                        DISPUTE
                      </span>
                    ) : (
                      <span aria-hidden className={cx("size-2 rounded-full", FEED_TONE[event.action] ?? "bg-state-empty")} />
                    )}
                    <span className="font-mono text-xs font-bold text-ink">
                      {event.board === null ? "Round" : `Board ${event.board}`}
                      {section && ` (Sec ${section.name})`}
                    </span>
                  </span>
                  <span className={cx("font-mono text-[11px]", disputed ? "font-medium text-rose-text" : "text-ink-3")}>
                    {relativeTime(event.at, now)}
                  </span>
                </div>
                <p className="text-xs leading-relaxed text-ink-2">{describe(event)}</p>
                {disputed && (
                  <Link
                    to={`/t/${tournamentId}/rounds/${event.round_id}?filter=attention`}
                    className="inline-flex items-center gap-1 pt-1 text-xs font-semibold text-rose-text hover:text-rose-text [&>svg]:size-3.5"
                  >
                    Open the board
                    <ArrowRight />
                  </Link>
                )}
              </li>
            );
          })}
        </ol>
      )}
    </Card>
  );
}

/** Drop the next round's files here and land in the import wizard with them. */
function RoundFileSync({
  tournamentId,
  sections,
  manager,
  managerLabel,
}: {
  tournamentId: string;
  sections: SectionSummary[];
  manager: string;
  managerLabel: string;
}) {
  const navigate = useNavigate();
  const next = sections
    .map((section) => nextAction(section))
    .find((action): action is Extract<NextAction, { kind: "import" }> => action.kind === "import");
  const onFiles = (list: FileList | null) => {
    const files = Array.from(list ?? []);
    if (files.length === 0) return;
    void Promise.all(
      files.map(async (one): Promise<PickedFile> => {
        const content = await readText(one);
        return { name: one.name, content, kind: sniff(content) };
      }),
    ).then((picked) => {
      const section = sections.length === 1 ? `?section=${encodeURIComponent(sections[0]!.name)}` : "";
      void navigate(`/t/${tournamentId}/import${section}`, { state: { files: picked } });
    });
  };
  return (
    <Card className="flex flex-col gap-4 p-4 sm:p-6">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-bold">Round file sync</h2>
        <Chip tone="neutral">{manager === "vega" ? "TRF16" : "Text export"} · {managerLabel}</Chip>
      </div>
      <DropZone
        compact
        multiple
        accept=".trf,.txt,text/plain"
        inputLabel="round files"
        onFiles={onFiles}
        title={
          manager === "vega" ? (
            <>
              Drop the Vega <span className="font-mono text-accent">.trf</span> here
            </>
          ) : (
            <>
              Drop the {managerLabel} <span className="font-mono text-accent">.txt</span> files here
            </>
          )
        }
        hint={next ? `Drag files here to prepare round ${next.round_number}` : "The preview shows what the file changes"}
      />
    </Card>
  );
}

function labelOf(action: NextAction, managerLabel: string): string {
  switch (action.kind) {
    case "import":
      return `Import round ${action.round_number}`;
    case "fix":
      return `Fix ${joinNonEmpty([
        action.round.disputed > 0 && `${action.round.disputed} disputed`,
        action.round.empty > 0 && `${action.round.empty} empty`,
      ])}`;
    case "release":
      return `Release round ${action.round.number}`;
    case "export":
      return `Export for ${managerLabel}`;
    case "players":
      return "Enter players";
    case "pair":
      return `Pair round ${action.round_number}`;
    case "finished":
      return "All rounds played · standings";
  }
}

function toneOf(action: NextAction): "primary" | "danger" | "success" {
  switch (action.kind) {
    case "fix":
      return action.round.disputed > 0 ? "danger" : "primary";
    case "export":
    case "finished":
      return "success";
    default:
      return "primary";
  }
}
