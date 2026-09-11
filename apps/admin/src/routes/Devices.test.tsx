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
            revoked_at: null,
            last_seen_at: null,
            active: true,
          },
          {
            id: "d0",
            label: "old poster",
            issued_at: "2026-09-01T10:00:00Z",
            revoked_at: "2026-09-01T20:00:00Z",
            last_seen_at: "2026-09-01T19:00:00Z",
            active: false,
          },
        ],
        [`/api/tournaments/${T}`]: { id: T, name: "Test Open", city: "", federation: "", start_date: null, end_date: null, sections: [] },
      },
      POST: {
        [`/api/tournaments/${T}/devices`]: {
          device_id: "d2",
          label: "wall",
          token: "secret",
          qr_payload: "http://localhost/hall/t1#t=secret",
        },
        "/api/devices/d1/revoke": { device_id: "d1", revoked_at: "2026-09-02T12:00:00Z" },
      },
      DELETE: { "/api/devices/d0": { device_id: "d0" } },
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
    const revoked = () => calls.some((c) => c.method === "POST" && c.path.endsWith("/revoke"));
    expect(revoked()).toBe(false);
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Revoke" }));
    await waitFor(() => expect(revoked()).toBe(true));

    // Only the revoked phone offers removal, and removal is a plain DELETE.
    expect(screen.queryByRole("button", { name: /Remove poster/ })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Remove old poster" }));
    await waitFor(() =>
      expect(calls.some((c) => c.method === "DELETE" && c.path === "/api/devices/d0")).toBe(true),
    );
  });
});

describe("TournamentList", () => {
  it("goes straight to the only tournament", async () => {
    stubApi({
      GET: { "/api/tournaments": [{ id: "only", name: "Only Open", city: "", start_date: null, end_date: null, manager: "vega", manager_label: "Vega",
    native: false, role: "owner" }] },
    });
    renderAt("/", "/", <TournamentList />);
    expect(await screen.findByTestId("elsewhere")).toBeInTheDocument();
  });

  it("shows the list when asked for it, even with one tournament", async () => {
    stubApi({
      GET: { "/api/tournaments": [{ id: "only", name: "Only Open", city: "", start_date: null, end_date: null, manager: "vega", manager_label: "Vega",
    native: false, role: "owner" }] },
    });
    renderAt("/?all", "/", <TournamentList />);
    expect(await screen.findByText("Only Open")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "New tournament" })).toBeInTheDocument();
  });

  it("asks which program pairs it, then creates the tournament and moves to it", async () => {
    const calls = stubApi({
      GET: {
        "/api/tournaments": [],
        "/api/managers": [
          { key: "vega", label: "Vega", verified: false, native: false },
          { key: "swiss_manager", label: "Swiss-Manager", verified: true, native: false },
          { key: "gacrux", label: "Rochade (Gacrux engine)", verified: true, native: true },
        ],
      },
      POST: { "/api/tournaments": { id: "new", name: "Club Open" } },
    });
    renderAt("/", "/", <TournamentList />);
    await userEvent.click(await screen.findByRole("button", { name: "Create the first one" }));
    const dialog = screen.getByRole("dialog");
    // Nothing chosen yet: no way forward. Rochade's own program is one of the three.
    const next = within(dialog).getByRole("button", { name: "Continue" });
    expect(next).toBeDisabled();
    expect(await within(dialog).findByRole("radio", { name: /Rochade \(Gacrux engine\)/ })).toBeEnabled();
    await userEvent.click(within(dialog).getByRole("radio", { name: /Swiss-Manager/ }));
    await userEvent.click(next);

    expect(within(dialog).getByRole("button", { name: "Create" })).toBeDisabled();
    await userEvent.type(within(dialog).getByLabelText("Name"), "Club Open");
    await userEvent.type(within(dialog).getByLabelText("Federation"), "sui");
    await userEvent.click(within(dialog).getByRole("button", { name: "Create" }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST")).toBe(true));
    expect(calls.find((c) => c.method === "POST")!.body).toEqual({
      name: "Club Open",
      manager: "swiss_manager",
      city: "",
      federation: "SUI",
      start_date: null,
      end_date: null,
    });
    expect(await screen.findByTestId("elsewhere")).toBeInTheDocument();
  });
});
