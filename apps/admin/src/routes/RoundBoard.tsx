/**
 * The round, board by board. This is where the arbiter lives while a round is
 * open: results arrive from the phones every few seconds, the ones that need a
 * hand are one filter away, and the release is in the dock at the bottom.
 */

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { Link, useLocation, useParams, useSearchParams } from "react-router";

import {
  errorMessage,
  type BoardDetail,
  type GameResult,
  type RoundDetail,
  type RoundSummary,
} from "../api";
import {
  changedBoards,
  countBoards,
  defaultFilter,
  filterBoards,
  filterCount,
  isFilter,
  readyToRelease,
  type Counts,
  type Filter,
} from "../boards";
import { BoardRow, PLAYED, ROW_GRID } from "../components/BoardRow";
import { ConfirmDialog } from "../components/Dialog";
import { Gavel, Keyboard, QrCode, Search } from "../components/icons";
import { ProgressBar } from "../components/ProgressBar";
import { download, ExportDialog, ReleaseDialog } from "../components/RoundDialogs";
import { SegmentedTabs } from "../components/SegmentedTabs";
import { RoundChip, STATE_TEXT } from "../components/StateChip";
import { useToast } from "../components/Toast";
import { Banner, Button, Card, EmptyState, Input, Kbd, Skeleton, SuccessCheck, cx } from "../components/ui";
import { plural, relativeTime, resultLabel } from "../format";
import {
  keys,
  pollInterval,
  useConfirmBoards,
  useExportFile,
  useResolveDispute,
  useRound,
  useRoundEvents,
  useSetResult,
  useTournament,
} from "../queries";
import { useNow } from "../useNow";

const FILTER_LABEL: Record<Filter, string> = {
  all: "All",
  attention: "Attention",
  entered: "Entered",
  confirmed: "Confirmed",
};

