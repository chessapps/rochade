import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { ImportPlan, ManagerSummary, TournamentDetail } from "../api";
import { renderAt, stubApi } from "../test-utils";
import { ImportWizard } from "./ImportWizard";

const T = "t1";

const managers: ManagerSummary[] = [
  {
    key: "vega",
    label: "Vega",
    reads_format: "vega tournament folder",
    writes_format: "trf16 for Vega",
    exports_unplayed_round: "yes",
    merges_on_import: "yes",
    verified: true,
    native: false,
    result_codes_out: [],
    export_howto: "",
    import_howto: "",
    notes: [],
  },
  {
    key: "swiss_manager",
    label: "Swiss-Manager",
    reads_format: "trf16",
    writes_format: "pairing file",
    exports_unplayed_round: "yes",
    merges_on_import: "yes",
    verified: true,
    native: false,
    result_codes_out: [],
    export_howto: "Extras → FIDE-Daten-Export TRF16",
    import_howto: "",
    notes: [],
  },
];

const tournament: TournamentDetail = {
  id: T,
  name: "Test Open",
  published: false,
  slug: null,
  city: "",
  federation: "",
  start_date: null,
  end_date: null,
  manager: "swiss_manager",
  manager_label: "Swiss-Manager",
    native: false,
  sections: [],
};

function plan(overrides: Partial<ImportPlan> = {}): ImportPlan {
  return {
    section_name: "A",
    section_exists: false,
    file_round: 1,
    expected_round: 1,
    is_expected_round: true,
    declared_rounds: 5,
    tournament_name: "Test Open",
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
  };
}

function mount(previewed: ImportPlan) {
  const calls = stubApi({
    GET: { "/api/managers": managers, [`/api/tournaments/${T}`]: tournament },
    POST: {
      [`/api/tournaments/${T}/imports/preview`]: previewed,
      [`/api/tournaments/${T}/imports`]: {
        section_id: "s1",
        round_id: "r1",
        round_number: previewed.file_round,
        boards: 4,
        byes: 0,
        claims_carried: 0,
        claims_dropped: 0,
      },
    },
  });
  renderAt(`/t/${T}/import`, "/t/:tournamentId/import", <ImportWizard />);
  return calls;
}

const CRLF = String.fromCharCode(13, 10);
const PLAYERS = [
  "Nr;Name;Titel;Identnr;EloNat;EloInt;Geburt;Fed;Sex;Nachname;Vorname",
  "1;Brunner Livia;WGM;;0;2447;01.06.1992;SUI;W;Brunner;Livia",
  "",
].join(CRLF);
const PAIRINGS = [
  "Runde;Brett;IdentW;IdentS;NrW;NrS;ErgW;ErgS;Kontumaz;Erg;Mnr;ErgEloW;ErgEloS",
  "1;1;0;0;1;51;0;0;;0:0;0;;",
  "",
].join(CRLF);

async function upload(name: string, content: string) {
  const input = document.querySelector<HTMLInputElement>('input[type="file"]')!;
  await userEvent.upload(input, new File([content], name, { type: "text/plain" }));
  await screen.findByText(name);
}

async function chooseFile() {
  const input = document.querySelector<HTMLInputElement>('input[type="file"]')!;
  await userEvent.upload(input, new File(["012 Test Open\n001    1 ..."], "r1.trf", { type: "text/plain" }));
  await screen.findByText("r1.trf");
}

