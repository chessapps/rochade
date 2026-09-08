/**
 * Two taps from the sketch:
 *
 *   board list (sticky search)  ->  result choice, which sends  ->  done
 *
 * Black on white, ruled like a printed pairing sheet, two columns on a tablet: this is read on a
 * five-year-old Android in a badly lit hall by someone who has just played four
 * hours of chess and wants to leave. A white and a black disc mark who has
 * which colour, everywhere a name appears. There is no confirm step; the choice
 * screen shows both names by colour so the tap itself is the check.
 */

import type { ReactNode } from "react";

import type { Board, SectionStandings } from "./api";
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

export type View = "boards" | "standings";

/** Boards | Standings, at the top of the list. */
export function ViewTabs({
  view,
  onView,
  hasStandings,
}: {
  view: View;
  onView: (view: View) => void;
  hasStandings: boolean;
}) {
  if (!hasStandings) return null;
  const tabs: { key: View; label: string }[] = [
    { key: "boards", label: "Boards" },
    { key: "standings", label: "Standings" },
  ];
  return (
    <div role="tablist" className="mt-1.5 grid grid-cols-2 gap-1 rounded-md border-2 border-ink p-0.5">
      {tabs.map((tab) => (
        <button
          key={tab.key}
          type="button"
          role="tab"
          aria-selected={view === tab.key}
          onClick={() => onView(tab.key)}
          className={[
            "rounded py-1.5 text-sm font-semibold",
            view === tab.key ? "bg-ink text-paper" : "text-ink active:bg-neutral-100",
          ].join(" ")}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

export function BoardListScreen({
  boards,
  query,
  onQuery,
  onPick,
  pendingKeys,
  offline,
  queued,
  tournamentName,
  tabs,
}: {
  boards: Board[];
  query: string;
  onQuery: (value: string) => void;
  onPick: (board: Board) => void;
  pendingKeys: Set<string>;
  offline: boolean;
  queued: number;
  tournamentName?: string;
  tabs?: ReactNode;
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
        {tabs}
      </header>

      <div className="flex-1 overflow-y-auto pb-6">
        {groups.map((group) => (
          <section key={group.key}>
            {!oneGroup && (
              <h2 className="border-b border-ink bg-neutral-100 px-3 py-1 text-[11px] font-semibold tracking-wide text-mute uppercase">
                {group.section} · round {group.round}
              </h2>
            )}
            <ul className="grid grid-cols-1 sm:grid-cols-2 sm:gap-x-4 sm:px-3">
              {group.boards.map((board) => (
                <BoardRow
                  key={board.game_id}
                  board={board}
                  pending={pendingKeys.has(board.game_id)}
                  onPick={onPick}
                />
              ))}
            </ul>
          </section>
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

type Status = "open" | "sending" | "entered" | "bye";

function statusOf(board: Board, pending: boolean): Status {
  if (board.is_bye) return "bye";
  if (pending) return "sending";
  if (board.entered) return "entered";
  return "open";
}

/** The piece colour, as it sits on the board: a white disc and a black one. */
function Piece({ colour }: { colour: "white" | "black" }) {
  return (
    <span
      aria-hidden="true"
      className={[
        "inline-block h-3.5 w-3.5 shrink-0 rounded-full border-2 border-ink",
        colour === "white" ? "bg-paper" : "bg-ink",
      ].join(" ")}
    />
  );
}

const STATUS_LABEL: Record<Status, string> = {
  open: "open",
  sending: "sending",
  entered: "entered",
  bye: "bye",
};

function BoardRow({
  board,
  pending,
  onPick,
}: {
  board: Board;
  pending: boolean;
  onPick: (board: Board) => void;
}) {
  const status = statusOf(board, pending);
  const open = status !== "bye";
  const inner = (
    <>
      <span className="w-8 shrink-0 text-right text-base font-semibold tabular-nums">
        {board.board}
      </span>
      <span className="min-w-0 flex-1 leading-tight">
        <span className="flex items-center gap-2">
          <Piece colour="white" />
          <span className="truncate">{board.white_name}</span>
        </span>
        <span className="flex items-center gap-2">
          <Piece colour="black" />
          <span className="truncate">{board.black_name ?? "bye"}</span>
        </span>
      </span>
      <span className="shrink-0 self-center text-right">
        <BoardCell board={board} status={status} />
      </span>
    </>
  );
  const row = "flex w-full items-start gap-2 border-b border-rule px-2 py-1.5 text-left";
  return (
    <li className="min-w-0">
      {open ? (
        <button
          type="button"
          onClick={() => onPick(board)}
          aria-label={`Board ${board.board}, ${board.white_name} against ${board.black_name}, ${STATUS_LABEL[status]}`}
          className={`${row} active:bg-neutral-100 focus-visible:bg-neutral-100 focus-visible:outline-none`}
        >
          {inner}
        </button>
      ) : (
        <div className={`${row} text-mute`}>{inner}</div>
      )}
    </li>
  );
}

function BoardCell({ board, status }: { board: Board; status: Status }) {
  if (status === "sending") return <span className="text-xs text-mute">sending…</span>;
  if (status === "bye") return <span className="text-xs">bye</span>;
  if (status === "entered") {
    return (
      <span className="font-semibold tabular-nums whitespace-nowrap">
        {SHEET_SCORE[board.white_result] ?? board.white_result}
      </span>
    );
  }
  return <span className="text-xl leading-none text-mute">›</span>;
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
  busy,
  correcting = false,
  onChoose,
  onBack,
}: {
  board: Board;
  busy: boolean;
  correcting?: boolean;
  onChoose: (result: GameResult) => void;
  onBack: () => void;
}) {
  return (
    <div className="mx-auto flex min-h-full w-full max-w-xl flex-col gap-4 overflow-y-auto p-3">
      <BoardHeading board={board} />
      <Players board={board} />
      <p className="text-lg font-semibold">
        {correcting ? "Tap the right result to replace it" : "Tap the result to send it"}
      </p>
      <div className="flex flex-col gap-2">
        {(Object.keys(RESULT_LABELS) as GameResult[]).map((result) => (
          <button
            key={result}
            type="button"
            onClick={() => onChoose(result)}
            disabled={busy}
            className="group flex items-center gap-4 rounded-md border-2 border-ink px-4 py-3 text-left focus-visible:ring-2 focus-visible:ring-ink focus-visible:ring-offset-2 focus-visible:outline-none active:bg-ink active:text-paper disabled:opacity-50"
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
        <SecondaryButton onClick={onBack} disabled={busy}>
          Back to the list
        </SecondaryButton>
      </div>
    </div>
  );
}

function winnerLine(board: Board, result: GameResult): string {
  if (result === "white_win") return `${board.white_name} wins`;
  if (result === "black_win") return `${board.black_name ?? "black"} wins`;
  return "half a point each";
}

/**
 * The result as it will appear on the pairing sheet: one line per colour,
 * the winner's line inverted so the eye lands on it even at arm's length.
 */
function ScoreSheet({ board, result }: { board: Board; result: GameResult }) {
  const rows: { colour: "white" | "black"; name: string; score: string; wins: boolean }[] = [
    {
      colour: "white" as const,
      name: board.white_name,
      score: RESULT_LABELS[result].white,
      wins: result === "white_win",
    },
    {
      colour: "black" as const,
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
                "w-[5.5rem] py-3 pr-2 pl-3 text-xs font-semibold tracking-wide uppercase",
                row.wins ? "text-neutral-300" : "text-mute",
              ].join(" ")}
            >
              <span className="flex items-center gap-1.5">
                <span
                  aria-hidden="true"
                  className={[
                    "inline-block h-3.5 w-3.5 shrink-0 rounded-full border-2",
                    row.colour === "white" ? "border-ink bg-paper" : "border-paper bg-ink",
                    row.wins && row.colour === "white" ? "border-paper" : "",
                  ].join(" ")}
                />
                {row.colour}
              </span>
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
  corrected,
  onCorrect,
  onDone,
}: {
  board: Board;
  result: GameResult;
  queued: boolean;
  corrected: boolean;
  onCorrect: () => void;
  onDone: () => void;
}) {
  const title = queued ? "Saved on this phone" : corrected ? "Correction sent" : "Result sent";
  return (
    <div className="mx-auto flex min-h-full w-full max-w-xl flex-col gap-4 overflow-y-auto p-3">
      <BoardHeading board={board} />
      <div className="flex items-center gap-3">
        <span
          aria-hidden="true"
          className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-ink text-2xl font-bold text-paper"
        >
          {queued ? "…" : "✓"}
        </span>
        <div className="leading-tight">
          <p className="text-2xl font-bold">{title}</p>
          <p className="text-sm text-mute">
            {queued
              ? "It will send itself as soon as there is a network."
              : "The arbiter confirms it at the end of the round."}
          </p>
        </div>
      </div>
      <ScoreSheet board={board} result={result} />
      <div className="flex flex-col gap-2 pt-2">
        <button
          type="button"
          onClick={onDone}
          className="w-full rounded-md bg-ink py-4 text-xl font-bold text-paper focus-visible:ring-2 focus-visible:ring-ink focus-visible:ring-offset-2 focus-visible:outline-none active:bg-neutral-800"
        >
          Done
        </button>
        <SecondaryButton onClick={onCorrect}>Wrong result? Correct it</SecondaryButton>
      </div>
    </div>
  );
}

/** Which name has which colour, so "White wins" is never a guess. */
function Players({ board }: { board: Board }) {
  return (
    <dl className="grid grid-cols-[4.5rem_1fr] gap-y-1 text-lg leading-tight">
      <dt className="flex items-center gap-1.5 self-center text-xs font-semibold tracking-wide text-mute uppercase">
        <Piece colour="white" />
        White
      </dt>
      <dd className="font-semibold break-words">{board.white_name}</dd>
      <dt className="flex items-center gap-1.5 self-center text-xs font-semibold tracking-wide text-mute uppercase">
        <Piece colour="black" />
        Black
      </dt>
      <dd className="font-semibold break-words">{board.black_name ?? "bye"}</dd>
    </dl>
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

/** "2½", as it is written on the wall. */
export function score(value: number | null | undefined): string {
  if (value === null || value === undefined) return "";
  const whole = Math.floor(value);
  const half = value - whole >= 0.5;
  if (whole === 0 && half) return "½";
  return `${whole}${half ? "½" : ""}`;
}

/**
 * The manager's table, not ours: the points, tiebreaks and ranks arrive with
 * its player list and are shown as they came. Dense, like the printout.
 */
export function StandingsScreen({
  sections,
  query,
  onQuery,
  tournamentName,
  tabs,
}: {
  sections: SectionStandings[];
  query: string;
  onQuery: (value: string) => void;
  tournamentName?: string;
  tabs?: ReactNode;
}) {
  const needle = query.trim().toLowerCase();
  return (
    <div className="flex h-full flex-col">
      <header className="sticky top-0 z-10 border-b-2 border-ink bg-paper px-3 pt-2 pb-2">
        <p className="truncate text-xs font-semibold tracking-wide uppercase">
          {tournamentName ?? "Standings"}
        </p>
        <input
          value={query}
          onChange={(event) => onQuery(event.target.value)}
          placeholder="Your name"
          aria-label="Search the standings"
          autoComplete="off"
          autoCapitalize="off"
          spellCheck={false}
          className="mt-1.5 w-full rounded-md border-2 border-ink bg-paper px-3 py-2 text-base placeholder:text-mute focus:outline-none focus:ring-2 focus:ring-ink focus:ring-offset-1"
        />
        {tabs}
      </header>
      <div className="flex-1 overflow-y-auto pb-6">
        {sections.map((section) => {
          const columns = Math.max(section.tiebreak_columns, section.tiebreak_names.length);
          const names = Array.from(
            { length: columns },
            (_, i) => section.tiebreak_names[i] || `TB${i + 1}`,
          );
          const rows = needle
            ? section.rows.filter((row) => row.name.toLowerCase().includes(needle))
            : section.rows;
          return (
            <section key={section.section_id}>
              <h2 className="flex items-baseline justify-between border-b border-ink bg-neutral-100 px-3 py-1 text-[11px] font-semibold tracking-wide text-mute uppercase">
                <span>{sections.length > 1 ? section.section_name : "Standings"}</span>
                <span>
                  {section.after_round === 0 ? "starting order" : `after round ${section.after_round}`}
                </span>
              </h2>
              <table className="w-full table-fixed border-collapse text-[15px]">
                <thead>
                  <tr className="border-b border-rule text-[11px] tracking-wide text-mute uppercase">
                    <th className="w-9 py-1 pl-2 text-right">#</th>
                    <th className="py-1 pl-2 text-left">Name</th>
                    <th className="w-11 py-1 pr-1 text-right">Pts</th>
                    {names.map((name) => (
                      <th key={name} className="w-12 truncate py-1 pr-2 text-right" title={name}>
                        {name}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.start_rank} className="border-b border-rule tabular-nums">
                      <td className="py-1.5 pl-2 text-right font-semibold">{row.rank}</td>
                      <td className="truncate py-1.5 pl-2">{row.name}</td>
                      <td className="py-1.5 pr-1 text-right font-semibold">{score(row.points)}</td>
                      {names.map((name, i) => (
                        <td key={name} className="py-1.5 pr-2 text-right text-mute">
                          {score(row.tiebreaks[i])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              {rows.length === 0 && (
                <p className="px-4 py-6 text-center text-mute">No player matches that.</p>
              )}
            </section>
          );
        })}
      </div>
    </div>
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
