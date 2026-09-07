import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

const TOURNAMENT = "11111111-2222-3333-4444-555555555555";

const joinWithCode = vi.fn();
const fetchBoards = vi.fn(async () => ({ tournament_name: "Test Open", boards: [] }));

vi.mock("./api", () => ({
  joinWithCode: (code: string) => joinWithCode(code),
  fetchBoards: () => fetchBoards(),
  submitClaim: vi.fn(async () => ({ status: "accepted" })),
}));

describe("a phone with no QR code", () => {
  beforeEach(() => {
    localStorage.clear();
    joinWithCode.mockReset();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("joins with a typed code, keeps the credential and moves on", async () => {
    joinWithCode.mockResolvedValue({
      tournament_id: TOURNAMENT,
      tournament_name: "Test Open",
      device_id: "d1",
      label: "code K7QW2M",
      token: "secret-token",
      expires_at: "2026-10-03T22:00:00Z",
    });

    render(<App />);
    const field = screen.getByLabelText(/type the code/i);
    await userEvent.type(field, "k7qw2m");
    // Typed in any case, shown as the arbiter reads it out.
    expect(field).toHaveValue("K7QW2M");

    await userEvent.click(screen.getByRole("button", { name: "Join" }));

    await waitFor(() => expect(localStorage.getItem("seebach.device-token")).toBe("secret-token"));
    expect(localStorage.getItem("seebach.tournament-id")).toBe(TOURNAMENT);
    expect(joinWithCode).toHaveBeenCalledWith("K7QW2M");
    // The screen moves on without a page reload, which would drop the queue.
    await waitFor(() => expect(screen.queryByLabelText(/type the code/i)).not.toBeInTheDocument());
  });

  it("says so when the code opens nothing, and keeps no credential", async () => {
    joinWithCode.mockRejectedValue(new Error("That code does not open anything."));

    render(<App />);
    await userEvent.type(screen.getByLabelText(/type the code/i), "ZZZZZZ");
    await userEvent.click(screen.getByRole("button", { name: "Join" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/does not open anything/i);
    expect(localStorage.getItem("seebach.device-token")).toBeNull();
    expect(screen.getByRole("button", { name: "Join" })).toBeEnabled();
  });

  it("will not send a code too short to be one", async () => {
    render(<App />);
    await userEvent.type(screen.getByLabelText(/type the code/i), "AB");

    expect(screen.getByRole("button", { name: "Join" })).toBeDisabled();
    expect(joinWithCode).not.toHaveBeenCalled();
  });
});
