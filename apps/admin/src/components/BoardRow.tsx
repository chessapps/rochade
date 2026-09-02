/**
 * One board of a round: who plays, what stands, and the buttons to change it.
 *
 * The same row serves the laptop (a wide grid, everything on one line) and a
 * phone in the hall (stacked, thumb-sized buttons). The common case is three
 * buttons; forfeits are one tap further away so they cannot be hit by accident.
 */

import { useId, useState, type ButtonHTMLAttributes } from "react";

import type { BoardDetail, GameResult, RoundEvent } from "../api";
import { clockTime, resultLabel } from "../format";
import { StateChip } from "./StateChip";
import { Button, cx } from "./ui";

export const PLAYED: { label: string; white: string; black: string; result: GameResult }[] = [
  { label: "1:0", white: "1", black: "0", result: "white_win" },
  { label: "½:½", white: "=", black: "=", result: "draw" },
  { label: "0:1", white: "0", black: "1", result: "black_win" },
];

export const FORFEITS: { label: string; title: string; white: string; black: string }[] = [
  { label: "+:−", title: "Black did not appear", white: "+", black: "-" },
  { label: "−:+", title: "White did not appear", white: "-", black: "+" },
  { label: "−:−", title: "Neither appeared", white: "-", black: "-" },
];

const CLAIM_LABEL: Record<string, string> = {
  white_win: "1:0",
  draw: "½:½",
  black_win: "0:1",
};

export interface BoardActions {
  onSet: (board: BoardDetail, white: string, black: string) => void;
  onResolve: (board: BoardDetail, result: GameResult) => void;
}

export function BoardRow({
  board,
  editable,
  busy,
  changed,
  events,
  actions,
}: {
  board: BoardDetail;
  editable: boolean;
  busy: boolean;
  changed: boolean;
  events: RoundEvent[] | undefined;
  actions: BoardActions;
}) {
  const [history, setHistory] = useState(false);
  const historyId = useId();
  const own = events?.filter((e) => e.board === board.board) ?? [];
  const claims = own.filter(
    (e) => e.action === "result_claimed" || e.action === "result_disputed",
  );

  return (
    <li
      tabIndex={0}
      data-game-id={board.game_id}
      aria-label={`board ${board.board}, ${board.white_name} against ${board.black_name ?? "bye"}`}
      className={cx(
        "grid gap-x-3 gap-y-2 border-t border-slate-100 px-3 py-3 outline-offset-[-2px] sm:px-4",
        "grid-cols-[2.5rem_minmax(0,1fr)_auto] lg:grid-cols-[3rem_minmax(0,1fr)_10rem_auto] lg:items-center",
        changed && "animate-row-pulse",
        board.state === "disputed" && "bg-rose-50/60",
        board.is_bye && "text-slate-400",
      )}
    >
      <span className="pt-0.5 text-lg font-semibold text-slate-500 tabular-nums lg:text-xl">
        {board.board}
      </span>

      <span className="min-w-0">
        <span className="block truncate text-base">{board.white_name}</span>
        <span className="block truncate text-base text-slate-500">
          {board.black_name ?? "bye"}
        </span>
      </span>

      <span className="flex flex-col items-end gap-1 lg:items-start">
        <span className="text-lg font-semibold tabular-nums">
          {resultLabel(board.white_result, board.black_result, board.is_bye)}
        </span>
        {!board.is_bye && (
          <span className="flex items-center gap-2">
            <StateChip state={board.state} />
            {own.length > 0 && (
              <button
                type="button"
                onClick={() => setHistory((v) => !v)}
                aria-expanded={history}
                aria-controls={historyId}
                className="text-xs text-slate-400 underline-offset-2 hover:text-slate-600 hover:underline"
              >
                {history ? "hide" : "history"}
              </button>
            )}
          </span>
        )}
      </span>

      {editable && !board.is_bye && (
        <div className="col-span-3 lg:col-span-1 lg:justify-self-end">
          <Controls board={board} busy={busy} actions={actions} />
        </div>
      )}

      {board.state === "disputed" && (
        <Claims
          claims={claims}
          standing={board.white_result}
          other={board.disputed_white_result}
          className="col-span-3 lg:col-span-4"
        />
      )}

      {history && <History id={historyId} events={own} className="col-span-3 lg:col-span-4" />}
    </li>
  );
}