describe("ImportWizard", () => {
  it("names the tournament's program and previews before writing anything", async () => {
    const calls = mount(plan());
    expect(await screen.findByText("Swiss-Manager")).toBeInTheDocument();
    expect(screen.queryByLabelText("Tournament manager")).toBeNull();
    expect(screen.getByText(/Extras → FIDE-Daten-Export/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Preview the changes" })).toBeDisabled();
    await chooseFile();
    await userEvent.click(screen.getByRole("button", { name: "Preview the changes" }));
    expect(await screen.findByText("What round 1 changes")).toBeInTheDocument();
    expect(calls.filter((c) => c.method === "POST").map((c) => c.path)).toEqual([
      `/api/tournaments/${T}/imports/preview`,
    ]);
    // Never forced: a forced preview would hide the one block that matters.
    expect(calls.find((c) => c.method === "POST")!.body).toMatchObject({ force: false });
    expect(screen.getByText(/Nothing to note/)).toBeInTheDocument();
  });

  it("a plan that must be read gates the import behind the checkbox", async () => {
    const calls = mount(
      plan({
        section_exists: true,
        file_round: 3,
        expected_round: 3,
        disagreements: [
          { round_number: 2, white_name: "A", black_name: "B", ours: "1", theirs: "0" },
        ],
        players_added: [{ start_rank: 9, name: "New,Player", rating: null }],
      }),
    );
    await screen.findByText("Swiss-Manager");
    await chooseFile();
    await userEvent.click(screen.getByRole("button", { name: "Preview the changes" }));
    await screen.findByText("Read before importing");
    expect(screen.getByText(/the manager says "0"/)).toBeInTheDocument();
    // The roster diff is folded away so the disagreement is not buried.
    expect(screen.queryByText(/New,Player/)).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: /Show 1 detail/ }));
    expect(screen.getByText(/New,Player/)).toBeInTheDocument();

    const importButton = screen.getByRole("button", { name: "Import round 3" });
    expect(importButton).toBeDisabled();
    await userEvent.click(screen.getByLabelText("I have read the changes above."));
    await userEvent.click(importButton);
    await waitFor(() =>
      expect(calls.some((c) => c.path === `/api/tournaments/${T}/imports`)).toBe(true),
    );
    expect(calls.find((c) => c.path === `/api/tournaments/${T}/imports`)!.body).toMatchObject({
      section_name: "A",
      filename: "r1.trf",
      force: false,
    });
    // Then straight to the round.
    expect(await screen.findByTestId("elsewhere")).toBeInTheDocument();
  });

  it("a blocked plan asks again before importing over the block", async () => {
    const calls = mount(plan({ blocked_by: ["round 1 is already exported"] }));
    await screen.findByText("Swiss-Manager");
    await chooseFile();
    await userEvent.click(screen.getByRole("button", { name: "Preview the changes" }));
    await screen.findByText("Why this should not be imported");
    await userEvent.click(screen.getByRole("button", { name: "Import anyway…" }));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText("round 1 is already exported")).toBeInTheDocument();
    expect(calls.some((c) => c.path === `/api/tournaments/${T}/imports`)).toBe(false);
    await userEvent.click(within(dialog).getByRole("button", { name: "Import anyway" }));
    await waitFor(() =>
      expect(calls.find((c) => c.path === `/api/tournaments/${T}/imports`)?.body).toMatchObject({
        force: true,
      }),
    );
  });
});

describe("the two files Swiss-Manager writes", () => {
  it("holds the import until both are there, and says which is missing", async () => {
    mount(plan());
    await screen.findByText("Swiss-Manager");

    await upload("pairings.txt", PAIRINGS);
    expect(screen.getByRole("button", { name: "Preview the changes" })).toBeDisabled();
    expect(screen.getByText(/Add the players file/)).toBeInTheDocument();

    await upload("players.txt", PLAYERS);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Preview the changes" })).toBeEnabled(),
    );
  });

  it("sends both as one body, players first", async () => {
    const calls = mount(plan());
    await screen.findByText("Swiss-Manager");
    await upload("players.txt", PLAYERS);
    await upload("pairings.txt", PAIRINGS);
    await userEvent.click(screen.getByRole("button", { name: "Preview the changes" }));

    await screen.findByText("What round 1 changes");
    const previewed = calls.find((c) => c.method === "POST")!.body as { content: string };
    expect(previewed.content.indexOf("Nr;Name")).toBeLessThan(
      previewed.content.indexOf("Runde;Brett"),
    );

    // The name recorded against the round is the file that carries it.
    await userEvent.click(screen.getByRole("button", { name: "Import round 1" }));
    await waitFor(() => expect(calls.filter((c) => c.method === "POST")).toHaveLength(2));
    const imported = calls.filter((c) => c.method === "POST")[1]!.body as { filename: string };
    expect(imported.filename).toBe("pairings.txt");
  });
});