export function RoundBoard() {
  const { tournamentId = "", roundId = "" } = useParams();
  const round = useRound(roundId);
  const tournament = useTournament(tournamentId);
  const location = useLocation();
  const toast = useToast();
  const client = useQueryClient();
  const now = useNow(1_000);

  const state = round.data?.state;
  const events = useRoundEvents(roundId, state);
  const setResult = useSetResult();
  const resolve = useResolveDispute();
  const confirmBoards = useConfirmBoards();

  const [params, setParams] = useSearchParams();
  const requested = params.get("filter");
  const filter: Filter = isFilter(requested) ? requested : defaultFilter(state ?? "open");
  const [query, setQuery] = useState("");
  const [dialog, setDialog] = useState<"release" | "export" | "confirm" | null>(null);
  const search = useRef<HTMLInputElement>(null);

  // Rows that moved since the previous poll light up for a moment, and a board
  // that moved has a new line in the log: fetch it now, not at the log's own
  // slower cadence, so a dispute arrives with its phones named.
  const previous = useRef<BoardDetail[] | undefined>(undefined);
  const [changed, setChanged] = useState<Set<string>>(() => new Set());
  useEffect(() => {
    if (!round.data) return;
    const diff = changedBoards(previous.current, round.data.boards);
    previous.current = round.data.boards;
    setChanged(diff);
    if (diff.size > 0) void client.invalidateQueries({ queryKey: keys.events(roundId) });
  }, [round.data, client, roundId]);

  // Once the round leaves "open", the default filter changes; drop an explicit
  // one that only made sense while entering.
  useEffect(() => {
    if (state && state !== "open" && requested === "attention") {
      setParams({}, { replace: true });
    }
  }, [state, requested, setParams]);

  // "/" jumps to the search from anywhere on the page but a text field.
  useEffect(() => {
    const onSlash = (event: globalThis.KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (event.key !== "/" || target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement) return;
      event.preventDefault();
      search.current?.focus();
    };
    window.addEventListener("keydown", onSlash);
    return () => window.removeEventListener("keydown", onSlash);
  }, []);

  if (round.isPending) return <Skeleton rows={8} />;
  if (round.isError) {
    return <Banner tone="error">Could not load the round: {errorMessage(round.error)}</Banner>;
  }

  const detail = round.data;
  const section = tournament.data?.sections?.find((s) => s.id === detail.section_id);
  const managerLabel = section?.manager_label ?? "the manager";
  const counts = countBoards(detail.boards);
  // The release and export dialogs read the same numbers the board shows,
  // polled together, never a second copy that could lag behind.
  const summary = summarise(detail, counts);
  const editable = detail.state !== "exported";
  const shown = filterBoards(detail.boards, filter, query);
  const busy = setResult.isPending || resolve.isPending || confirmBoards.isPending;
  // Confirm what is on screen: the whole Entered list, or the part a search left.
  const entered = shown.filter((b) => b.state === "claimed");
  const disputedBoards = detail.boards.filter((b) => b.state === "disputed").map((b) => b.board);

  const fail = (error: unknown) => toast.error(errorMessage(error));
  const actions = {
    onSet: (board: BoardDetail, white: string, black: string) =>
      setResult.mutate(
        { gameId: board.game_id, roundId, tournamentId, white, black },
        { onError: fail },
      ),
    onResolve: (board: BoardDetail, result: GameResult) =>
      resolve.mutate({ gameId: board.game_id, roundId, tournamentId, result }, { onError: fail }),
  };

  const onKey = (event: KeyboardEvent<HTMLElement>) => {
    const target = event.target as HTMLElement;
    if (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement) return;
    const row = target.closest<HTMLElement>("[data-game-id]");
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const rows = [...event.currentTarget.querySelectorAll<HTMLElement>("[data-game-id]")];
      const index = row ? rows.indexOf(row) : -1;
      const next = rows[index + (event.key === "ArrowDown" ? 1 : -1)] ?? rows[index] ?? rows[0];
      next?.focus();
      return;
    }
    if (!row || !editable || busy) return;
    const board = detail.boards.find((b) => b.game_id === row.dataset.gameId);
    if (!board || board.is_bye) return;
    const choice = { "1": 0, "=": 1, "2": 1, "0": 2, "3": 2 }[event.key];
    if (choice === undefined) return;
    event.preventDefault();
    const option = PLAYED[choice]!;
    if (board.state === "disputed") actions.onResolve(board, option.result);
    else actions.onSet(board, option.white, option.black);
  };

  const freshness = round.isError
    ? "not updating"
    : round.dataUpdatedAt
      ? `updated ${relativeTime(new Date(round.dataUpdatedAt).toISOString(), now)}`
      : "";
  const every = pollInterval(detail.state);
  const done = counts.confirmed + counts.claimed;
  const percent = counts.boards > 0 ? Math.round((done / counts.boards) * 1000) / 10 : 0;

  return (
    <div className="flex flex-col gap-4 pb-32">
      {/* Round control bar */}
      <Card className="p-4 sm:p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-col gap-1">
            <p className="flex items-center gap-1.5 text-body-sm font-medium text-ink-2">
              <Link to={`/t/${tournamentId}`} className="hover:text-ink">
                {tournament.data?.name ?? "Tournament"}
              </Link>
              <span className="text-line-strong">/</span>
              <span>Section {detail.section_name}</span>
              {detail.source_filename && (
                <>
                  <span className="text-line-strong">/</span>
                  <code className="font-mono text-xs text-ink-3">{detail.source_filename}</code>
                </>
              )}
            </p>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
              <h1 className="text-headline-md">
                Section {detail.section_name} · Round {detail.number}
              </h1>
              <RoundChip state={detail.state}>
                {every && <span className="normal-case tracking-normal">· polling {every / 1000}s</span>}
              </RoundChip>
              <span
                className={cx(
                  "font-mono text-[11px]",
                  round.isFetching ? "text-accent" : "text-ink-3",
                  round.failureCount > 0 && "text-amber-700",
                )}
                aria-live="polite"
              >
                {round.failureCount > 0 ? "not updating — check the network" : freshness}
              </span>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button size="sm" to={`/t/${tournamentId}/devices`} icon={<QrCode />}>
              Hall QR code
            </Button>
          </div>
        </div>

        {/* Pipeline strip */}
        <div className="mt-4 flex flex-col gap-3 border-t border-line pt-3.5 text-xs md:flex-row md:items-center md:justify-between">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span className="font-semibold text-ink">
              {plural(counts.boards, "board")}
              {counts.byes > 0 && <span className="font-normal text-ink-2">, {plural(counts.byes, "bye")}</span>}
            </span>
            <span className="text-line-strong">•</span>
            <span className="flex items-center gap-2 font-mono text-[11px]">
              <span className={cx("font-semibold", STATE_TEXT.confirmed)}>{counts.confirmed} Confirmed</span>
              <span className="text-line-strong">/</span>
              <span className={cx("font-semibold", STATE_TEXT.claimed)}>{counts.claimed} Entered</span>
              <span className="text-line-strong">/</span>
              <span className={cx("font-semibold", STATE_TEXT.disputed)}>{counts.disputed} Dispute</span>
              <span className="text-line-strong">/</span>
              <span className="text-ink-2">{counts.empty} Awaiting</span>
            </span>
          </div>
          <div className="flex items-center gap-2.5 md:w-72">
            <ProgressBar counts={counts} size="sm" caption={false} className="flex-1" />
            <span className="font-mono text-[11px] font-semibold text-ink-2">{percent}%</span>
          </div>
        </div>
      </Card>

      {tournament.isError && (
        <Banner tone="error">
          The tournament summary did not load: {errorMessage(tournament.error)}. The board is
          live; the manager's name is not.
        </Banner>
      )}

      {detail.state === "exported" && (
        <Handoff
          roundId={roundId}
          roundNumber={detail.number}
          managerLabel={managerLabel}
          tournamentId={tournamentId}
          sectionName={detail.section_name}
          justExported={Boolean((location.state as { justExported?: boolean } | null)?.justExported)}
        />
      )}

      {/* Filter toolbar */}
      <div className="flex flex-col gap-3">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <SegmentedTabs
            label="show"
            value={filter}
            onChange={(option) => setParams(option === defaultFilter(detail.state) ? {} : { filter: option })}
            segments={(Object.keys(FILTER_LABEL) as Filter[]).map((option) => ({
              key: option,
              label: FILTER_LABEL[option],
              count: filterCount(detail.boards, option),
              alert: option === "attention",
            }))}
          />
          <div className="flex items-center gap-2 md:ml-auto">
            {editable && filter === "entered" && entered.length > 0 && (
              <Button tone="success" size="sm" onClick={() => setDialog("confirm")} disabled={busy}>
                Confirm {query ? `these ${entered.length}` : `all ${entered.length}`}
              </Button>
            )}
            <div className="relative w-full md:w-72">
              <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-ink-3" />
              <Input
                ref={search}
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="name or board number"
                aria-label="search boards"
                className="min-h-10 w-full pr-8 pl-9 text-xs"
                onKeyDown={(event) => {
                  if (event.key === "Escape") setQuery("");
                }}
              />
              <span className="pointer-events-none absolute top-1/2 right-2.5 hidden -translate-y-1/2 sm:inline">
                <Kbd>/</Kbd>
              </span>
            </div>
          </div>
        </div>

        {editable && (
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 rounded-lg border border-line bg-subtle/80 px-3 py-2 text-[11px] text-ink-2 [&>svg]:size-3.5">
            <Keyboard className="text-ink-3" />
            <span className="font-semibold text-ink">Hotkeys</span>
            <span className="inline-flex items-center gap-1">
              <Kbd>↑</Kbd>
              <Kbd>↓</Kbd> move
            </span>
            <span className="text-line-strong">•</span>
            <span className="inline-flex items-center gap-1">
              <Kbd>1</Kbd> White wins
            </span>
            <span className="text-line-strong">•</span>
            <span className="inline-flex items-center gap-1">
              <Kbd>=</Kbd> Draw
            </span>
            <span className="text-line-strong">•</span>
            <span className="inline-flex items-center gap-1">
              <Kbd>0</Kbd> Black wins
            </span>
            <span className="text-line-strong">•</span>
            <span className="inline-flex items-center gap-1">
              <Kbd>/</Kbd> Search
            </span>
          </div>
        )}
      </div>

      {/* Board table */}
      <Card className="overflow-hidden">
        <div
          className={cx(
            "hidden gap-x-3 border-b border-line bg-subtle/90 px-4 py-2 text-label-sm text-ink-2 lg:grid",
            ROW_GRID,
          )}
        >
          <span className="text-center">Brd</span>
          <span>White</span>
          <span className="text-center">Result</span>
          <span>Black</span>
          <span className="text-right">{editable ? "Decision" : "Status"}</span>
        </div>
        {shown.length === 0 ? (
          <div className="p-4">
            <EmptyState title={emptyTitle(filter, query)}>
              {filter === "attention" && !query && "Every board has a result and nobody disagrees."}
            </EmptyState>
          </div>
        ) : (
          <ul onKeyDown={onKey} className="[&>li:first-child]:border-t-0 focus-within:[&_li:focus]:bg-accent-soft/40">
            {shown.map((board) => (
              <BoardRow
                key={board.game_id}
                board={board}
                editable={editable}
                busy={busy}
                changed={changed.has(board.game_id)}
                events={events.data}
                actions={actions}
              />
            ))}
          </ul>
        )}
      </Card>

      {detail.state !== "exported" && (
        <Dock
          round={summary}
          disputedBoards={disputedBoards}
          managerLabel={managerLabel}
          showingAttention={filter === "attention"}
          onAttention={() => setParams({ filter: "attention" })}
          onRelease={() => setDialog("release")}
          onExport={() => setDialog("export")}
        />
      )}

      <ConfirmDialog
        open={dialog === "confirm"}
        onClose={() => setDialog(null)}
        title={`Confirm ${plural(entered.length, "entered board")}?`}
        confirmLabel="Confirm"
        tone="success"
        busy={confirmBoards.isPending}
        onConfirm={() =>
          confirmBoards.mutate(
            { roundId, tournamentId, gameIds: entered.map((b) => b.game_id) },
            {
              onSuccess: (outcome) => {
                toast.success(`${plural(outcome.confirmed, "board")} confirmed.`);
                setDialog(null);
              },
              onError: fail,
            },
          )
        }
      >
        <p>
          The results stand as the phones entered them:{" "}
          {entered.map((b) => `${b.board} ${resultLabel(b.white_result, b.black_result)}`).join(", ")}.
          A confirmed board is closed to the phones; anything a player still wants changed
          comes to you.
        </p>
      </ConfirmDialog>

      {detail.state !== "exported" && (
        <>
          <ReleaseDialog
            round={summary}
            tournamentId={tournamentId}
            boards={{
              empty: detail.boards.filter((b) => !b.is_bye && b.state === "empty").map((b) => b.board),
              disputed: disputedBoards,
            }}
            open={dialog === "release"}
            onClose={() => setDialog(null)}
          />
          <ExportDialog
            round={summary}
            tournamentId={tournamentId}
            managerLabel={managerLabel}
            open={dialog === "export"}
            onClose={() => setDialog(null)}
          />
        </>
      )}
    </div>
  );
}

