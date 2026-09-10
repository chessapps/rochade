import { screen, within } from "@testing-library/react";

import type { RoundEvent, RoundSummary, TournamentDetail } from "../api";
import { renderAt, stubApi } from "../test-utils";
import { TournamentHome } from "./TournamentHome";

const T = "t1";

function round(id: string, number: number, overrides: Partial<RoundSummary> = {}): RoundSummary {
  return {
    id,
    number,
    state: "open",
    boards: 4,
    byes: 0,
    empty: 0,
    claimed: 0,
    disputed: 0,
    confirmed: 4,
    imported_at: "2026-09-02T11:00:00Z",
    released_at: null,
    exported_at: null,
    ...overrides,
  };
}

function tournament(): TournamentDetail {
  return {
    id: T,
    name: "Test Open",
    city: "Zürich",
    federation: "SUI",
    start_date: "2026-09-02",
    end_date: "2026-09-04",
    sections: [
      {
        id: "sA",
        name: "A",
        manager: "swiss_manager",
        manager_label: "Swiss-Manager",
        players: 9,
        declared_rounds: 5,
        rounds: [
          round("r1", 1, { state: "exported", exported_at: "2026-09-01T18:40:00Z" }),
          round("r3", 3, { empty: 1, claimed: 1, disputed: 1, confirmed: 1 }),
        ],
      },
      {
        id: "sB",
        name: "B",
        manager: "swiss_manager",
        manager_label: "Swiss-Manager",
        players: 6,
        declared_rounds: 5,
        rounds: [round("r2", 2, { state: "exported", boards: 3, confirmed: 3, exported_at: "2026-09-02T12:00:00Z" })],
      },
    ],
  };
}

function event(id: string, action: RoundEvent["action"], board: number, at: string): RoundEvent {
  return {
    id,
    board,
    white_name: `White${board}`,
    black_name: `Black${board}`,
    action,
    actor_kind: "device",
    device_label: "poster",
    at,
    payload: { claimed: "white_win" },
  };
}

function mount() {
  stubApi({
    GET: {
      [`/api/tournaments/${T}/devices`]: [
        { id: "d1", label: "poster", active: true, last_seen_at: "2026-09-02T12:30:00Z", revoked_at: null, issued_at: "2026-09-02T10:00:00Z" },
      ],
      [`/api/tournaments/${T}`]: tournament(),
      "/api/rounds/r3/events": [
        event("e1", "result_claimed", 2, "2026-09-02T12:20:00Z"),
        event("e2", "result_disputed", 3, "2026-09-02T12:30:00Z"),
      ],
      "/api/rounds/r2/events": [],
    },
  });
  renderAt(`/t/${T}`, "/t/:tournamentId", <TournamentHome />);
}

describe("TournamentHome", () => {
  it("lays the tournament out: name, the three numbers, one card per section", async () => {
    mount();
    expect(await screen.findByRole("heading", { level: 1, name: "Test Open" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Section A" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Section B" })).toBeInTheDocument();
    expect(screen.getByText("Results this round")).toBeInTheDocument();
    expect(screen.getByText("Phones admitted")).toBeInTheDocument();
    // Only the open round of A counts for "this round"; B is frozen.
    expect(screen.getByRole("progressbar", { name: "2 of 4 boards entered" })).toBeInTheDocument();
  });

  it("points the dispute metric and the section callout at the boards that need the desk", async () => {
    mount();
    await screen.findByRole("heading", { level: 1, name: "Test Open" });
    const links = screen.getAllByRole("link", { name: /resolve/i });
    expect(links.length).toBeGreaterThan(0);
    for (const link of links) expect(link).toHaveAttribute("href", `/t/${T}/rounds/r3?filter=attention`);
    expect(screen.getByRole("button", { name: /Fix 1 disputed · 1 empty/ })).toBeInTheDocument();
  });

  it("shows where each round stands and what to do next", async () => {
    mount();
    await screen.findByRole("heading", { level: 1, name: "Test Open" });
    expect(screen.getByRole("list", { name: "round 3 progress" })).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "round 2 progress" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Import round 3/ })).toBeInTheDocument();
  });

  it("folds earlier rounds away under the section", async () => {
    mount();
    await screen.findByRole("heading", { level: 1, name: "Test Open" });
    const earlier = screen.getByText(/Earlier rounds \(1 of 5\)/).closest("details")!;
    expect(within(earlier).getByRole("link", { name: "Round 1" })).toHaveAttribute("href", `/t/${T}/rounds/r1`);
    expect(within(earlier).getByText(/Exported/)).toBeInTheDocument();
  });

  it("streams the hall's entries, newest first, with the dispute marked", async () => {
    mount();
    const feed = (await screen.findByRole("heading", { name: /Live hall feed/ })).closest("section")!;
    const items = await within(feed).findAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(within(items[0]!).getByText("DISPUTE")).toBeInTheDocument();
    expect(within(items[0]!).getByText(/Board 3/)).toBeInTheDocument();
    expect(within(items[1]!).getByText(/Board 2/)).toBeInTheDocument();
    expect(within(items[0]!).getByRole("link", { name: /Open the board/ })).toHaveAttribute(
      "href",
      `/t/${T}/rounds/r3?filter=attention`,
    );
  });
});
