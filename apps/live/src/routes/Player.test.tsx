import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { readWatchList } from "../watch";
import { PATHS, SECTION, SLUG, clearWatchList, player, renderAt, stubApi, tournament } from "../test-utils";
import { Player } from "./Player";

const ROUTES = [{ path: "/:slug/s/:sectionId/p/:startRank", element: <Player /> }];

beforeEach(clearWatchList);

describe("the player page", () => {
  it("shows the standing and every game from the player's side, and watches on a tap", async () => {
    const user = userEvent.setup();
    stubApi({ [PATHS.tournament]: tournament(), [PATHS.player(1)]: player() });
    renderAt(`/${SLUG}/s/${SECTION}/p/1`, ROUTES);

    expect(await screen.findByRole("heading", { level: 1, name: "Baumann, Lukas" })).toBeInTheDocument();
    expect(screen.getByText("Rank").nextSibling).toHaveTextContent("2");
    expect(screen.getByText("Points").nextSibling).toHaveTextContent("½");

    const games = screen.getAllByRole("listitem");
    expect(games).toHaveLength(2);
    expect(games[0]).toHaveTextContent("R1");
    expect(games[0]).toHaveTextContent("Chen, Wei");
    expect(games[0]).toHaveTextContent("½-½");
    expect(games[1]).toHaveTextContent("Dubois, Elise");
    expect(screen.getByTitle(/preliminary/)).toHaveTextContent("1-0");

    const watch = screen.getByRole("button", { name: "Watch" });
    expect(watch).toHaveAttribute("aria-pressed", "false");
    await user.click(watch);
    expect(screen.getByRole("button", { name: "Watching" })).toHaveAttribute("aria-pressed", "true");
    expect(readWatchList()).toEqual([
      { slug: SLUG, sectionId: SECTION, startRank: 1, name: "Baumann, Lukas" },
    ]);
    expect(JSON.parse(localStorage.getItem("rochade.live.watch") ?? "[]")).toHaveLength(1);

    await user.click(screen.getByRole("button", { name: "Watching" }));
    expect(readWatchList()).toEqual([]);
  });

  it("says when the player is no longer in the section", async () => {
    stubApi({ [PATHS.tournament]: tournament(), [PATHS.player(9)]: { status: 404 } });
    renderAt(`/${SLUG}/s/${SECTION}/p/9`, ROUTES);
    expect(await screen.findByText("No longer in this section")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Club Open/ })).toHaveAttribute("href", `/${SLUG}`);
  });
});
