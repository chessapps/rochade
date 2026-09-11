import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { renderAt, stubApi } from "../test-utils";
import { NewSection } from "./NewSection";

const T = "t1";

const tournament = {
  id: T, name: "Club Open", city: "", federation: "", start_date: null, end_date: null,
  manager: "gacrux", manager_label: "Rochade (Gacrux engine)", native: true, join_code: null, sections: [],
};

describe("NewSection", () => {
  it("opens a section with the default tie-breaks and a drawn colour", async () => {
    const user = userEvent.setup();
    const calls = stubApi({
      GET: { [`/api/tournaments/${T}`]: tournament },
      POST: {
        [`/api/tournaments/${T}/sections`]: {
          section_id: "sA", name: "Open", declared_rounds: 7,
          tiebreaks: ["PTS", "BH/C1", "BH", "SB"], top_board_colour: "black", drawn_by_lot: true,
        },
      },
    });
    renderAt(`/t/${T}/sections/new`, "/t/:tournamentId/sections/new", <NewSection />);

    await user.type(await screen.findByLabelText(/Name/), "Open");
    const rounds = screen.getByLabelText("Rounds");
    await user.clear(rounds);
    await user.type(rounds, "7");
    // Points first and fixed; the rest can be reordered and pruned.
    const order = screen.getByRole("list", { name: "tie-break order" });
    expect(order).toHaveTextContent(/1\.\s*Points/);
    await user.click(screen.getByRole("button", { name: "remove SB" }));
    await user.click(screen.getByRole("button", { name: "move BH up" }));
    await user.click(screen.getByRole("button", { name: "Open the section" }));

    await waitFor(() => expect(calls.some((c) => c.method === "POST")).toBe(true));
    expect(calls.find((c) => c.method === "POST")!.body).toEqual({
      name: "Open",
      declared_rounds: 7,
      tiebreaks: ["PTS", "BH", "BH/C1"],
      top_board_colour: null,
    });
    expect(await screen.findByText(/black on board one, drawn by lot/)).toBeInTheDocument();
  });
});
