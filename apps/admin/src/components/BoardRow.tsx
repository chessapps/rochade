/**
 * One board of a round: who plays, what stands, and the buttons to change it.
 *
 * The same row serves the desk (five columns on one line: board, White,
 * result, Black, what to do) and a phone in the hall (stacked, thumb-sized
 * buttons). The common case is three buttons; the rest of the TRF palette --
 * forfeits, unrated games, any pair of codes -- is one tap further away so it
 * cannot be hit by accident. A bye carries one code and offers the bye codes
 * instead.
 */

import { useId, useState, type ButtonHTMLAttributes } from "react";

import type { BoardDetail, GameResult, RoundEvent } from "../api";
import { clockTime, resultLabel } from "../format";
import { BoardNumber, type BoardNumberTone } from "./BoardNumber";
import { Disc } from "./Disc";
import { TriangleAlert } from "./icons";
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

/** Played, but not for rating: the TRF's W, D and L. */
export const UNRATED: { label: string; title: string; white: string; black: string }[] = [
  { label: "W:L", title: "White won, not rated", white: "W", black: "L" },
  { label: "D:D", title: "Draw, not rated", white: "D", black: "D" },
  { label: "L:W", title: "Black won, not rated", white: "L", black: "W" },
];

/** What a bye can carry. */
export const BYE_CODES: { code: string; label: string; title: string }[] = [
  { code: "U", label: "1 · bye", title: "Pairing-allocated bye, one point" },
  { code: "F", label: "1 · full", title: "Full-point bye" },
  { code: "H", label: "½ · half", title: "Half-point bye" },
  { code: "Z", label: "0 · absent", title: "Zero-point bye" },
];

/** Every code one side of a game may carry, for the free combination. */
export const SIDE_CODES: { code: string; label: string }[] = [
  { code: "1", label: "1 win" },
  { code: "=", label: "½ draw" },
  { code: "0", label: "0 loss" },
  { code: "+", label: "+ forfeit win" },
  { code: "-", label: "− forfeit loss" },
  { code: "W", label: "W win (unrated)" },
  { code: "D", label: "D draw (unrated)" },
  { code: "L", label: "L loss (unrated)" },
  { code: "H", label: "H half-point bye" },
  { code: "F", label: "F full-point bye" },
  { code: "U", label: "U allocated bye" },
  { code: "Z", label: "Z zero-point bye" },
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

/** The desk grid: board · White · result · Black · action. */
export const ROW_GRID = "lg:grid-cols-[3rem_minmax(0,1fr)_9rem_minmax(0,1fr)_auto]";

function toneOf(board: BoardDetail): BoardNumberTone {
  if (board.is_bye) return "muted";
  if (board.state === "disputed") return "disputed";
  if (board.state === "claimed") return "claimed";
  return "neutral";
}

/** "1 : 0" on the row, the way a pairing list prints it. */
function scoreOf(board: BoardDetail): string {
  const label = resultLabel(board.white_result, board.black_result, board.is_bye);
  return board.is_bye ? label : label.replace(":", " : ");
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
    (e) =>
      e.action === "result_claimed" ||
      e.action === "result_corrected" ||
      e.action === "result_disputed",
  );
  const score = scoreOf(board);

  return (
    <li
      tabIndex={0}
      data-game-id={board.game_id}
      aria-label={`board ${board.board}, ${board.white_name} against ${board.black_name ?? "bye"}`}
      className={cx(
        "grid grid-cols-[2.5rem_minmax(0,1fr)_auto] gap-x-3 gap-y-2 border-t border-line border-l-4 px-3 py-3 outline-offset-[-2px] transition-colors lg:items-center lg:px-4 lg:py-2.5",
        ROW_GRID,
        changed && "animate-row-pulse",
        board.state === "disputed"
          ? "border-l-rose-500 bg-rose-50/60"
          : board.state === "claimed"
            ? "border-l-amber-400 bg-amber-50/40 hover:bg-amber-50/70"
            : "border-l-transparent hover:bg-subtle/60",
        board.is_bye && "text-ink-3",
      )}
    >
      <span className="row-span-2 flex justify-center lg:row-span-1">
        <BoardNumber tone={toneOf(board)}>{String(board.board).padStart(2, "0")}</BoardNumber>
      </span>

      <Player side="white" name={board.white_name} rank={board.white_rank} muted={board.is_bye} />

      <span className="col-start-3 row-span-2 flex flex-col items-end gap-1 lg:col-start-3 lg:row-span-1 lg:items-center">
        {board.state === "disputed" ? (
          <>
            <span className="rounded-sm border border-rose-200 bg-rose-100/90 px-2 py-0.5 font-mono text-xs font-bold text-rose-700">
              DISPUTED
            </span>
            <span className="font-mono text-[10px] font-medium text-rose-600">
              {resultLabel(board.white_result, board.black_result)} vs{" "}
              {resultLabel(board.disputed_white_result ?? " ", mirror(board.disputed_white_result ?? " "))}
            </span>
          </>
        ) : (
          <span
            className={cx(
              "font-mono text-base font-bold whitespace-nowrap",
              score === "" ? "text-ink-3" : board.is_bye ? "text-ink-2" : "text-ink",
              board.state === "claimed" && "rounded-sm border border-amber-200 bg-amber-100 px-2 text-amber-900",
            )}
          >
            {score === "" ? "— : —" : score}
          </span>
        )}
        {!board.is_bye && (
          <span className="flex items-center gap-2">
            <StateChip state={board.state} />
            {own.length > 0 && (
              <button
                type="button"
                onClick={() => setHistory((v) => !v)}
                aria-expanded={history}
                aria-controls={historyId}
                className="text-[11px] text-ink-3 underline-offset-2 hover:text-ink-2 hover:underline"
              >
                {history ? "hide" : "history"}
              </button>
            )}
          </span>
        )}
      </span>

      <span className="col-start-2 lg:col-start-4">
        {board.black_name ? (
          <Player side="black" name={board.black_name} rank={board.black_rank} muted={board.is_bye} />
        ) : (
          <span className="text-body-md text-ink-3">bye</span>
        )}
      </span>

      {editable && (
        <div className="col-span-3 lg:col-span-1 lg:col-start-5 lg:justify-self-end">
          {board.is_bye ? (
            <ByeControls board={board} busy={busy} actions={actions} />
          ) : (
            <Controls board={board} busy={busy} actions={actions} />
          )}
        </div>
      )}

      {board.state === "disputed" && (
        <Claims
          claims={claims}
          standing={board.white_result}
          other={board.disputed_white_result}
          className="col-span-3 lg:col-span-5"
        />
      )}

      {history && <History id={historyId} events={own} className="col-span-3 lg:col-span-5" />}
    </li>
  );
}

