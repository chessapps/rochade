import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { PlayerList, TournamentDetail } from "../api";
import { renderAt, stubApi } from "../test-utils";
import { Players } from "./Players";

const T = "t1";

function tournament(native = true): TournamentDetail {
  return {
    id: T,
    name: "Club Open",
    city: "",
    federation: "",
    start_date: null,
    end_date: null,
    manager: native ? "gacrux" : "swiss_manager",
    manager_label: native ? "Rochade (Gacrux engine)" : "Swiss-Manager",
    native,
    join_code: null,
    sections: [
      {
        id: "sA",
        name: "A",
        manager: native ? "gacrux" : "swiss_manager",
        manager_label: native ? "Rochade (Gacrux engine)" : "Swiss-Manager",
        native,
        players: 2,
        declared_rounds: 5,
        rounds: [],
      },
    ],
  };
}

function list(editable = true, seeded = false): PlayerList {
  return {
    section_id: "sA",
    section_name: "A",
    editable,
    seeded,
    rounds_held: seeded ? 1 : 0,
    players: [
      { id: "p1", start_rank: 1, name: "Baumann, Lukas", title: "FM", rating: 2201, federation: "SUI", fide_id: "", sex: "m", birth_date: "", withdrawn_from_round: null, points: null, rank: null },
      { id: "p2", start_rank: 2, name: "Chen, Wei", title: "", rating: null, federation: "", fide_id: "", sex: "", birth_date: "", withdrawn_from_round: 2, points: null, rank: null },
    ],
  };
}

describe("Players", () => {
  it("lists the section's players with their status", async () => {
    stubApi({ GET: { [`/api/tournaments/${T}`]: tournament(), "/api/sections/sA/players": list() } });
    renderAt(`/t/${T}/players`, "/t/:tournamentId/players", <Players />);
    expect(await screen.findByText("Baumann, Lukas")).toBeInTheDocument();
    expect(screen.getByText("withdrawn from round 2")).toBeInTheDocument();
    expect(screen.getByText(/1 player, 1 withdrawn/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add player…" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reinstate" })).toBeInTheDocument();
  });

  it("adds a player through the dialog", async () => {
    const user = userEvent.setup();
    const calls = stubApi({
      GET: { [`/api/tournaments/${T}`]: tournament(), "/api/sections/sA/players": list() },
      POST: {
        "/api/sections/sA/players": (_path: string, init?: { body?: unknown }) => ({
          ...(init?.body as object),
          id: "p3",
          start_rank: 3,
          withdrawn_from_round: null,
          points: null,
          rank: null,
        }),
      },
    });
    renderAt(`/t/${T}/players`, "/t/:tournamentId/players", <Players />);
    await user.click(await screen.findByRole("button", { name: "Add player…" }));
    const dialog = screen.getByRole("dialog", { name: /Add a player to section A/ });
    await user.type(within(dialog).getByLabelText(/^Name/), "Dubois, Elise");
    await user.type(within(dialog).getByLabelText(/^Rating/), "2098");
    await user.click(within(dialog).getByRole("button", { name: "Add" }));

    await waitFor(() => expect(calls.some((c) => c.method === "POST")).toBe(true));
    const body = calls.find((c) => c.method === "POST")!.body as Record<string, unknown>;
    expect(body.name).toBe("Dubois, Elise");
    expect(body.rating).toBe(2098);
    expect(await screen.findByText(/entered as number 3/)).toBeInTheDocument();
  });

  it("is read-only for a manager's tournament", async () => {
    stubApi({ GET: { [`/api/tournaments/${T}`]: tournament(false), "/api/sections/sA/players": list(false) } });
    renderAt(`/t/${T}/players`, "/t/:tournamentId/players", <Players />);
    expect(await screen.findByText("Baumann, Lukas")).toBeInTheDocument();
    expect(screen.getByText(/Read-only: this list comes from Swiss-Manager/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Add player…" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Withdraw/ })).not.toBeInTheDocument();
  });

  it("withdraws a player from the next unpaired round", async () => {
    const user = userEvent.setup();
    const calls = stubApi({
      GET: { [`/api/tournaments/${T}`]: tournament(), "/api/sections/sA/players": list(true, true) },
      POST: { "/api/players/p1/withdraw": { ...list().players[0]!, withdrawn_from_round: 2 } },
    });
    renderAt(`/t/${T}/players`, "/t/:tournamentId/players", <Players />);
    await user.click(await screen.findByRole("button", { name: "Withdraw…" }));
    const dialog = screen.getByRole("dialog", { name: /Withdraw Baumann, Lukas\?/ });
    await user.click(within(dialog).getByRole("button", { name: "Withdraw from round 2" }));
    await waitFor(() => expect(calls.some((c) => c.path === "/api/players/p1/withdraw")).toBe(true));
    expect(calls.find((c) => c.path === "/api/players/p1/withdraw")!.body).toEqual({ from_round: null, note: "" });
  });
});