const CROSSTABLE =
  "Rochade M0 Spike\r\nRochade - 05/09/2026, 07/09/2026\r\n\r\n Cross Table at round 2\r\n\r\n" +
  "  N NAME                 Rtg   T  Fed  Pts |   1     2  \r\n" +
  "--------------------------------------------------------\r\n" +
  "  1 Baumann, Lukas       2201  FM SUI  1.5 | +W5   =B2   \r\n";
const SORTED_PAIRS =
  "Rochade M0 Spike: Pairing of round 3 sorted by name\n\n====\n" +
  "Baumann, Lukas        plays with white VS         Dubois, Elise          in board    2\n";

describe("a tournament on Vega", () => {
  it("takes the two folder files and asks how many rounds the tournament has", async () => {
    const calls = stubApi({
      GET: {
        "/api/managers": managers,
        [`/api/tournaments/${T}`]: { ...tournament, manager: "vega", manager_label: "Vega", sections: [] },
      },
      POST: { [`/api/tournaments/${T}/imports/preview`]: plan() },
    });
    renderAt(`/t/${T}/import`, "/t/:tournamentId/import", <ImportWizard />);
    await screen.findByText("Vega");
    expect(screen.queryByText(/Not yet verified/)).not.toBeInTheDocument();
    await upload("SortedPairs.txt", SORTED_PAIRS);
    expect(screen.getByText(/Add engine26.trf/)).toBeInTheDocument();
    await upload("crosstable.txt", CROSSTABLE);
    const preview = screen.getByRole("button", { name: "Preview the changes" });
    expect(preview).toBeDisabled();
    await userEvent.type(screen.getByLabelText("rounds in the tournament"), "5");
    await userEvent.click(preview);
    await waitFor(() => expect(calls.some((c) => c.method === "POST")).toBe(true));
    const body = calls.find((c) => c.method === "POST")!.body as { declared_rounds: number; content: string };
    expect(body.declared_rounds).toBe(5);
    expect(body.content.indexOf("Cross Table")).toBeLessThan(body.content.indexOf("Pairing of round"));
  });

  it("does not ask for the rounds when the engine file carries them", async () => {
    const ENGINE =
      "012 TestOpen\r\n142 5\r\n001    1 m FM BaumannLukas                      2201 SUI           0 1990        0.0    1\r\n";
    const calls = stubApi({
      GET: {
        "/api/managers": managers,
        [`/api/tournaments/${T}`]: { ...tournament, manager: "vega", manager_label: "Vega", sections: [] },
      },
      POST: { [`/api/tournaments/${T}/imports/preview`]: plan() },
    });
    renderAt(`/t/${T}/import`, "/t/:tournamentId/import", <ImportWizard />);
    await screen.findByText("Vega");
    await upload("SortedPairs.txt", SORTED_PAIRS);
    expect(screen.getByLabelText("rounds in the tournament")).toBeInTheDocument();
    await upload("engine26.trf", ENGINE);
    expect(screen.queryByLabelText("rounds in the tournament")).not.toBeInTheDocument();
    const preview = screen.getByRole("button", { name: "Preview the changes" });
    expect(preview).toBeEnabled();
    await userEvent.click(preview);
    await waitFor(() => expect(calls.some((c) => c.method === "POST")).toBe(true));
    const body = calls.find((c) => c.method === "POST")!.body as { declared_rounds?: number; content: string };
    expect(body.declared_rounds).toBeUndefined();
    expect(body.content.indexOf("012 TestOpen")).toBeLessThan(body.content.indexOf("Pairing of round"));
  });

  it("refuses Swiss-Manager's text files and asks for the folder files", async () => {
    stubApi({
      GET: {
        "/api/managers": managers,
        [`/api/tournaments/${T}`]: { ...tournament, manager: "vega", manager_label: "Vega" },
      },
    });
    renderAt(`/t/${T}/import`, "/t/:tournamentId/import", <ImportWizard />);
    await screen.findByText("Vega");
    await upload("players.txt", PLAYERS);
    await upload("pairings.txt", PAIRINGS);
    expect(screen.getByText(/this tournament runs on Vega/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Preview the changes" })).toBeDisabled();
  });
});