function Player({
  side,
  name,
  rank,
  muted,
}: {
  side: "white" | "black";
  name: string;
  rank: number | null;
  muted: boolean;
}) {
  return (
    <span className="flex min-w-0 items-center gap-2.5">
      <Disc side={side} />
      <span className={cx("truncate text-body-md font-semibold", muted ? "text-ink-3" : "text-ink")}>
        {name}
      </span>
      {rank !== null && <span className="shrink-0 font-mono text-xs text-ink-3">#{rank}</span>}
    </span>
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
    <div className="flex flex-col items-end gap-2" role="group" aria-label="set result">
      <div className="flex flex-wrap items-center gap-1.5">
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
        {board.state !== "disputed" && (
          <button
            type="button"
            onClick={() => setMore((v) => !v)}
            disabled={busy}
            aria-expanded={more}
            className="min-h-11 rounded px-2 text-xs text-ink-2 hover:bg-subtle hover:text-ink lg:min-h-8"
            title="forfeits, unrated games and every other code"
          >
            {more ? "less" : "more…"}
          </button>
        )}
        {changing && (
          <button
            type="button"
            onClick={() => setChanging(false)}
            className="min-h-11 px-2 text-xs text-ink-2 hover:text-ink lg:min-h-8"
          >
            keep
          </button>
        )}
      </div>
      {more && board.state !== "disputed" && (
        <Palette current={current} busy={busy} onPick={(w, b) => pick(w, b, null)} />
      )}
    </div>
  );
}

/** The rest of the TRF vocabulary, grouped, plus any pair of codes by hand. */
function Palette({
  current,
  busy,
  onPick,
}: {
  current: string;
  busy: boolean;
  onPick: (white: string, black: string) => void;
}) {
  const [white, setWhite] = useState(current[0] && current[0] !== " " ? current[0] : "1");
  const [black, setBlack] = useState(current[1] && current[1] !== " " ? current[1] : "0");
  const groups: { name: string; options: { label: string; title: string; white: string; black: string }[] }[] = [
    { name: "Forfeit", options: FORFEITS },
    { name: "Unrated", options: UNRATED },
  ];
  return (
    <div className="flex flex-col gap-1.5 rounded-lg border border-line bg-subtle p-2 text-sm">
      {groups.map((group) => (
        <div key={group.name} className="flex flex-wrap items-center gap-1.5">
          <span className="w-16 text-label-sm text-ink-3">{group.name}</span>
          {group.options.map((option) => (
            <Choice
              key={option.label}
              active={current === option.white + option.black}
              disabled={busy}
              title={option.title}
              onClick={() => onPick(option.white, option.black)}
            >
              {option.label}
            </Choice>
          ))}
        </div>
      ))}
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="w-16 text-label-sm text-ink-3">Any pair</span>
        <SideSelect label="white code" value={white} onChange={setWhite} />
        <span className="text-ink-3">:</span>
        <SideSelect label="black code" value={black} onChange={setBlack} />
        <Button size="sm" disabled={busy} onClick={() => onPick(white, black)}>
          Set
        </Button>
      </div>
    </div>
  );
}

function SideSelect({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <select
      aria-label={label}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      className="min-h-9 rounded border border-line bg-card px-2 font-mono text-sm lg:min-h-8"
    >
      {SIDE_CODES.map((side) => (
        <option key={side.code} value={side.code}>
          {side.label}
        </option>
      ))}
    </select>
  );
}

/** A bye has one side; the codes say what it was worth. */
function ByeControls({
  board,
  busy,
  actions,
}: {
  board: BoardDetail;
  busy: boolean;
  actions: BoardActions;
}) {
  const [changing, setChanging] = useState(false);
  if (!changing) {
    return (
      <Button size="sm" tone="ghost" onClick={() => setChanging(true)} disabled={busy}>
        change
      </Button>
    );
  }
  return (
    <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="set bye">
      {BYE_CODES.map((option) => (
        <Choice
          key={option.code}
          active={board.white_result === option.code}
          disabled={busy}
          title={option.title}
          className="min-w-0"
          onClick={() => {
            actions.onSet(board, option.code, " ");
            setChanging(false);
          }}
        >
          {option.label}
        </Choice>
      ))}
      <button
        type="button"
        onClick={() => setChanging(false)}
        className="min-h-11 px-2 text-xs text-ink-2 hover:text-ink lg:min-h-8"
      >
        keep
      </button>
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
        "min-h-11 min-w-14 rounded border px-3 font-mono text-sm font-bold whitespace-nowrap transition-colors disabled:opacity-40 lg:min-h-8 lg:min-w-12 lg:text-xs",
        active
          ? "border-ink bg-ink text-white"
          : "border-line bg-card text-ink hover:border-line-strong hover:bg-subtle",
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
  const first = claims.find(
    (c) => c.action === "result_claimed" || c.action === "result_corrected",
  );
  const second = claims.find((c) => c.action === "result_disputed");
  return (
    <p
      className={cx(
        "flex items-start gap-2 rounded-lg border border-rose-200 bg-card px-3 py-2 text-body-sm text-rose-800 [&>svg]:mt-0.5 [&>svg]:size-4 [&>svg]:shrink-0 [&>svg]:text-rose-600",
        className,
      )}
    >
      <TriangleAlert />
      <span>
        <span className="font-semibold">Two phones disagree.</span>{" "}
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
      </span>
    </p>
  );
}

function mirror(code: string): string {
  return { "1": "0", "0": "1", "=": "=" }[code] ?? " ";
}

const ACTION_LABEL: Record<string, string> = {
  result_claimed: "entered",
  result_corrected: "corrected by the same phone",
  result_disputed: "disputed",
  result_set: "set by the arbiter",
  result_confirmed: "confirmed by the arbiter",
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
    <ol id={id} className={cx("flex flex-col gap-0.5 font-mono text-[11px] text-ink-2", className)}>
      {events.map((event) => (
        <li key={event.id}>
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
