import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { BoardDetail, RoundDetail, TournamentDetail } from "../api";
import { renderAt, stubApi } from "../test-utils";
import { RoundBoard } from "./RoundBoard";

const T = "t1";
const R = "r1";

function board(n: number, overrides: Partial<BoardDetail> = {}): BoardDetail {
  return {
    game_id: `g${n}`,
    board: n,
    white_rank: n,
    white_name: `White${n},Anna`,
    black_rank: n + 10,
    black_name: `Black${n},Ben`,
    white_result: " ",
    black_result: " ",
    disputed_white_result: null,
    state: "empty",
    is_bye: false,
    updated_at: "2026-09-02T12:00:00Z",
    ...overrides,
  };
}

function round(state: RoundDetail["state"] = "open"): RoundDetail {
  return {
    id: R,
    number: 3,
    state,
    section_id: "s1",
    section_name: "A",
    source_filename: "FIDE_Export.TXT",
    imported_at: "2026-09-02T11:00:00Z",
    released_at: null,
    exported_at: null,
    boards: [
      board(1, { state: "confirmed", white_result: "1", black_result: "0" }),
      board(2, { state: "claimed", white_result: "=", black_result: "=" }),
      board(3, { state: "disputed", white_result: "1", black_result: "0", disputed_white_result: "0" }),
      board(4),
      board(5, { is_bye: true, black_rank: null, black_name: null, white_result: "U", state: "confirmed" }),
    ],
  };
}

function tournament(state: RoundDetail["state"] = "open", counts = { empty: 1, claimed: 1, disputed: 1, confirmed: 1 }): TournamentDetail {
  return {
    id: T,
    name: "Test Open",
    city: "",
    federation: "",
    start_date: null,
    end_date: null,
    sections: [
      {
        id: "s1",
        name: "A",
        manager: "swiss_manager",
        manager_label: "Swiss-Manager",
        players: 9,
        declared_rounds: 5,
        rounds: [
          {
            id: R,
            number: 3,
            state,
            boards: 4,
            byes: 1,
            ...counts,
            imported_at: "2026-09-02T11:00:00Z",
            released_at: null,
            exported_at: null,
          },
        ],
      },
    ],
  };
}

function mount(path = `/t/${T}/rounds/${R}`, detail = round(), tour = tournament()) {
  const calls = stubApi({
    GET: {
      [`/api/rounds/${R}/events`]: [],
      [`/api/rounds/${R}`]: detail,
      [`/api/tournaments/${T}`]: tour,
    },
    PUT: { "/api/games/": { game_id: "g", state: "confirmed", white_result: "1", black_result: "0" } },
    POST: { "/api/games/": { game_id: "g", state: "confirmed", white_result: "=", black_result: "=" } },
  });
  renderAt(path, "/t/:tournamentId/rounds/:roundId", <RoundBoard />);
  return calls;
}