function summarise(detail: RoundDetail, counts: Counts): RoundSummary {
  return {
    id: detail.id,
    number: detail.number,
    state: detail.state,
    boards: counts.boards,
    byes: counts.byes,
    empty: counts.empty,
    claimed: counts.claimed,
    disputed: counts.disputed,
    confirmed: counts.confirmed,
    imported_at: detail.imported_at,
    released_at: detail.released_at,
    exported_at: detail.exported_at,
  };
}

function emptyTitle(filter: Filter, query: string): string {
  if (query) return `No board matches “${query}”.`;
  switch (filter) {
    case "attention":
      return "Nothing needs you.";
    case "entered":
      return "No results waiting for release.";
    case "confirmed":
      return "Nothing confirmed yet.";
    default:
      return "No boards.";
  }
}

/** The floating dock: where the round stands and the one action for it, always in reach. */
function Dock({
  round,
  disputedBoards,
  managerLabel,
  showingAttention,
  onAttention,
  onRelease,
  onExport,
}: {
  round: RoundSummary;
  disputedBoards: number[];
  managerLabel: string;
  showingAttention: boolean;
  onAttention: () => void;
  onRelease: () => void;
  onExport: () => void;
}) {
  const ready = readyToRelease(round);
  const open = round.empty + round.disputed;
  const percent = round.boards > 0 ? Math.round((round.confirmed / round.boards) * 1000) / 10 : 0;
  return (
    <div className="no-print pointer-events-none fixed inset-x-0 bottom-4 z-10 px-4 sm:px-6">
      <div className="pointer-events-auto mx-auto flex max-w-[1160px] flex-col items-center justify-between gap-3 rounded-lg border border-slate-800 bg-ink p-3 text-white shadow-dock sm:flex-row sm:px-5 sm:py-3.5">
        <div className="flex w-full items-center gap-3 sm:w-auto">
          <span aria-hidden className="relative flex size-2.5 shrink-0">
            {!ready && round.state === "open" && (
              <span className="absolute inline-flex size-full animate-ping rounded-full bg-rose-500" />
            )}
            <span
              className={cx(
                "relative inline-flex size-2.5 rounded-full",
                round.state !== "open" ? "bg-round-released" : ready ? "bg-state-confirmed" : "bg-rose-500",
              )}
            />
          </span>
          <div>
            <p className="flex flex-wrap items-center gap-2 text-xs font-semibold sm:text-sm">
              {round.state === "open" ? (
                ready ? (
                  <span>Every board has a result. Release the round to confirm them.</span>
                ) : (
                  <span>
                    <span className="text-rose-300">{plural(open, "board")}</span> still{" "}
                    {open === 1 ? "needs" : "need"} you before release.
                  </span>
                )
              ) : (
                <span>Released. Export the results for {managerLabel} to close the round.</span>
              )}
              <span className="rounded-sm bg-slate-800 px-1.5 py-0.5 font-mono text-[11px] text-slate-300">
                {round.confirmed} of {round.boards} · {percent}%
              </span>
            </p>
            {round.state === "open" && disputedBoards.length > 0 && (
              <p className="mt-0.5 flex items-center gap-1 text-[11px] font-medium text-rose-300">
                {disputedBoards.length === 1 ? "A dispute on board" : "Disputes on boards"}{" "}
                {disputedBoards.join(", ")} must be resolved before release.
              </p>
            )}
          </div>
        </div>
        <div className="flex w-full items-center justify-end gap-2 sm:w-auto">
          {round.state === "open" && disputedBoards.length > 0 && !showingAttention && (
            <Button tone="danger" size="md" icon={<Gavel />} onClick={onAttention}>
              Resolve first
            </Button>
          )}
          {round.state === "open" ? (
            <Button
              tone={ready ? "primary" : "ghost"}
              size="md"
              onClick={onRelease}
              className={cx(!ready && "text-slate-300 hover:bg-slate-800 hover:text-white")}
            >
              {ready ? `Release round ${round.number}` : "Release anyway…"}
            </Button>
          ) : (
            <Button tone="success" size="md" onClick={onExport}>
              Export for {managerLabel}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * Shown once the round is frozen. The arbiter is about to switch to the
 * manager, so this is the one instruction that matters, in the manager's own
 * menu terms, with the file a click away in case the download went astray.
 */
function Handoff({
  roundId,
  roundNumber,
  managerLabel,
  tournamentId,
  sectionName,
  justExported,
}: {
  roundId: string;
  roundNumber: number;
  managerLabel: string;
  tournamentId: string;
  sectionName: string;
  justExported: boolean;
}) {
  const file = useExportFile(roundId, true);
  return (
    <Card className="border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-950 sm:p-5">
      <div className="flex items-start gap-3">
        {justExported && <SuccessCheck />}
        <div className="flex min-w-0 flex-1 flex-col gap-2">
          <p className="text-headline-sm">
            Round {roundNumber} exported
            {file.data && (
              <>
                {" "}
                as <code className="font-mono text-sm font-medium">{file.data.filename}</code>
              </>
            )}{" "}
            and frozen.
          </p>
          {file.data ? (
            <p>
              <span className="font-semibold">Now in {managerLabel}:</span> {file.data.next_step}
            </p>
          ) : file.isError ? (
            <p className="text-rose-800">{errorMessage(file.error)}</p>
          ) : (
            <p className="text-emerald-800">Fetching the file…</p>
          )}
          {file.data && (file.data.boards_left_blank ?? []).length > 0 && (
            <p>
              Left blank for you to enter there by hand: boards{" "}
              {(file.data.boards_left_blank ?? []).join(", ")}.
            </p>
          )}
          <div className="mt-1 flex flex-wrap gap-2">
            <Button tone="success" onClick={() => file.data && download(file.data)} disabled={!file.data}>
              {justExported ? "Download again" : "Download the file"}
            </Button>
            <Button
              to={`/t/${tournamentId}/import?section=${encodeURIComponent(sectionName)}`}
              className="border-emerald-300 hover:bg-emerald-100"
            >
              Import round {roundNumber + 1}
            </Button>
          </div>
        </div>
      </div>
    </Card>
  );
}
