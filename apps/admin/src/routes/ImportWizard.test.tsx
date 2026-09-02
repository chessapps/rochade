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
    reads_format: "trf16",
    writes_format: "trf16",
    exports_unplayed_round: "unverified",
    merges_on_import: "unverified",
    verified: false,
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
    result_codes_out: [],
    export_howto: "Extras → FIDE-Daten-Export TRF16",
    import_howto: "",
    notes: [],
  },
];

const tournament: TournamentDetail = {
  id: T,
  name: "Test Open",
  city: "",
  federation: "",
  start_date: null,
  end_date: null,
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

async function chooseFile() {
  const input = document.querySelector<HTMLInputElement>('input[type="file"]')!;
  await userEvent.upload(input, new File(["012 Test Open\n001    1 ..."], "r1.trf", { type: "text/plain" }));
  await screen.findByText("r1.trf");
}

describe("ImportWizard", () => {
  it("defaults to the verified manager and previews before writing anything", async () => {
    const calls = mount(plan());
    expect(await screen.findByLabelText("Tournament manager")).toHaveValue("swiss_manager");
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
    await screen.findByLabelText("Tournament manager");
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
      manager: "swiss_manager",
      filename: "r1.trf",
      force: false,
    });
    // Then straight to the round.
    expect(await screen.findByTestId("elsewhere")).toBeInTheDocument();
  });

  it("a blocked plan asks again before importing over the block", async () => {
    const calls = mount(plan({ blocked_by: ["round 1 is already exported"] }));
    await screen.findByLabelText("Tournament manager");
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
