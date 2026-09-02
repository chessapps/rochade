import type { BoardDetail, RoundSummary, SectionSummary } from "./api";
import {
  changedBoards,
  countBoards,
  defaultFilter,
  filterBoards,
  matchesQuery,
  nextAction,
} from "./boards";

function board(overrides: Partial<BoardDetail> & { board: number }): BoardDetail {
  return {
    game_id: `g${overrides.board}`,
    white_rank: overrides.board,
    white_name: "Müller,Anna",
    black_rank: overrides.board + 10,
    black_name: "Baumann,Lukas",
    white_result: " ",
    black_result: " ",
    disputed_white_result: null,
    state: "empty",
    is_bye: false,
    updated_at: "2026-09-02T12:00:00Z",
    ...overrides,
  };
}

const boards: BoardDetail[] = [
  board({ board: 3, state: "confirmed", white_result: "1", black_result: "0" }),
  board({ board: 1, state: "disputed", white_result: "1", disputed_white_result: "0" }),
  board({ board: 2, state: "claimed", white_result: "=", black_result: "=" }),
  board({ board: 4 }),
  board({ board: 5, is_bye: true, black_rank: null, black_name: null, white_result: "U" }),
];

describe("filterBoards", () => {
  it("attention is what the arbiter has to touch, in board order", () => {
    expect(filterBoards(boards, "attention", "").map((b) => b.board)).toEqual([1, 4]);
  });

  it("the bye is never attention, whatever its state", () => {
    const bye = board({ board: 9, is_bye: true, black_rank: null, black_name: null });
    expect(filterBoards([bye], "attention", "")).toEqual([]);
    expect(filterBoards([bye], "all", "")).toHaveLength(1);
  });

  it("entered and confirmed pick their states", () => {
    expect(filterBoards(boards, "entered", "").map((b) => b.board)).toEqual([2]);
    expect(filterBoards(boards, "confirmed", "").map((b) => b.board)).toEqual([3]);
  });
});

describe("matchesQuery", () => {
  it("matches either name, case-insensitively", () => {
    expect(matchesQuery(boards[0]!, "baum")).toBe(true);
    expect(matchesQuery(boards[0]!, "MÜLL")).toBe(true);
    expect(matchesQuery(boards[0]!, "schmidt")).toBe(false);
  });

  it("a number is a board number", () => {
    expect(matchesQuery(boards[0]!, "3")).toBe(true);
    expect(matchesQuery(boards[0]!, "13")).toBe(false);
  });
});

describe("countBoards", () => {
  it("counts by state and keeps byes apart", () => {
    expect(countBoards(boards)).toEqual({
      boards: 4,
      byes: 1,
      empty: 1,
      claimed: 1,
      disputed: 1,
      confirmed: 1,
    });
  });
});

describe("changedBoards", () => {
  it("lights up rows that moved since the last look and nothing on first load", () => {
    expect(changedBoards(undefined, boards).size).toBe(0);
    const later = boards.map((b) =>
      b.board === 4 ? { ...b, state: "claimed" as const, updated_at: "2026-09-02T12:01:00Z" } : b,
    );
    expect([...changedBoards(boards, later)]).toEqual(["g4"]);
  });
});

describe("defaultFilter", () => {
  it("looks for trouble while open, at the record afterwards", () => {
    expect(defaultFilter("open")).toBe("attention");
    expect(defaultFilter("confirmed")).toBe("all");
    expect(defaultFilter("exported")).toBe("all");
  });
});

describe("nextAction", () => {
  const round = (
    number: number,
    state: RoundSummary["state"],
    empty = 0,
    disputed = 0,
  ): RoundSummary => ({
    id: `r${number}`,
    number,
    state,
    boards: 4,
    byes: 1,
    empty,
    claimed: 0,
    disputed,
    confirmed: 0,
    imported_at: null,
    released_at: null,
    exported_at: null,
  });
  const section = (rounds: RoundSummary[]): SectionSummary => ({
    id: "s",
    name: "A",
    manager: "swiss_manager",
    manager_label: "Swiss-Manager",
    players: 9,
    declared_rounds: 5,
    rounds,
  });

  it("starts with importing round 1", () => {
    expect(nextAction(section([]))).toEqual({ kind: "import", round_number: 1 });
  });

  it("follows the loop on the highest round", () => {
    expect(nextAction(section([round(1, "exported"), round(2, "open", 2, 0)])).kind).toBe("fix");
    expect(nextAction(section([round(2, "open")])).kind).toBe("release");
    expect(nextAction(section([round(2, "confirmed")])).kind).toBe("export");
    expect(nextAction(section([round(2, "exported"), round(1, "exported")]))).toEqual({
      kind: "import",
      round_number: 3,
    });
  });
});
