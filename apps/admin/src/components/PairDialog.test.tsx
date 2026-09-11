import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { PairingPlan } from "../api";
import { renderAt, stubApi } from "../test-utils";
import { PairDialog } from "./PairDialog";

const T = "t1";

function plan(overrides: Partial<PairingPlan> = {}): PairingPlan {
  return {
    section_id: "sA",
    section_name: "A",
    round_number: 1,
    declared_rounds: 5,
    seeds: true,
    players_in: 5,
    boards: [
      { board: 1, white_rank: 1, white_name: "Baumann, Lukas", black_rank: 3, black_name: "Dubois, Elise" },
      { board: 2, white_rank: 4, white_name: "Egger, Tobias", black_rank: 2, black_name: "Chen, Wei" },
    ],
    byes: [{ board: 3, start_rank: 5, name: "Fischer, Jonas", result: "U" }],
    withdrawn: [],
    warnings: [],
    blocked_by: [],
    ...overrides,
  };
}

function mount(preview: PairingPlan) {
  const calls = stubApi({
    GET: {
      "/api/sections/sA/players": {
        section_id: "sA", section_name: "A", editable: true, seeded: false, rounds_held: 0,
        players: [
          { id: "p1", start_rank: 1, name: "Baumann, Lukas", title: "", rating: 2201, federation: "", fide_id: "", sex: "", birth_date: "", withdrawn_from_round: null, points: null, rank: null },
          { id: "p2", start_rank: 2, name: "Chen, Wei", title: "", rating: 2150, federation: "", fide_id: "", sex: "", birth_date: "", withdrawn_from_round: null, points: null, rank: null },
        ],
      },
    },
    POST: {
      "/api/sections/sA/pairings/preview": preview,
      "/api/sections/sA/pairings": { section_id: "sA", round_id: "r1", round_number: 1, boards: 2, byes: 1, seeded: true, previous_round_closed: null },
    },
  });
  renderAt(
    `/t/${T}`,
    "/t/:tournamentId",
    <PairDialog section={{ id: "sA", name: "A" }} tournamentId={T} roundNumber={1} open onClose={() => {}} />,
  );
  return calls;
}

describe("PairDialog", () => {
  it("shows the boards and the bye before pairing, then pairs", async () => {
    const user = userEvent.setup();
    const calls = mount(plan());
    const dialog = await screen.findByRole("dialog", { name: /Pair round 1 of section A/ });
    const table = await within(dialog).findByRole("table", { name: "round 1 boards" });
    expect(within(table).getAllByRole("row")).toHaveLength(3);
    expect(within(dialog).getByText(/Fischer, Jonas \(5\): bye, one point/)).toBeInTheDocument();
    expect(within(dialog).getByText(/seeds the start numbers/)).toBeInTheDocument();

    await user.click(within(dialog).getByRole("button", { name: "Pair round 1" }));
    await waitFor(() => expect(calls.some((c) => c.path === "/api/sections/sA/pairings")).toBe(true));
    expect(await screen.findByText(/Round 1 paired: 2 boards, 1 bye/)).toBeInTheDocument();
  });

  it("refuses to pair while the plan is blocked", async () => {
    mount(plan({ boards: [], byes: [], blocked_by: ["round 1 is still open for entry; release it first"] }));
    const dialog = await screen.findByRole("dialog");
    expect(await within(dialog).findByText(/still open for entry/)).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Pair round 1" })).toBeDisabled();
  });

  it("marks a player absent and previews again with it", async () => {
    const user = userEvent.setup();
    const calls = mount(plan());
    const dialog = await screen.findByRole("dialog");
    await within(dialog).findByRole("table");
    await user.selectOptions(await within(dialog).findByLabelText("mark a player absent"), "2");
    await user.click(within(dialog).getByRole("button", { name: "Add" }));
    await user.selectOptions(within(dialog).getByLabelText("points for Chen, Wei"), "H");
    await waitFor(() => {
      const previews = calls.filter((c) => c.path === "/api/sections/sA/pairings/preview");
      expect(previews.at(-1)!.body).toEqual({ absent: [{ start_rank: 2, result: "H" }] });
    });
    await user.click(within(dialog).getByRole("button", { name: "Pair round 1" }));
    await waitFor(() =>
      expect(calls.find((c) => c.path === "/api/sections/sA/pairings")!.body).toEqual({
        absent: [{ start_rank: 2, result: "H" }],
      }),
    );
  });
});
