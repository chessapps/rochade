import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

const TOURNAMENT = "11111111-2222-3333-4444-555555555555";

const fetchBoards = vi.fn(async () => ({
  tournament_id: TOURNAMENT,
  tournament_name: "Test Open",
  generated_at: new Date().toISOString(),
  open_rounds: [4],
  boards: [],
}));
const fetchStandings = vi.fn(async () => ({
  tournament_id: TOURNAMENT,
  tournament_name: "Test Open",
  sections: [
    {
      section_id: "s1",
      section_name: "A",
      manager_label: "Swiss-Manager",
      after_round: 3,
      rounds_held: 4,
      stale: false,
      tiebreak_names: ["Buchholz"],
      tiebreak_columns: 1,
      rows: [
        { rank: 1, start_rank: 4, name: "Keller, Urs", title: "", federation: "SUI", rating: 2300, points: 2.5, tiebreaks: [13.5] },
        { rank: 2, start_rank: 1, name: "Brunner, Livia", title: "", federation: "SUI", rating: 2447, points: 2, tiebreaks: [12] },
      ],
    },
  ],
}));

vi.mock("./api", () => ({
  joinWithCode: vi.fn(),
  fetchBoards: () => fetchBoards(),
  fetchStandings: () => fetchStandings(),
  submitClaim: vi.fn(async () => ({ status: "accepted" })),
}));

describe("the standings tab", () => {
  beforeEach(() => {
    localStorage.setItem("seebach.device-token", "t");
    localStorage.setItem("seebach.tournament-id", TOURNAMENT);
  });

  it("shows the manager's table after the round it is current for", async () => {
    render(<App />);
    await userEvent.click(await screen.findByRole("tab", { name: "Standings" }));

    expect(screen.getByText("after round 3")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Buchholz" })).toBeInTheDocument();
    const rows = screen.getAllByRole("row");
    expect(rows[1]).toHaveTextContent("1Keller, Urs2½13½");
    expect(rows[2]).toHaveTextContent("2Brunner, Livia212");
  });
});
