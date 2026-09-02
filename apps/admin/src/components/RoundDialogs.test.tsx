import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { RoundSummary } from "../api";
import { renderAt, stubApi } from "../test-utils";
import { ExportDialog, ReleaseDialog } from "./RoundDialogs";

const round: RoundSummary = {
  id: "r1",
  number: 2,
  state: "confirmed",
  boards: 4,
  byes: 0,
  empty: 0,
  claimed: 0,
  disputed: 0,
  confirmed: 4,
  imported_at: null,
  released_at: "2026-09-02T12:00:00Z",
  exported_at: null,
};

const exported = {
  round_id: "r1",
  round_number: 2,
  filename: "A-round2.txt",
  content: "Runde;Brett",
  manager: "swiss_manager",
  manager_label: "Swiss-Manager",
  file_format: "pairing file",
  next_step: "Extras → Daten Import/Export",
  boards_written: 4,
  boards_left_blank: [],
  forced: false,
};

describe("ExportDialog", () => {
  it("exports once however often the button is hit, downloads, and moves to the board", async () => {
    // The server is slow; the arbiter is not.
    let finish: (value: typeof exported) => void = () => undefined;
    const calls = stubApi({
      POST: {
        "/api/rounds/r1/export": () => new Promise<typeof exported>((resolve) => (finish = resolve)),
      },
    });
    const clicked = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    // jsdom has neither; a spread of URL would lose its constructor, which the router needs.
    URL.createObjectURL = () => "blob:x";
    URL.revokeObjectURL = () => undefined;

    renderAt(
      "/t/t1",
      "/t/:tournamentId",
      <ExportDialog round={round} tournamentId="t1" managerLabel="Swiss-Manager" open onClose={() => undefined} />,
    );
    const button = screen.getByRole("button", { name: "Export and freeze" });
    await userEvent.click(button);
    await userEvent.click(button);
    await userEvent.click(button);
    expect(calls.filter((c) => c.method === "POST")).toHaveLength(1);
    expect(calls[0]!.body).toEqual({ force: false });
    finish(exported);
    await waitFor(() => expect(clicked).toHaveBeenCalledTimes(1));
    expect(await screen.findByTestId("elsewhere")).toBeInTheDocument();
  });

  it("says what goes blank when the round was forced", () => {
    stubApi({});
    renderAt(
      "/t/t1",
      "/t/:tournamentId",
      <ExportDialog
        round={{ ...round, empty: 2, disputed: 1 }}
        tournamentId="t1"
        managerLabel="Vega"
        open
        onClose={() => undefined}
      />,
    );
    expect(screen.getByText(/2 boards with no result and 1 disputed board go into the file blank/)).toBeInTheDocument();
  });
});

describe("ReleaseDialog", () => {
  it("releases a ready round without a checkbox and reports what was confirmed", async () => {
    const calls = stubApi({
      POST: {
        "/api/rounds/r1/release": { round_id: "r1", round_number: 2, state: "confirmed", confirmed: 4, forced: false },
      },
    });
    const onClose = vi.fn();
    renderAt(
      "/t/t1",
      "/t/:tournamentId",
      <ReleaseDialog round={{ ...round, state: "open", claimed: 4, confirmed: 0 }} tournamentId="t1" open onClose={onClose} />,
    );
    expect(screen.queryByRole("checkbox")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Release" }));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(calls[0]!.body).toEqual({ force: false, note: "" });
    expect(screen.getByText("Round 2 released: 4 results confirmed.")).toBeInTheDocument();
  });

  it("shows the API's refusal inside the dialog", async () => {
    stubApi({ POST: { "/api/rounds/r1/release": new Error("this round has already been exported") } });
    renderAt(
      "/t/t1",
      "/t/:tournamentId",
      <ReleaseDialog round={{ ...round, state: "open" }} tournamentId="t1" open onClose={() => undefined} />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Release" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("already been exported");
  });
});
