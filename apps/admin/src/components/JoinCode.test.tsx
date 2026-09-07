import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { renderAt, stubApi } from "../test-utils";
import { Devices } from "../routes/Devices";

const T = "t1";

function mount(joinCode: string | null) {
  return stubApi({
    GET: {
      [`/api/tournaments/${T}/devices`]: [],
      [`/api/tournaments/${T}`]: {
        id: T,
        name: "Test Open",
        city: "",
        federation: "",
        start_date: null,
        end_date: null,
        join_code: joinCode,
        sections: [],
      },
    },
    POST: { [`/api/tournaments/${T}/join-code`]: { join_code: "K7QW2M" } },
    DELETE: { [`/api/tournaments/${T}/join-code`]: { join_code: null } },
  });
}

describe("the join code", () => {
  it("offers to open joining when there is no code", async () => {
    const calls = mount(null);
    renderAt(`/t/${T}/devices`, "/t/:tournamentId/devices", <Devices />);

    const button = await screen.findByRole("button", { name: "Open joining with a code" });
    expect(screen.queryByText("K7QW2M")).not.toBeInTheDocument();

    await userEvent.click(button);
    await waitFor(() =>
      expect(calls.some((c) => c.method === "POST" && c.path.endsWith("/join-code"))).toBe(true),
    );
  });

  it("shows the code and can close joining again", async () => {
    const calls = mount("K7QW2M");
    renderAt(`/t/${T}/devices`, "/t/:tournamentId/devices", <Devices />);

    expect(await screen.findByText("K7QW2M")).toBeInTheDocument();
    // Read out loud across a hall, so it is spelled out for a screen reader too.
    expect(screen.getByLabelText(/Join code K 7 Q W 2 M/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Turn off" }));
    await waitFor(() => expect(calls.some((c) => c.method === "DELETE")).toBe(true));
  });
});
