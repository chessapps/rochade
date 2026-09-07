/**
 * The three screens from the sketch, unchanged:
 *
 *   board list (sticky search)  ->  result choice  ->  confirm
 *
 * Black on white, ruled like a printed pairing sheet: this is read on a
 * five-year-old Android in a badly lit hall by someone who has just played four
 * hours of chess and wants to leave. Rows are dense, the confirmation is not.
 */

import type { Board } from "./api";
import type { GameResult, PendingClaim } from "./queue";

export const RESULT_LABELS: Record<
  GameResult,
  { score: string; name: string; white: string; black: string }
> = {
  white_win: { score: "1 : 0", name: "White wins", white: "1", black: "0" },
  draw: { score: "½ : ½", name: "Draw", white: "½", black: "½" },
  black_win: { score: "0 : 1", name: "Black wins", white: "0", black: "1" },
};

/** The stored code, as the row shows it once a result stands. */
const SHEET_SCORE: Record<string, string> = { "1": "1 – 0", "=": "½ – ½", "0": "0 – 1" };

export function BoardListScreen({
  boards,
  query,
  onQuery,
  onPick,
  pendingKeys,
  offline,
  queued,
  tournamentName,
}: {
  boards: Board[];
  query: string;
  onQuery: (value: string) => void;
  onPick: (board: Board) => void;
  pendingKeys: Set<string>;
  offline: boolean;
  queued: number;
  tournamentName?: string;
}) {
  const needle = query.trim().toLowerCase();
  const shown = needle
    ? boards.filter(
        (board) =>
          String(board.board) === needle ||
          board.white_name.toLowerCase().includes(needle) ||
          (board.black_name ?? "").toLowerCase().includes(needle),
      )
    : boards;
  const groups = groupByRound(shown);
  const oneGroup = groupByRound(boards).length === 1;

  return (
    <div className="flex h-full flex-col">
      <header className="sticky top-0 z-10 border-b-2 border-ink bg-paper px-3 pt-2 pb-2">
        <div className="flex items-baseline justify-between gap-2">
          <p className="truncate text-xs font-semibold tracking-wide uppercase">
            {tournamentName ?? "Results"}
          </p>
          <StatusLine offline={offline} queued={queued} shown={shown.length} />
        </div>
        <input
          value={query}
          onChange={(event) => onQuery(event.target.value)}
          placeholder="Your name or board"
          aria-label="Search by name or board number"
          autoComplete="off"
          autoCapitalize="off"
          spellCheck={false}
          className="mt-1.5 w-full rounded-md border-2 border-ink bg-paper px-3 py-2 text-base placeholder:text-mute focus:outline-none focus:ring-2 focus:ring-ink focus:ring-offset-1"
        />
      </header>

      <div className="flex-1 overflow-y-auto pb-6">
        {groups.map((group) => (
          <table key={group.key} className="w-full table-fixed border-collapse text-[15px]">
            <thead>
              <tr className="border-b border-ink bg-neutral-100 text-left text-[11px] font-semibold tracking-wide text-mute uppercase">
                <th className="w-9 py-1 pl-2 text-right">Bd</th>
                <th className="py-1 pl-2">
                  {oneGroup ? "White · Black" : `${group.section} · round ${group.round}`}
                </th>
                <th className="w-16 py-1 pr-2 text-right">Result</th>
              </tr>
            </thead>
            <tbody>
              {group.boards.map((board) => {
                const pending = pendingKeys.has(board.game_id);
                const open = !board.is_bye;
                return (
                  <tr
                    key={board.game_id}
                    role={open ? "button" : undefined}
                    tabIndex={open ? 0 : undefined}
                    aria-label={
                      open ? `Board ${board.board}, ${board.white_name} against ${board.black_name}` : undefined
                    }
                    onClick={open ? () => onPick(board) : undefined}
                    onKeyDown={
                      open
                        ? (event) => {
                            if (event.key === "Enter" || event.key === " ") {
                              event.preventDefault();
                              onPick(board);
                            }
                          }
                        : undefined
                    }
                    className={[
                      "border-b border-rule align-top",
                      open
                        ? "cursor-pointer active:bg-neutral-100 focus-visible:bg-neutral-100 focus-visible:outline-none"
                        : "text-mute",
                    ].join(" ")}
                  >
                    <td className="py-1.5 pl-2 text-right font-semibold tabular-nums">
                      {board.board}
                    </td>
                    <td className="py-1.5 pl-2 leading-tight">
                      <span className="block truncate">{board.white_name}</span>
                      <span className="block truncate text-mute">{board.black_name ?? "bye"}</span>
                    </td>
                    <td className="py-1.5 pr-2 text-right align-middle">
                      <BoardCell board={board} pending={pending} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ))}
        {shown.length === 0 && (
          <p className="px-4 py-10 text-center text-mute">
            {boards.length === 0 ? "No round is open for entry." : "No board matches that."}
          </p>
        )}
      </div>
    </div>
  );
}

function groupByRound(boards: Board[]) {
  const groups = new Map<string, { key: string; section: string; round: number; boards: Board[] }>();
  for (const board of boards) {
    const key = `${board.section_id}:${board.round_number}`;
    let group = groups.get(key);
    if (!group) {
      group = { key, section: board.section_name, round: board.round_number, boards: [] };
      groups.set(key, group);
    }
    group.boards.push(board);
  }
  return [...groups.values()];
}

function BoardCell({ board, pending }: { board: Board; pending: boolean }) {
  if (pending) {
    return <span className="text-xs text-mute">sending…</span>;
  }
  if (board.is_bye) {
    return <span className="text-xs">bye</span>;
  }
  if (board.entered) {
    return (
      <span className="font-semibold tabular-nums whitespace-nowrap">
        {SHEET_SCORE[board.white_result] ?? board.white_result}
      </span>
    );
  }
  return (
    <span className="rounded border border-ink px-2 py-0.5 text-xs font-semibold whitespace-nowrap">
      enter
    </span>
  );
}

function StatusLine({
  offline,
  queued,
  shown,
}: {
  offline: boolean;
  queued: number;
  shown: number;
}) {
  if (offline || queued > 0) {
    return (
      <p className="shrink-0 text-xs font-semibold">
        {offline ? "Offline" : ""}
        {offline && queued > 0 ? " · " : ""}
        {queued > 0 ? `${queued} waiting to send` : ""}
      </p>
    );
  }
  return <p className="shrink-0 text-xs text-mute tabular-nums">{shown} boards</p>;
}

export function ResultChoiceScreen({
  board,
  onChoose,
  onBack,
}: {
  board: Board;
  onChoose: (result: GameResult) => void;
  onBack: () => void;
}) {
  return (
    <div className="flex min-h-full flex-col gap-4 overflow-y-auto p-3">
      <BoardHeading board={board} />
      <p className="text-lg font-semibold">Who won?</p>
      <div className="flex flex-col gap-2">
        {(Object.keys(RESULT_LABELS) as GameResult[]).map((result) => (
          <button
            key={result}
            type="button"
            onClick={() => onChoose(result)}
            className="group flex items-center gap-4 rounded-md border-2 border-ink px-4 py-3 text-left focus-visible:ring-2 focus-visible:ring-ink focus-visible:ring-offset-2 focus-visible:outline-none active:bg-ink active:text-paper"
          >
            <span className="w-20 shrink-0 text-2xl font-bold tabular-nums">
              {RESULT_LABELS[result].score}
            </span>
            <span className="min-w-0 flex-1 leading-tight">
              <span className="block text-lg font-semibold">{RESULT_LABELS[result].name}</span>
              <span className="block text-sm text-mute break-words group-active:text-neutral-300">
                {winnerLine(board, result)}
              </span>
            </span>
          </button>
        ))}
      </div>
      <div className="pt-2">
        <SecondaryButton onClick={onBack}>Back to the list</SecondaryButton>
      </div>
    </div>
  );
}

function winnerLine(board: Board, result: GameResult): string {
  if (result === "white_win") return `${board.white_name} wins`;
  if (result === "black_win") return `${board.black_name ?? "black"} wins`;
  return "half a point each";
}

export function ConfirmScreen({
  board,
  result,
  onConfirm,
  onBack,
  busy,
}: {
  board: Board;
  result: GameResult;
  onConfirm: () => void;
  onBack: () => void;
  busy: boolean;
}) {
  return (
    <div className="flex min-h-full flex-col gap-4 overflow-y-auto p-3">
      <BoardHeading board={board} />
      <div>
        <p className="text-xs font-semibold tracking-wide text-mute uppercase">Check before sending</p>
        <p className="mt-1 text-3xl font-bold leading-tight">{RESULT_LABELS[result].name}</p>
        <p className="text-base text-mute">{winnerLine(board, result)}</p>
      </div>
      <ScoreSheet board={board} result={result} />
      <div className="flex flex-col gap-2 pt-2">
        <button
          type="button"
          onClick={onConfirm}
          disabled={busy}
          className="w-full rounded-md bg-ink py-4 text-xl font-bold text-paper focus-visible:ring-2 focus-visible:ring-ink focus-visible:ring-offset-2 focus-visible:outline-none active:bg-neutral-800 disabled:opacity-50"
        >
          {busy ? "Sending…" : `Confirm ${RESULT_LABELS[result].score}`}
        </button>
        <SecondaryButton onClick={onBack} disabled={busy}>
          Wrong, change it
        </SecondaryButton>
      </div>
    </div>
  );
}

/**
 * The result as it will appear on the pairing sheet: one line per colour,
 * the winner's line inverted so the eye lands on it even at arm's length.
 */
function ScoreSheet({ board, result }: { board: Board; result: GameResult }) {
  const rows: Array<{ colour: string; name: string; score: string; wins: boolean }> = [
    {
      colour: "White",
      name: board.white_name,
      score: RESULT_LABELS[result].white,
      wins: result === "white_win",
    },
    {
      colour: "Black",
      name: board.black_name ?? "bye",
      score: RESULT_LABELS[result].black,
      wins: result === "black_win",
    },
  ];
  return (
    <table className="w-full table-fixed border-collapse overflow-hidden rounded-md border-2 border-ink text-lg">
      <tbody>
        {rows.map((row) => (
          <tr
            key={row.colour}
            className={[
              "border-b-2 border-ink last:border-b-0",
              row.wins ? "bg-ink text-paper" : "",
            ].join(" ")}
          >
            <td
              className={[
                "w-[4.5rem] py-3 pr-2 pl-3 text-xs font-semibold tracking-wide uppercase",
                row.wins ? "text-neutral-300" : "text-mute",
              ].join(" ")}
            >
              {row.colour}
            </td>
            <td className="py-3 pr-2 leading-tight">
              <span className="block font-semibold break-words">{row.name}</span>
            </td>
            <td className="w-16 py-3 pr-3 text-right text-3xl font-bold tabular-nums">{row.score}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function DoneScreen({
  board,
  result,
  queued,
  onDone,
}: {
  board: Board;
  result: GameResult;
  queued: boolean;
  onDone: () => void;
}) {
  return (
    <div className="flex min-h-full flex-col gap-4 overflow-y-auto p-3">
      <BoardHeading board={board} />
      <div className="flex items-center gap-3">
        <span
          aria-hidden="true"
          className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-ink text-2xl font-bold text-paper"
        >
          {queued ? "…" : "✓"}
        </span>
        <div className="leading-tight">
          <p className="text-2xl font-bold">{queued ? "Saved on this phone" : "Result sent"}</p>
          <p className="text-sm text-mute">
            {queued
              ? "It will send itself as soon as there is a network."
              : "The arbiter confirms it at the end of the round."}
          </p>
        </div>
      </div>
      <ScoreSheet board={board} result={result} />
      <div className="pt-2">
        <button
          type="button"
          onClick={onDone}
          className="w-full rounded-md bg-ink py-4 text-xl font-bold text-paper focus-visible:ring-2 focus-visible:ring-ink focus-visible:ring-offset-2 focus-visible:outline-none active:bg-neutral-800"
        >
          Done
        </button>
      </div>
    </div>
  );
}

function BoardHeading({ board }: { board: Board }) {
  return (
    <header className="flex items-baseline justify-between gap-3 border-b-2 border-ink pb-2">
      <p className="text-2xl font-bold tabular-nums">Board {board.board}</p>
      <p className="truncate text-xs font-semibold tracking-wide text-mute uppercase">
        {board.section_name} · round {board.round_number}
      </p>
    </header>
  );
}

function SecondaryButton({
  onClick,
  disabled,
  children,
}: {
  onClick: () => void;
  disabled?: boolean;
  children: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="w-full rounded-md border-2 border-ink py-3 text-lg font-semibold focus-visible:ring-2 focus-visible:ring-ink focus-visible:ring-offset-2 focus-visible:outline-none active:bg-neutral-100 disabled:opacity-50"
    >
      {children}
    </button>
  );
}

export function RejectedBanner({
  claims,
  onDismiss,
}: {
  claims: PendingClaim[];
  onDismiss: (key: string) => void;
}) {
  if (claims.length === 0) return null;
  return (
    <div role="alert" className="border-b-2 border-ink bg-ink px-3 py-2 text-sm text-paper">
      {claims.map((claim) => (
        <p key={claim.key} className="flex items-center justify-between gap-3 py-1">
          <span>
            <span className="font-bold">Not accepted: </span>
            {claim.rejected}
          </span>
          <button
            type="button"
            onClick={() => onDismiss(claim.key)}
            className="shrink-0 rounded border border-paper px-3 py-1 font-semibold"
          >
            OK
          </button>
        </p>
      ))}
    </div>
  );
}
