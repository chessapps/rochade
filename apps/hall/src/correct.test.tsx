import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

const TOURNAMENT = "11111111-2222-3333-4444-555555555555";

const submitClaim = vi.fn(async (_claim: unknown) => ({ status: "accepted" as const }));
const fetchBoards = vi.fn(async () => ({
  tournament_id: TOURNAMENT,
  tournament_name: "Test Open",
  generated_at: new Date().toISOString(),
  open_rounds: [1],
  boards: [
    {
      game_id: "g1",
      section_id: "s1",
      section_name: "A",
      round_number: 1,
      board: 1,
      white_name: "Müller, Hans",
      black_name: "Schneider, Anna",
      white_result: " ",
      state: "empty",
      is_bye: false,
      entered: false,
    },
  ],
}));

vi.mock("./api", () => ({
  joinWithCode: vi.fn(),
  fetchBoards: () => fetchBoards(),
  submitClaim: (claim: unknown) => submitClaim(claim),
}));

describe("correcting a sent result", () => {
  beforeEach(() => {
    localStorage.setItem("seebach.device-token", "t");
    localStorage.setItem("seebach.tournament-id", TOURNAMENT);
    submitClaim.mockClear();
  });

  it("sends a second claim for the same board and says it was a correction", async () => {
    render(<App />);
    await userEvent.click(await screen.findByRole("button", { name: /Board 1,/ }));
    await userEvent.click(screen.getByRole("button", { name: /White wins/ }));
    await screen.findByText("Result sent");

    await userEvent.click(screen.getByRole("button", { name: /Correct it/ }));
    expect(screen.getByText("Tap the right result to replace it")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Draw/ }));
    await screen.findByText("Correction sent");

    await waitFor(() => expect(submitClaim).toHaveBeenCalledTimes(2));
    const sent = submitClaim.mock.calls.map(
      ([claim]) => claim as { gameId: string; result: string },
    );
    expect(sent.map((c) => c.result)).toEqual(["white_win", "draw"]);
    expect(sent.every((c) => c.gameId === "g1")).toBe(true);
  });
});
