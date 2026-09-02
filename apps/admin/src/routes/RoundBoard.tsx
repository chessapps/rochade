/**
 * The round, board by board. This is where the arbiter lives while a round is
 * open: results arrive from the phones every few seconds, the ones that need a
 * hand are one filter away, and the release is at the bottom of the page.
 */

import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { Link, useLocation, useParams, useSearchParams } from "react-router";

import { errorMessage, type BoardDetail, type GameResult, type RoundSummary } from "../api";
import {
  changedBoards,
  countBoards,
  defaultFilter,
  filterBoards,
  filterCount,
  isFilter,
  readyToRelease,
  type Filter,
} from "../boards";
import { BoardRow, PLAYED } from "../components/BoardRow";
import { ProgressBar } from "../components/ProgressBar";
import { download, ExportDialog, ReleaseDialog } from "../components/RoundDialogs";
import { RoundChip } from "../components/StateChip";
import { useToast } from "../components/Toast";
import { Banner, Button, Card, EmptyState, Input, Skeleton, SuccessCheck, cx } from "../components/ui";
import { plural, relativeTime } from "../format";
import {
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
  const now = useNow(1_000);

  const state = round.data?.state;
  const events = useRoundEvents(roundId, state !== undefined);
  const setResult = useSetResult();
  const resolve = useResolveDispute();

  const [params, setParams] = useSearchParams();
  const requested = params.get("filter");
  const filter: Filter = isFilter(requested) ? requested : defaultFilter(state ?? "open");
  const [query, setQuery] = useState("");
  const [dialog, setDialog] = useState<"release" | "export" | null>(null);

  // Rows that moved since the previous poll light up for a moment.
  const previous = useRef<BoardDetail[] | undefined>(undefined);
  const changed = useMemo(() => {
    const boards = round.data?.boards ?? [];
    const diff = changedBoards(previous.current, boards);
    previous.current = boards;
    return diff;
  }, [round.data]);

  // Once the round leaves "open", the default filter changes; drop an explicit
  // one that only made sense while entering.
  useEffect(() => {
    if (state && state !== "open" && requested === "attention") {
      setParams({}, { replace: true });
    }
  }, [state, requested, setParams]);

  if (round.isPending) return <Skeleton rows={8} />;
  if (round.isError) {
    return <Banner tone="error">Could not load the round: {errorMessage(round.error)}</Banner>;
  }

  const detail = round.data;
  const section = tournament.data?.sections?.find((s) => s.id === detail.section_id);
  const summary = section?.rounds?.find((r) => r.id === detail.id);
  const managerLabel = section?.manager_label ?? "the manager";
  const counts = countBoards(detail.boards);
  const editable = detail.state !== "exported";
  const shown = filterBoards(detail.boards, filter, query);
  const busy = setResult.isPending || resolve.isPending;

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

  return (
    <div className="flex flex-col gap-4 pb-24">
      <header className="flex flex-col gap-2">
        <Link to={`/t/${tournamentId}`} className="text-sm text-slate-500 hover:underline">
          ← {tournament.data?.name ?? "Tournament"}
        </Link>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <h1 className="text-xl font-semibold">
            Section {detail.section_name} · Round {detail.number}
          </h1>
          <RoundChip state={detail.state} />
          <span className="flex-1" />
          <span
            className={cx(
              "text-xs tabular-nums",
              round.isFetching ? "text-accent" : "text-slate-400",
              round.failureCount > 0 && "text-amber-700",
            )}
            aria-live="polite"
          >
            {round.failureCount > 0 ? "not updating — check the network" : freshness}
          </span>
        </div>
        <p className="text-sm text-slate-500">
          {detail.source_filename && <>from <code>{detail.source_filename}</code> · </>}
          {plural(counts.boards, "board")}
          {counts.byes > 0 && `, ${plural(counts.byes, "bye")}`}
        </p>
      </header>

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

      <Card className="p-4 sm:p-5">
        <ProgressBar counts={counts} />
      </Card>

      <Card>
        <div className="flex flex-col gap-3 border-b border-slate-100 p-3 sm:flex-row sm:items-center sm:p-4">
          <div role="tablist" aria-label="show" className="flex gap-1 overflow-x-auto">
            {(Object.keys(FILTER_LABEL) as Filter[]).map((option) => {
              const count = filterCount(detail.boards, option);
              const active = filter === option;
              return (
                <button
                  key={option}
                  role="tab"
                  aria-selected={active}
                  type="button"
                  onClick={() => setParams(option === defaultFilter(detail.state) ? {} : { filter: option })}
                  className={cx(
                    "min-h-10 rounded-lg px-3 text-sm font-medium whitespace-nowrap tabular-nums transition-colors",
                    active ? "bg-ink text-white" : "text-slate-600 hover:bg-slate-100",
                    option === "attention" && !active && count > 0 && "text-rose-700",
                  )}
                >
                  {FILTER_LABEL[option]} <span className="opacity-70">{count}</span>
                </button>
              );
            })}
          </div>
          <Input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="name or board number"
            aria-label="search boards"
            className="min-h-10 sm:ml-auto sm:w-64"
            onKeyDown={(event) => {
              if (event.key === "Escape") setQuery("");
            }}
          />
        </div>

        {shown.length === 0 ? (
          <div className="p-4">
            <EmptyState title={emptyTitle(filter, query)}>
              {filter === "attention" && !query && "Every board has a result and nobody disagrees."}
            </EmptyState>
          </div>
        ) : (
          <ul onKeyDown={onKey} className="focus-within:[&_li:focus]:bg-accent-soft/40">
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

      {editable && (
        <p className="text-xs text-slate-400">
          Keyboard: ↑ ↓ move between boards, then <kbd>1</kbd> <kbd>=</kbd> <kbd>0</kbd> set the
          result.
        </p>
      )}

      {summary && detail.state !== "exported" && (
        <Footer
          round={summary}
          managerLabel={managerLabel}
          onRelease={() => setDialog("release")}
          onExport={() => setDialog("export")}
        />
      )}

      {summary && (
        <>
          <ReleaseDialog
            round={summary}
            tournamentId={tournamentId}
            boards={{
              empty: detail.boards.filter((b) => !b.is_bye && b.state === "empty").map((b) => b.board),
              disputed: detail.boards.filter((b) => b.state === "disputed").map((b) => b.board),
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

/** The one action for this round, always in reach. */
function Footer({
  round,
  managerLabel,
  onRelease,
  onExport,
}: {
  round: RoundSummary;
  managerLabel: string;
  onRelease: () => void;
  onExport: () => void;
}) {
  const ready = readyToRelease(round);
  return (
    <div className="no-print fixed inset-x-0 bottom-0 z-10 border-t border-slate-200 bg-white/95 backdrop-blur">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-3 px-4 py-3 sm:px-6">
        <p className="text-sm text-slate-600">
          {round.state === "open" ? (
            ready ? (
              <>Every board has a result. Release the round to confirm them.</>
            ) : (
              <>
                <span className="font-medium text-rose-700">
                  {plural(round.empty + round.disputed, "board")}
                </span>{" "}
                still {round.empty + round.disputed === 1 ? "needs" : "need"} you before release.
              </>
            )
          ) : (
            <>Released. Export the results for {managerLabel} to close the round.</>
          )}
        </p>
        <span className="flex-1" />
        {round.state === "open" ? (
          <Button tone={ready ? "primary" : "secondary"} size="lg" onClick={onRelease}>
            {ready ? `Release round ${round.number}` : "Release anyway…"}
          </Button>
        ) : (
          <Button tone="success" size="lg" onClick={onExport}>
            Export for {managerLabel}
          </Button>
        )}
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
    <Card className="border-emerald-300 bg-emerald-50 p-4 text-sm text-emerald-950 sm:p-5">
      <div className="flex items-start gap-3">
        {justExported && <SuccessCheck />}
        <div className="flex min-w-0 flex-1 flex-col gap-2">
          <p className="text-base font-semibold">
            Round {roundNumber} exported
            {file.data && (
              <>
                {" "}
                as <code className="font-mono text-sm">{file.data.filename}</code>
              </>
            )}{" "}
            and frozen.
          </p>
          {file.data ? (
            <p>
              <span className="font-medium">Now in {managerLabel}:</span> {file.data.next_step}
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
            <Link
              to={`/t/${tournamentId}/import?section=${encodeURIComponent(sectionName)}`}
              className="inline-flex min-h-11 items-center rounded-lg border border-emerald-300 bg-white px-4 text-sm font-medium hover:bg-emerald-100"
            >
              Import round {roundNumber + 1}
            </Link>
          </div>
        </div>
      </div>
    </Card>
  );
}