function Controls({
  board,
  busy,
  actions,
}: {
  board: BoardDetail;
  busy: boolean;
  actions: BoardActions;
}) {
  const [more, setMore] = useState(false);
  const [changing, setChanging] = useState(false);

  if (board.state === "confirmed" && !changing) {
    return (
      <Button size="sm" tone="ghost" onClick={() => setChanging(true)} disabled={busy}>
        change
      </Button>
    );
  }

  // A dispute has two claims; lighting one up would take a side.
  const current = board.state === "disputed" ? "" : `${board.white_result}${board.black_result}`;
  const pick = (white: string, black: string, result: GameResult | null) => {
    if (board.state === "disputed" && result) actions.onResolve(board, result);
    else actions.onSet(board, white, black);
    setChanging(false);
    setMore(false);
  };

  return (
    <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="set result">
      {PLAYED.map((option) => (
        <Choice
          key={option.label}
          active={current === option.white + option.black}
          disabled={busy}
          onClick={() => pick(option.white, option.black, option.result)}
        >
          {option.label}
        </Choice>
      ))}
      {board.state !== "disputed" &&
        (more ? (
          FORFEITS.map((option) => (
            <Choice
              key={option.label}
              active={current === option.white + option.black}
              disabled={busy}
              title={option.title}
              onClick={() => pick(option.white, option.black, null)}
            >
              {option.label}
            </Choice>
          ))
        ) : (
          <button
            type="button"
            onClick={() => setMore(true)}
            disabled={busy}
            className="min-h-11 rounded-lg px-2 text-sm text-slate-500 hover:bg-slate-100 lg:min-h-9"
            title="forfeits"
          >
            forfeit…
          </button>
        ))}
      {changing && (
        <button
          type="button"
          onClick={() => setChanging(false)}
          className="min-h-11 px-2 text-sm text-slate-500 lg:min-h-9"
        >
          keep
        </button>
      )}
    </div>
  );
}

function Choice({
  active,
  children,
  className,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { active: boolean }) {
  return (
    <button
      type="button"
      {...rest}
      aria-pressed={active}
      className={cx(
        "min-h-11 min-w-14 rounded-lg border px-3 text-base font-semibold tabular-nums transition-colors disabled:opacity-40 lg:min-h-9 lg:min-w-12 lg:text-sm",
        active
          ? "border-ink bg-ink text-white"
          : "border-slate-300 bg-white hover:border-slate-400 hover:bg-slate-50",
        className,
      )}
    >
      {children}
    </button>
  );
}

/** Both sides of a dispute, and who said what if the log knows. */
function Claims({
  claims,
  standing,
  other,
  className,
}: {
  claims: RoundEvent[];
  standing: string;
  other: string | null;
  className?: string;
}) {
  const said = (claim: RoundEvent) => {
    const label = CLAIM_LABEL[String(claim.payload.claimed)] ?? String(claim.payload.claimed);
    const who = claim.device_label ? `“${claim.device_label}”` : "a phone";
    return `${label} — ${who}, ${clockTime(claim.at)}`;
  };
  const first = claims.find((c) => c.action === "result_claimed");
  const second = claims.find((c) => c.action === "result_disputed");
  return (
    <p className={cx("text-sm text-rose-800", className)}>
      <span className="font-medium">Two phones disagree.</span>{" "}
      {first && second ? (
        <>
          First {said(first)}; then {said(second)}.
        </>
      ) : (
        <>
          First “{resultLabel(standing, mirror(standing))}”, then “
          {resultLabel(other ?? " ", mirror(other ?? " "))}”.
        </>
      )}{" "}
      Pick the right one, or set it from the scoresheet.
    </p>
  );
}

function mirror(code: string): string {
  return { "1": "0", "0": "1", "=": "=" }[code] ?? " ";
}

const ACTION_LABEL: Record<string, string> = {
  result_claimed: "entered",
  result_disputed: "disputed",
  result_set: "set by the arbiter",
  dispute_resolved: "resolved by the arbiter",
};

function History({
  id,
  events,
  className,
}: {
  id: string;
  events: RoundEvent[];
  className?: string;
}) {
  return (
    <ol id={id} className={cx("flex flex-col gap-0.5 text-xs text-slate-500", className)}>
      {events.map((event) => (
        <li key={event.id} className="tabular-nums">
          {clockTime(event.at)} · {ACTION_LABEL[event.action] ?? event.action}
          {"claimed" in event.payload && ` ${CLAIM_LABEL[String(event.payload.claimed)] ?? ""}`}
          {"white_result" in event.payload &&
            ` ${resultLabel(String(event.payload.white_result), String(event.payload.black_result ?? " "))}`}
          {"chosen" in event.payload && ` ${CLAIM_LABEL[String(event.payload.chosen)] ?? ""}`}
          {event.device_label && ` · “${event.device_label}”`}
          {event.actor_kind === "staff" && " · you"}
        </li>
      ))}
    </ol>
  );
}