describe("RoundBoard", () => {
  it("opens on the boards that need the arbiter while the round is open", async () => {
    mount();
    expect(await screen.findByText("Section A · Round 3")).toBeInTheDocument();
    const rows = screen.getAllByRole("listitem");
    expect(rows.map((r) => r.getAttribute("data-game-id"))).toEqual(["g3", "g4"]);
    expect(screen.getByRole("tab", { name: /Attention/ })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText(/Two phones disagree/)).toBeInTheDocument();
  });

  it("the All filter shows every board including the bye, in board order", async () => {
    mount(`/t/${T}/rounds/${R}?filter=all`);
    await screen.findByText("Section A · Round 3");
    const rows = screen.getAllByRole("listitem");
    expect(rows).toHaveLength(5);
    expect(within(rows[4]!).getByText("1 · bye")).toBeInTheDocument();
    // The bye has no buttons: it is the manager's, not ours.
    expect(within(rows[4]!).queryByRole("group", { name: "set result" })).toBeNull();
  });

  it("a result button writes both codes and confirms the board", async () => {
    const calls = mount(`/t/${T}/rounds/${R}?filter=all`);
    await screen.findByText("Section A · Round 3");
    const empty = screen.getAllByRole("listitem")[3]!;
    await userEvent.click(within(empty).getByRole("button", { name: "0:1" }));
    await waitFor(() => expect(calls.some((c) => c.method === "PUT")).toBe(true));
    const put = calls.find((c) => c.method === "PUT")!;
    expect(put.path).toBe("/api/games/g4/result");
    expect(put.body).toEqual({ white_result: "0", black_result: "1", note: "" });
  });

  it("forfeits are one tap further away", async () => {
    const calls = mount(`/t/${T}/rounds/${R}?filter=all`);
    await screen.findByText("Section A · Round 3");
    const empty = screen.getAllByRole("listitem")[3]!;
    expect(within(empty).queryByRole("button", { name: "+:−" })).toBeNull();
    await userEvent.click(within(empty).getByRole("button", { name: "forfeit…" }));
    await userEvent.click(within(empty).getByRole("button", { name: "+:−" }));
    await waitFor(() => expect(calls.some((c) => c.method === "PUT")).toBe(true));
    expect(calls.find((c) => c.method === "PUT")!.body).toEqual({ white_result: "+", black_result: "-", note: "" });
  });

  it("a disputed board is resolved, not overwritten, and no side is pre-lit", async () => {
    const calls = mount();
    await screen.findByText("Section A · Round 3");
    const disputed = screen.getAllByRole("listitem")[0]!;
    for (const name of ["1:0", "½:½", "0:1"]) {
      expect(within(disputed).getByRole("button", { name })).toHaveAttribute("aria-pressed", "false");
    }
    await userEvent.click(within(disputed).getByRole("button", { name: "½:½" }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST")).toBe(true));
    const post = calls.find((c) => c.method === "POST")!;
    expect(post.path).toBe("/api/games/g3/resolve");
    expect(post.body).toEqual({ result: "draw", note: "" });
  });

  it("keys set the focused board and are ignored inside the search box", async () => {
    const calls = mount(`/t/${T}/rounds/${R}?filter=all`);
    await screen.findByText("Section A · Round 3");
    const rows = screen.getAllByRole("listitem");
    rows[3]!.focus();
    await userEvent.keyboard("1");
    await waitFor(() => expect(calls.some((c) => c.method === "PUT")).toBe(true));
    expect(calls.find((c) => c.method === "PUT")!.body).toEqual({ white_result: "1", black_result: "0", note: "" });

    const before = calls.length;
    await userEvent.type(screen.getByLabelText("search boards"), "1");
    expect(calls.filter((c) => c.method !== "GET").length).toBe(calls.slice(0, before).filter((c) => c.method !== "GET").length);
  });

  it("searching by number or name narrows the list", async () => {
    mount(`/t/${T}/rounds/${R}?filter=all`);
    await screen.findByText("Section A · Round 3");
    await userEvent.type(screen.getByLabelText("search boards"), "2");
    expect(screen.getAllByRole("listitem")).toHaveLength(1);
    await userEvent.clear(screen.getByLabelText("search boards"));
    await userEvent.type(screen.getByLabelText("search boards"), "black4");
    expect(screen.getAllByRole("listitem")).toHaveLength(1);
    expect(screen.getByText("White4,Anna")).toBeInTheDocument();
  });

  it("the footer asks before releasing with boards still open, and lists them", async () => {
    mount();
    await screen.findByText("Section A · Round 3");
    await userEvent.click(screen.getByRole("button", { name: "Release anyway…" }));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText(/Empty: boards 4/)).toBeInTheDocument();
    expect(within(dialog).getByText(/Disputed: boards 3/)).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Release anyway" })).toBeDisabled();
    await userEvent.click(within(dialog).getByRole("checkbox"));
    expect(within(dialog).getByRole("button", { name: "Release anyway" })).toBeEnabled();
  });

  it("a frozen round has no buttons and shows the hand-off", async () => {
    stubApi({
      GET: {
        [`/api/rounds/${R}/events`]: [],
        [`/api/rounds/${R}/export`]: {
          round_id: R,
          round_number: 3,
          filename: "A-round3.txt",
          content: "x",
          manager: "swiss_manager",
          manager_label: "Swiss-Manager",
          file_format: "pairing file",
          next_step: "Extras → Daten Import/Export",
          boards_written: 4,
          boards_left_blank: [],
          forced: false,
        },
        [`/api/rounds/${R}`]: { ...round("exported"), exported_at: "2026-09-02T13:00:00Z" },
        [`/api/tournaments/${T}`]: tournament("exported"),
      },
    });
    renderAt(`/t/${T}/rounds/${R}`, "/t/:tournamentId/rounds/:roundId", <RoundBoard />);
    expect(await screen.findByText(/Now in Swiss-Manager/)).toBeInTheDocument();
    expect(screen.getByText(/Daten Import\/Export/)).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: "set result" })).toBeNull();
    expect(screen.getByRole("link", { name: "Import round 4" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Release/ })).toBeNull();
  });
});
