/**
 * The three screens from the sketch, unchanged:
 *
 *   board list (sticky search)  ->  result choice  ->  confirm
 *
 * Dense rows, large tap targets, high contrast: this is read on a five-year-old
 * Android in a badly lit hall by someone who has just played four hours of
 * chess and wants to leave.
 */

import type { Board } from "./api";
import type { GameResult, PendingClaim } from "./queue";

export const RESULT_LABELS: Record<GameResult, { score: string; name: string }> = {
  white_win: { score: "1 : 0", name: "White wins" },
  draw: { score: "½ : ½", name: "Draw" },
  black_win: { score: "0 : 1", name: "Black wins" },
};

export function BoardListScreen({
  boards,
  query,
  onQuery,
  onPick,
  pendingKeys,
  offline,
  queued,
}: {
  boards: Board[];
  query: string;
  onQuery: (value: string) => void;
  onPick: (board: Board) => void;
  pendingKeys: Set<string>;
  offline: boolean;
  queued: number;
}) {
  const needle = query.trim().toLowerCase();
  const shown = needle
    ? boards.filter(
        (board) =>
          board.white_name.toLowerCase().includes(needle) ||
          (board.black_name ?? "").toLowerCase().includes(needle),
      )
    : boards;

  return (
    <div className="flex h-full flex-col">
      <header className="sticky top-0 z-10 bg-board px-3 pt-3 pb-2 shadow-lg shadow-black/40">
        <input
          value={query}
          onChange={(event) => onQuery(event.target.value)}
          placeholder="Search your name"
          autoComplete="off"
          autoCapitalize="off"
          spellCheck={false}
          className="w-full rounded-xl bg-slate-800 px-4 py-3 text-lg text-slate-50 placeholder:text-slate-400 focus:ring-2 focus:ring-sky-400 focus:outline-none"
        />
        <StatusLine offline={offline} queued={queued} shown={shown.length} />
      </header>

      <ul className="flex-1 overflow-y-auto pb-8">
        {shown.map((board) => (
          <li key={board.game_id}>
            <button
              type="button"
              disabled={board.is_bye}
              onClick={() => onPick(board)}
              className="flex w-full items-center gap-3 border-b border-slate-800 px-3 py-3 text-left active:bg-slate-800 disabled:opacity-40"
            >
              <span className="w-10 shrink-0 text-center text-sm text-slate-400 tabular-nums">
                {board.section_name}
                <span className="block text-base text-slate-200">{board.board}</span>
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-base">{board.white_name}</span>
                <span className="block truncate text-base text-slate-300">
                  {board.black_name ?? "bye"}
                </span>
              </span>
              <BoardBadge board={board} pending={pendingKeys.has(board.game_id)} />
            </button>
          </li>
        ))}
        {shown.length === 0 && (
          <li className="px-4 py-10 text-center text-slate-400">
            No board matches that name.
          </li>
        )}
      </ul>
    </div>
  );
}

function BoardBadge({ board, pending }: { board: Board; pending: boolean }) {
  if (pending) {
    return (
      <span className="shrink-0 rounded-lg bg-amber-500/20 px-2 py-1 text-xs text-amber-300">
        sending
      </span>
    );
  }
  if (board.is_bye) {
    return <span className="shrink-0 text-xs text-slate-500">bye</span>;
  }
  if (board.entered) {
    return (
      <span className="shrink-0 rounded-lg bg-emerald-500/20 px-2 py-1 text-xs text-emerald-300">
        entered
      </span>
    );
  }
  return <span className="shrink-0 text-2xl text-slate-600">›</span>;
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
      <p className="pt-2 text-sm text-amber-300">
        {offline ? "Offline — " : ""}
        {queued > 0
          ? `${queued} result${queued === 1 ? "" : "s"} waiting to send`
          : "your results will send when the network returns"}
      </p>
    );
  }
  return <p className="pt-2 text-sm text-slate-400">{shown} boards</p>;
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
    <div className="flex h-full flex-col p-4">
      <BoardHeading board={board} />
      <div className="flex flex-1 flex-col justify-center gap-3">
        {(Object.keys(RESULT_LABELS) as GameResult[]).map((result) => (
          <button
            key={result}
            type="button"
            onClick={() => onChoose(result)}
            className="flex items-center justify-between rounded-2xl bg-slate-800 px-5 py-6 text-left active:bg-slate-700"
          >
            <span className="text-2xl font-semibold tabular-nums">
              {RESULT_LABELS[result].score}
            </span>
            <span className="text-lg text-slate-300">{RESULT_LABELS[result].name}</span>
          </button>
        ))}
      </div>
      <BackButton onBack={onBack} />
    </div>
  );
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
    <div className="flex h-full flex-col p-4">
      <BoardHeading board={board} />
      <div className="flex flex-1 flex-col items-center justify-center gap-2">
        <p className="text-slate-400">You are reporting</p>
        <p className="text-5xl font-semibold tabular-nums">{RESULT_LABELS[result].score}</p>
        <p className="text-xl text-slate-300">{RESULT_LABELS[result].name}</p>
      </div>
      <div className="flex gap-3">
        <button
          type="button"
          onClick={onBack}
          className="flex-1 rounded-2xl bg-slate-800 py-5 text-lg active:bg-slate-700"
        >
          Back
        </button>
        <button
          type="button"
          onClick={onConfirm}
          disabled={busy}
          className="flex-[2] rounded-2xl bg-emerald-600 py-5 text-lg font-semibold active:bg-emerald-500 disabled:opacity-60"
        >
          {busy ? "Sending…" : "Confirm"}
        </button>
      </div>
    </div>
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
    <div className="flex h-full flex-col p-4">
      <BoardHeading board={board} />
      <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center">
        <p className="text-5xl">{queued ? "⏳" : "✓"}</p>
        <p className="text-2xl font-semibold tabular-nums">{RESULT_LABELS[result].score}</p>
        <p className="max-w-xs text-slate-300">
          {queued
            ? "Saved on this phone. It will send itself as soon as there is a network."
            : "Recorded. The arbiter confirms it at the end of the round."}
        </p>
      </div>
      <button
        type="button"
        onClick={onDone}
        className="rounded-2xl bg-slate-800 py-5 text-lg active:bg-slate-700"
      >
        Back to the board list
      </button>
    </div>
  );
}

function BoardHeading({ board }: { board: Board }) {
  return (
    <header className="border-b border-slate-800 pb-3">
      <p className="text-sm text-slate-400">
        {board.section_name} · round {board.round_number} · board {board.board}
      </p>
      <p className="truncate text-lg">{board.white_name}</p>
      <p className="truncate text-lg text-slate-300">{board.black_name ?? "bye"}</p>
    </header>
  );
}

function BackButton({ onBack }: { onBack: () => void }) {
  return (
    <button
      type="button"
      onClick={onBack}
      className="rounded-2xl bg-slate-800 py-5 text-lg active:bg-slate-700"
    >
      Back
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
    <div className="bg-rose-900/80 px-4 py-3 text-sm">
      {claims.map((claim) => (
        <p key={claim.key} className="flex items-center justify-between gap-3 py-1">
          <span>{claim.rejected}</span>
          <button
            type="button"
            onClick={() => onDismiss(claim.key)}
            className="shrink-0 rounded-lg bg-rose-800 px-3 py-1"
          >
            OK
          </button>
        </p>
      ))}
    </div>
  );
}
