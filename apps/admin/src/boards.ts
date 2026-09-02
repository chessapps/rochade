/**
 * Reading a round: which boards need the arbiter, what changed since the last
 * look, and what the next step is. Pure, so the screens stay thin.
 */

import type { BoardDetail, RoundState, RoundSummary, SectionSummary } from "./api";

export type Filter = "all" | "attention" | "entered" | "confirmed";

export const FILTERS: Filter[] = ["all", "attention", "entered", "confirmed"];

export function isFilter(value: string | null): value is Filter {
  return FILTERS.includes(value as Filter);
}

/** While a round is open the arbiter looks for trouble; afterwards, at the record. */
export function defaultFilter(state: RoundState): Filter {
  return state === "open" ? "attention" : "all";
}

export function matchesFilter(board: BoardDetail, filter: Filter): boolean {
  switch (filter) {
    case "all":
      return true;
    case "attention":
      return !board.is_bye && (board.state === "empty" || board.state === "disputed");
    case "entered":
      return board.state === "claimed";
    case "confirmed":
      return board.state === "confirmed";
  }
}

/** A name fragment or a board number. "12" is board 12, not anyone called 12. */
export function matchesQuery(board: BoardDetail, query: string): boolean {
  const needle = query.trim().toLowerCase();
  if (!needle) return true;
  if (/^\d+$/.test(needle)) return board.board === Number(needle);
  return (
    board.white_name.toLowerCase().includes(needle) ||
    (board.black_name ?? "").toLowerCase().includes(needle)
  );
}

export function filterBoards(boards: BoardDetail[], filter: Filter, query: string): BoardDetail[] {
  return boards
    .filter((board) => matchesFilter(board, filter) && matchesQuery(board, query))
    .sort((a, b) => a.board - b.board);
}

export interface Counts {
  boards: number;
  byes: number;
  empty: number;
  claimed: number;
  disputed: number;
  confirmed: number;
}

/** Byes are not boards: nobody enters them and they never need attention. */
export function countBoards(boards: BoardDetail[]): Counts {
  const counts: Counts = { boards: 0, byes: 0, empty: 0, claimed: 0, disputed: 0, confirmed: 0 };
  for (const board of boards) {
    if (board.is_bye) {
      counts.byes += 1;
      continue;
    }
    counts.boards += 1;
    counts[board.state] += 1;
  }
  return counts;
}

export function countsOfRound(round: RoundSummary): Counts {
  return {
    boards: round.boards,
    byes: round.byes,
    empty: round.empty,
    claimed: round.claimed,
    disputed: round.disputed,
    confirmed: round.confirmed,
  };
}

export function filterCount(boards: BoardDetail[], filter: Filter): number {
  return boards.filter((board) => matchesFilter(board, filter)).length;
}

/** Boards whose row should light up: touched since the last look. Nothing on first load. */
export function changedBoards(
  previous: BoardDetail[] | undefined,
  next: BoardDetail[],
): Set<string> {
  const changed = new Set<string>();
  if (!previous) return changed;
  const before = new Map(previous.map((board) => [board.game_id, board]));
  for (const board of next) {
    const was = before.get(board.game_id);
    if (!was || was.updated_at !== board.updated_at || was.state !== board.state) {
      changed.add(board.game_id);
    }
  }
  return changed;
}

export function readyToRelease(round: { empty: number; disputed: number }): boolean {
  return round.empty === 0 && round.disputed === 0;
}

/** The round the section is on: the highest one imported. */
export function currentRound(section: SectionSummary): RoundSummary | null {
  const rounds = section.rounds ?? [];
  return rounds.reduce<RoundSummary | null>(
    (best, round) => (best === null || round.number > best.number ? round : best),
    null,
  );
}

export type NextAction =
  | { kind: "import"; round_number: number }
  | { kind: "fix"; round: RoundSummary }
  | { kind: "release"; round: RoundSummary }
  | { kind: "export"; round: RoundSummary };

/**
 * The one thing to do next for a section. Computed, never chosen: the arbiter
 * should not have to work out which button is the live one.
 */
export function nextAction(section: SectionSummary): NextAction {
  const round = currentRound(section);
  if (round === null) return { kind: "import", round_number: 1 };
  switch (round.state) {
    case "open":
      return readyToRelease(round) ? { kind: "release", round } : { kind: "fix", round };
    case "confirmed":
      return { kind: "export", round };
    case "exported":
      return { kind: "import", round_number: round.number + 1 };
  }
}

/** The stepper's position for a round, 0..3: import → entry → released → exported. */
export function stepOf(round: RoundSummary): number {
  switch (round.state) {
    case "open":
      return 1;
    case "confirmed":
      return 2;
    case "exported":
      return 3;
  }
}
