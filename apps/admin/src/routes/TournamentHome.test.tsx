import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { api, type RoundEvent, type RoundSummary, type TournamentDetail } from "../api";
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
    published: false,
    slug: null,
    federation: "SUI",
    start_date: "2026-09-02",
    end_date: "2026-09-04",
    manager: "swiss_manager",
    manager_label: "Swiss-Manager",
    native: false,
    sections: [
      {
        id: "sA",
        name: "A",
        manager: "swiss_manager",
        manager_label: "Swiss-Manager",
    native: false,
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
    native: false,
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

function mount(role: "owner" | "arbiter" = "owner") {
  const calls = stubApi({
    DELETE: {
      [`/api/tournaments/${T}`]: (_path: string, init?: { params?: { query?: { confirm_name?: string } } }) => {
        const query = init?.params?.query;
        if (query?.confirm_name !== "Test Open") return new Error("the name does not match");
        return { id: T, name: "Test Open" };
      },
    },
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
      // Last: a bare prefix would otherwise answer every tournament route.
      "/api/tournaments": [
        { id: T, name: "Test Open", city: "Zürich", federation: "SUI", start_date: null, end_date: null, manager: "swiss_manager", manager_label: "Swiss-Manager",
    native: false, role },
      ],
    },
  });
  renderAt(`/t/${T}`, "/t/:tournamentId", <TournamentHome />);
  return calls;
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

  it("lets only the owner delete, and only after typing the name back", async () => {
    const user = userEvent.setup();
    const calls = mount();
    await screen.findByRole("heading", { level: 1, name: "Test Open" });
    await user.click(await screen.findByRole("button", { name: /Delete…/ }));

    const dialog = screen.getByRole("dialog", { name: "Delete this tournament?" });
    const confirm = within(dialog).getByRole("button", { name: "Delete tournament" });
    expect(confirm).toBeDisabled();

    const input = within(dialog).getByLabelText(/Type the tournament's name/);
    await user.type(input, "Test Ope");
    expect(confirm).toBeDisabled();
    await user.type(input, "n");
    expect(confirm).toBeEnabled();
    await user.click(confirm);

    await waitFor(() =>
      expect(calls.some((c) => c.method === "DELETE" && c.path === `/api/tournaments/${T}`)).toBe(true),
    );
  });

  it("publishes the tournament from the command bar and shows the public link", async () => {
    const user = userEvent.setup();
    const calls = mount("arbiter");
    vi.spyOn(api, "PUT").mockImplementation((async (_path: string, init?: { body?: { published: boolean; slug: string | null } }) => {
      calls.push({ method: "PUT", path: `/api/tournaments/${T}/publication`, body: init?.body });
      return { data: { published: init?.body?.published ?? false, slug: "test-open" }, response: new Response(null, { status: 200 }) };
    }) as never);
    await screen.findByRole("heading", { level: 1, name: "Test Open" });
    await user.click(screen.getByRole("button", { name: /Publish…/ }));

    const dialog = screen.getByRole("dialog", { name: "Publish this tournament" });
    await user.type(within(dialog).getByLabelText("public address"), "open-2026");
    await user.click(within(dialog).getByRole("button", { name: "Publish" }));

    await waitFor(() =>
      expect(calls.find((c) => c.method === "PUT")?.body).toEqual({ published: true, slug: "open-2026" }),
    );
  });

  it("hides the delete button from an arbiter", async () => {
    mount("arbiter");
    await screen.findByRole("heading", { level: 1, name: "Test Open" });
    await screen.findByText("Phones admitted");
    expect(screen.queryByRole("button", { name: /Delete…/ })).not.toBeInTheDocument();
  });
});

describe("TournamentHome for a tournament Rochade pairs itself", () => {
  function native(rounds: RoundSummary[], players = 9): TournamentDetail {
    const base = tournament();
    return {
      ...base,
      manager: "gacrux",
      manager_label: "Rochade (Gacrux engine)",
      native: true,
      sections: [
        { ...base.sections[0]!, manager: "gacrux", manager_label: "Rochade (Gacrux engine)", native: true, players, rounds },
      ],
    };
  }

  function mountNative(detail: TournamentDetail) {
    const calls = stubApi({
      GET: {
        [`/api/tournaments/${T}/devices`]: [],
        [`/api/tournaments/${T}`]: detail,
        "/api/rounds/": [],
        "/api/tournaments": [
          { id: T, name: "Test Open", city: "", federation: "", start_date: null, end_date: null, manager: "gacrux", manager_label: "Rochade (Gacrux engine)", native: true, role: "owner" },
        ],
      },
      POST: {
        "/api/sections/sA/pairings/preview": {
          section_id: "sA", section_name: "A", round_number: 1, declared_rounds: 5, seeds: true, players_in: 9,
          boards: [{ board: 1, white_rank: 1, white_name: "Baumann, Lukas", black_rank: 5, black_name: "Fischer, Jonas" }],
          byes: [], withdrawn: [], warnings: [], blocked_by: [],
        },
      },
    });
    renderAt(`/t/${T}`, "/t/:tournamentId", <TournamentHome />);
    return calls;
  }

  it("offers players and a new section instead of an import, and pairs from the card", async () => {
    const user = userEvent.setup();
    mountNative(native([]));
    await screen.findByRole("heading", { level: 1, name: "Test Open" });
    expect(screen.queryByRole("link", { name: /Import a round/ })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /New section/ })).toHaveAttribute("href", `/t/${T}/sections/new`);
    expect(screen.getByRole("link", { name: "Players" })).toHaveAttribute("href", `/t/${T}/players`);
    expect(screen.queryByText("Round file sync")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Pair round 1/ }));
    const dialog = await screen.findByRole("dialog", { name: /Pair round 1 of section A/ });
    expect(await within(dialog).findByText("Baumann, Lukas")).toBeInTheDocument();
  });

  it("asks for players first when the section is empty", async () => {
    mountNative(native([], 0));
    await screen.findByRole("heading", { level: 1, name: "Test Open" });
    expect(screen.getByRole("button", { name: /Enter players/ })).toBeInTheDocument();
  });

  it("names the steps paired and closed, and pairs the next round on a released one", async () => {
    mountNative(native([round("r1", 1, { state: "exported", exported_at: "2026-09-02T18:40:00Z" }), round("r2", 2, { state: "confirmed" })]));
    await screen.findByRole("heading", { level: 1, name: "Test Open" });
    const stepper = screen.getByRole("list", { name: "round 2 progress" });
    expect(within(stepper).getByText(/1\. Paired/)).toBeInTheDocument();
    expect(within(stepper).getByText(/4\. Closed/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Pair round 3/ })).toBeInTheDocument();
    const earlier = screen.getByText(/Earlier rounds/).closest("details")!;
    expect(within(earlier).getByText(/Closed/)).toBeInTheDocument();
    expect(within(earlier).queryByRole("button", { name: /Download/ })).not.toBeInTheDocument();
  });
});
