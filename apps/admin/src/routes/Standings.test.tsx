import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { renderAt, stubApi } from "../test-utils";
import { Standings, score } from "./Standings";

const T = "t1";

const standings = {
  tournament_id: T,
  tournament_name: "Test Open",
  sections: [
    {
      section_id: "s1",
      section_name: "A",
      manager_label: "Swiss-Manager",
    native: false,
      after_round: 3,
      rounds_held: 4,
      stale: false,
      tiebreak_names: ["Buchholz"],
      tiebreak_columns: 2,
      rows: [
        { rank: 1, start_rank: 4, name: "Keller,Urs", title: "FM", federation: "SUI", rating: 2300, points: 2.5, tiebreaks: [13.5, 9] },
        { rank: 2, start_rank: 1, name: "Brunner,Livia", title: "WGM", federation: "SUI", rating: 2447, points: 2.5, tiebreaks: [12, 8.5] },
      ],
    },
  ],
};

const tournament = {
  id: T, name: "Test Open", city: "", federation: "", start_date: null, end_date: null, join_code: null,
  sections: [{ id: "s1", name: "A", manager: "swiss_manager", manager_label: "Swiss-Manager",
    native: false, players: 14, declared_rounds: 5, rounds: [] }],
};

describe("Standings", () => {
  it("shows the manager's table with named and numbered tiebreaks", async () => {
    stubApi({ GET: { [`/api/tournaments/${T}/standings`]: standings, [`/api/tournaments/${T}`]: tournament } });
    renderAt(`/t/${T}/standings`, "/t/:tournamentId/standings", <Standings />);

    expect(await screen.findByText("Section A")).toBeInTheDocument();
    expect(screen.getByText(/after round 3 · Swiss-Manager/)).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Buchholz" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "TB2" })).toBeInTheDocument();
    const first = screen.getAllByRole("row")[1]!;
    expect(within(first).getByText("Keller,Urs")).toBeInTheDocument();
    expect(within(first).getByText("2½")).toBeInTheDocument();
    expect(within(first).getByText("13½")).toBeInTheDocument();
  });

  it("lets the arbiter name the tiebreak columns", async () => {
    const calls = stubApi({
      GET: { [`/api/tournaments/${T}/standings`]: standings, [`/api/tournaments/${T}`]: tournament },
      PUT: { [`/api/tournaments/${T}/sections/A/tiebreaks`]: { section_name: "A", tiebreak_names: ["Buchholz", "Wins"] } },
    });
    renderAt(`/t/${T}/standings`, "/t/:tournamentId/standings", <Standings />);
    await screen.findByText("Section A");

    await userEvent.click(screen.getByRole("button", { name: "Rename them" }));
    await userEvent.type(screen.getByLabelText("name of tiebreak 2"), "Wins");
    await userEvent.click(screen.getByRole("button", { name: "Save names" }));

    await waitFor(() => expect(calls.some((c) => c.method === "PUT")).toBe(true));
    expect(calls.find((c) => c.method === "PUT")!.body).toEqual({ names: ["Buchholz", "Wins"] });
  });

  it("imports a player list on its own, and refuses the wrong file", async () => {
    const calls = stubApi({
      GET: { [`/api/tournaments/${T}/standings`]: { ...standings, sections: [] }, [`/api/tournaments/${T}`]: tournament },
      POST: {
        [`/api/tournaments/${T}/standings`]: {
          section_name: "A", after_round: 4, players_updated: 14, unknown_start_numbers: [],
          standings: standings.sections[0],
        },
      },
    });
    renderAt(`/t/${T}/standings`, "/t/:tournamentId/standings", <Standings />);
    await screen.findByText("No standings yet");

    const input = screen.getByLabelText("player list file");
    const wrong = new File(["Runde;Brett;IdentW;IdentS;NrW;NrS;ErgW;ErgS;Kontumaz;Erg;Mnr;ErgEloW;ErgEloS\n1;1;0;0;1;2;1;0;;1:0;0;;\n"], "pairings.txt", { type: "text/plain" });
    await userEvent.upload(input, wrong);
    expect(await screen.findByText(/not the player list/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Import standings" })).toBeDisabled();

    const players = new File(["Nr;Nachname;Vorname;Pkt;Wtg1;Rang\n1;Brunner;Livia;3;12;1\n"], "players.txt", { type: "text/plain" });
    await userEvent.upload(input, players);
    await waitFor(() => expect(screen.getByRole("button", { name: "Import standings" })).toBeEnabled());
    await userEvent.click(screen.getByRole("button", { name: "Import standings" }));

    await waitFor(() => expect(calls.some((c) => c.method === "POST")).toBe(true));
    expect(calls.find((c) => c.method === "POST")!.body).toMatchObject({ section_name: "A" });
  });
});

describe("Standings for a tournament on Vega", () => {
  const vegaTournament = {
    ...tournament,
    manager: "vega",
    manager_label: "Vega",
    sections: [{ ...tournament.sections[0], manager: "vega", manager_label: "Vega" }],
  };
  const STANDINGS =
    "TestOpen\r\n - , \r\n\r\nStandings at round 3\r\n\r\n" +
    "Pos   N     NAME                      g | FRtg  NRtg  Fed |  Pts      BH\r\n" +
    "------------------------------------------------------------------------\r\n" +
    "  1   6     Gruber, Sarah             m | 1922     0  AUT |  2.5     5.0\r\n\r\nTie Break legend:\r\nBH : Buchholz\r\n";

  it("asks for standings.txt and takes it", async () => {
    const calls = stubApi({
      GET: { [`/api/tournaments/${T}/standings`]: { ...standings, sections: [] }, [`/api/tournaments/${T}`]: vegaTournament },
      POST: {
        [`/api/tournaments/${T}/standings`]: {
          section_name: "A", after_round: 3, players_updated: 16, unknown_start_numbers: [],
          standings: { ...standings.sections[0], manager_label: "Vega" },
        },
      },
    });
    renderAt(`/t/${T}/standings`, "/t/:tournamentId/standings", <Standings />);
    await screen.findByText("No standings yet");
    expect(await screen.findByText(/standings.txt, in the tournament folder/)).toBeInTheDocument();

    const input = screen.getByLabelText("standings file");
    const wrong = new File(["Nr;Nachname;Vorname;Pkt;Wtg1;Rang\n1;Brunner;Livia;3;12;1\n"], "players.txt", { type: "text/plain" });
    await userEvent.upload(input, wrong);
    expect(await screen.findByText(/not Vega's standings/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Import standings" })).toBeDisabled();

    await userEvent.upload(input, new File([STANDINGS], "standings.txt", { type: "text/plain" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Import standings" })).toBeEnabled());
    await userEvent.click(screen.getByRole("button", { name: "Import standings" }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST")).toBe(true));
    expect(calls.find((c) => c.method === "POST")!.body).toMatchObject({ section_name: "A" });
  });
});

describe("score", () => {
  it("writes halves the way the wall does", () => {
    expect(score(0)).toBe("0");
    expect(score(0.5)).toBe("½");
    expect(score(2.5)).toBe("2½");
    expect(score(13)).toBe("13");
    expect(score(null)).toBe("");
  });
});

describe("Standings for a section Rochade pairs itself", () => {
  const native = {
    ...standings,
    sections: [
      { ...standings.sections[0]!, manager_label: "Rochade (Gacrux engine)", tiebreak_names: ["BH/C1", "SB"], tiebreak_columns: 2 },
    ],
  };
  const nativeTournament = {
    ...tournament,
    manager: "gacrux",
    manager_label: "Rochade (Gacrux engine)",
    native: true,
    sections: [{ ...tournament.sections[0]!, manager: "gacrux", manager_label: "Rochade (Gacrux engine)", native: true }],
  };

  it("labels the tie-break codes, offers a recompute, and has no file to drop", async () => {
    const calls = stubApi({
      GET: { [`/api/tournaments/${T}/standings`]: native, [`/api/tournaments/${T}`]: nativeTournament },
      POST: {
        "/api/sections/s1/standings": {
          computed: false, after_round: 3, reason: "boards without a confirmed result: round 3 board 2", standings: native.sections[0],
        },
      },
    });
    renderAt(`/t/${T}/standings`, "/t/:tournamentId/standings", <Standings />);
    expect(await screen.findByRole("columnheader", { name: "Buchholz Cut 1" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Sonneborn-Berger" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /name them/i })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("player list file")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Recompute" }));
    await waitFor(() => expect(calls.some((c) => c.path === "/api/sections/s1/standings")).toBe(true));
    expect(await screen.findByText(/Not recomputed: boards without a confirmed result/)).toBeInTheDocument();
  });
});
