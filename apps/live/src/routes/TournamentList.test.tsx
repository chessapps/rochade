import { screen } from "@testing-library/react";

import { PATHS, renderAt, stubApi, summary } from "../test-utils";
import { TournamentList } from "./TournamentList";

describe("the front door", () => {
  it("lists published tournaments with where each section stands", async () => {
    stubApi({ [PATHS.list]: [summary(), summary({ slug: "blitz", name: "Blitz", sections: [{ id: "s-b", name: "Open", rounds_held: 0, in_play: false, declared_rounds: null }] })] });
    renderAt("/", [{ path: "/", element: <TournamentList /> }]);

    const first = await screen.findByRole("link", { name: /Club Open/ });
    expect(first).toHaveAttribute("href", "/club-open");
    expect(first).toHaveTextContent("A: round 2 of 5");
    expect(first).toHaveTextContent("in play");
    expect(screen.getByRole("link", { name: /Blitz/ })).toHaveTextContent("Open: not paired yet");
  });

  it("says so when nothing is published", async () => {
    stubApi({ [PATHS.list]: [] });
    renderAt("/", [{ path: "/", element: <TournamentList /> }]);
    expect(await screen.findByText("Nothing published yet")).toBeInTheDocument();
  });
});
