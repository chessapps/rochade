import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { renderAt, stubApi } from "../test-utils";
import { Devices } from "./Devices";
import { TournamentList } from "./TournamentList";

const T = "t1";

describe("Devices", () => {
  it("issuing shows a real QR code once, and revoking asks first", async () => {
    const calls = stubApi({
      GET: {
        [`/api/tournaments/${T}/devices`]: [
          {
            id: "d1",
            label: "poster",
            issued_at: "2026-09-02T10:00:00Z",
            expires_at: "2026-09-02T23:00:00Z",
            revoked_at: null,
            last_seen_at: null,
            active: true,
          },
        ],
        [`/api/tournaments/${T}`]: { id: T, name: "Test Open", city: "", federation: "", start_date: null, end_date: null, sections: [] },
      },
      POST: {
        [`/api/tournaments/${T}/devices`]: {
          device_id: "d2",
          label: "wall",
          token: "secret",
          expires_at: "2026-09-02T23:00:00Z",
          qr_payload: "http://localhost/hall/t1#t=secret",
        },
      },
      DELETE: { "/api/devices/d1": { device_id: "d1", revoked_at: "2026-09-02T12:00:00Z" } },
    });
    renderAt(`/t/${T}/devices`, "/t/:tournamentId/devices", <Devices />);
    expect(await screen.findByText("poster")).toBeInTheDocument();

    await userEvent.type(screen.getByPlaceholderText(/poster/), "wall");
    await userEvent.click(screen.getByRole("button", { name: "Issue a QR code" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByRole("img", { name: /QR code/ }).tagName.toLowerCase()).toBe("svg");
    expect(within(dialog).getByText(/Shown once/)).toBeInTheDocument();
    expect(calls.find((c) => c.method === "POST")!.body).toMatchObject({ label: "wall" });
    await userEvent.click(within(dialog).getByRole("button", { name: "Done" }));

    await userEvent.click(screen.getByRole("button", { name: "Revoke" }));
    expect(calls.some((c) => c.method === "DELETE")).toBe(false);
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Revoke" }));
    await waitFor(() => expect(calls.some((c) => c.method === "DELETE")).toBe(true));
  });
});

describe("TournamentList", () => {
  it("goes straight to the only tournament", async () => {
    stubApi({
      GET: { "/api/tournaments": [{ id: "only", name: "Only Open", city: "", start_date: null, end_date: null, role: "owner" }] },
    });
    renderAt("/", "/", <TournamentList />);
    expect(await screen.findByTestId("elsewhere")).toBeInTheDocument();
  });

  it("creates a tournament from the empty state and moves to it", async () => {
    const calls = stubApi({
      GET: { "/api/tournaments": [] },
      POST: { "/api/tournaments": { id: "new", name: "Club Open" } },
    });
    renderAt("/", "/", <TournamentList />);
    await userEvent.click(await screen.findByRole("button", { name: "Create the first one" }));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByRole("button", { name: "Create" })).toBeDisabled();
    await userEvent.type(within(dialog).getByLabelText("Name"), "Club Open");
    await userEvent.type(within(dialog).getByLabelText("Federation"), "sui");
    await userEvent.click(within(dialog).getByRole("button", { name: "Create" }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST")).toBe(true));
    expect(calls.find((c) => c.method === "POST")!.body).toEqual({
      name: "Club Open",
      city: "",
      federation: "SUI",
      start_date: null,
      end_date: null,
    });
    expect(await screen.findByTestId("elsewhere")).toBeInTheDocument();
  });
});
