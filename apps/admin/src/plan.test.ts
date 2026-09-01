import { describe, expect, it } from "vitest";

import type { ImportPlan } from "./api";
import { canImport, headline, needsAcknowledgement, planNotes } from "./plan";

function plan(overrides: Partial<ImportPlan> = {}): ImportPlan {
  return {
    section_name: "A",
    section_exists: true,
    file_round: 2,
    expected_round: 2,
    is_expected_round: true,
    declared_rounds: 5,
    tournament_name: "Seebach Open",
    players_total: 8,
    players_added: [],
    players_removed: [],
    players_renamed: [],
    boards: 4,
    byes: 0,
    disagreements: [],
    claims_carried: [],
    claims_dropped: [],
    unknown_result_codes: [],
    warnings: [],
    blocked_by: [],
    ...overrides,
  } as ImportPlan;
}

describe("reading an import plan", () => {
  it("summarises a clean file in one line", () => {
    expect(headline(plan())).toBe("Round 2: 4 boards, 8 players");
    expect(headline(plan({ boards: 4, byes: 1, players_total: 9 }))).toBe(
      "Round 2: 4 boards and 1 bye, 9 players",
    );
  });

  it("says nothing needs acknowledging when nothing does", () => {
    expect(planNotes(plan())).toEqual([]);
    expect(canImport(plan())).toBe(true);
    expect(needsAcknowledgement(plan())).toBe(false);
  });

  it("treats a changed earlier result as something to read, not an error", () => {
    const notes = planNotes(
      plan({
        disagreements: [
          {
            round_number: 1,
            white_name: "Baumann, Lukas",
            black_name: "Fischer, Jonas",
            ours: "1",
            theirs: "=",
          },
        ],
      }),
    );

    expect(notes).toHaveLength(1);
    expect(notes[0]?.severity).toBe("acknowledge");
    expect(notes[0]?.text).toContain("The manager wins");
    // It does not stop the import -- Vega is authoritative for earlier rounds.
    expect(canImport(plan({ disagreements: notes.length ? undefined : [] }))).toBe(true);
  });

  it("names the entered result a re-pair would drop", () => {
    const notes = planNotes(
      plan({
        claims_dropped: [
          {
            white_name: "Baumann, Lukas",
            black_name: "Fischer, Jonas",
            white_result: "1",
            state: "claimed",
          },
        ],
      }),
    );
    expect(notes[0]?.severity).toBe("acknowledge");
    expect(notes[0]?.text).toContain("stays in the audit log");
  });

  it("blocks on a frozen round and says why", () => {
    const frozen = plan({
      blocked_by: ["round 2 has already been exported to Vega"],
    });
    expect(canImport(frozen)).toBe(false);
    expect(planNotes(frozen)[0]).toEqual({
      severity: "blocking",
      text: "round 2 has already been exported to Vega",
    });
  });

  it("puts blocking notes before everything else", () => {
    const notes = planNotes(
      plan({
        blocked_by: ["out of order"],
        players_added: [{ start_rank: 9, name: "Jenni, Rafael", rating: 1755 }],
        unknown_result_codes: ["Q"],
      }),
    );
    expect(notes.map((note) => note.severity)).toEqual([
      "blocking",
      "acknowledge",
      "informational",
    ]);
  });

  it("flags an unexpected round number", () => {
    const notes = planNotes(
      plan({ file_round: 4, expected_round: 2, is_expected_round: false }),
    );
    expect(notes[0]?.text).toContain("round 2 was expected");
  });
});
