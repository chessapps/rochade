import { screen, within } from "@testing-library/react";

import { toggleWatch } from "../watch";
import { PATHS, SECTION, SLUG, clearWatchList, player, renderAt, round, standings, stubApi, tournament } from "../test-utils";
import { Tournament } from "./Tournament";

const ROUTES = [{ path: "/:slug", element: <Tournament /> }];

beforeEach(clearWatchList);

describe("the tournament page", () => {
  it("opens on the newest round, marks a preliminary result and links every name", async () => {
    stubApi({ [PATHS.tournament]: tournament(), [PATHS.round(2)]: round(2) });
    renderAt(`/${SLUG}`, ROUTES);

    expect(await screen.findByRole("heading", { level: 1, name: "Club Open" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { level: 2, name: /Round 2/ })).toBeInTheDocument();
    expect(screen.getByText("1 of 2 results in")).toBeInTheDocument();

    const boards = screen.getAllByRole("listitem");
    expect(boards).toHaveLength(2);
    expect(within(boards[0]!).getByTitle(/preliminary/)).toHaveTextContent("1-0");
    expect(within(boards[1]!).getByText("no result yet")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Baumann, Lukas/ })).toHaveAttribute(
      "href",
      `/${SLUG}/s/${SECTION}/p/1`,
    );
  });

  it("marks only the chosen view as the current tab and falls back on unknown params", async () => {
    stubApi({ [PATHS.tournament]: tournament(), [PATHS.standings]: standings() });
    renderAt(`/${SLUG}?s=nope&v=standings&r=abc`, ROUTES);

    await screen.findByRole("heading", { level: 2, name: "Standings" });
    const current = screen.getAllByRole("link", { current: "page" });
    expect(current.map((link) => link.textContent)).toEqual(["Standings"]);
  });

  it("shows an earlier round from the URL and steps between rounds", async () => {
    stubApi({ [PATHS.tournament]: tournament(), [PATHS.round(1)]: round(1) });
    renderAt(`/${SLUG}?r=1`, ROUTES);

    expect(await screen.findByRole("heading", { level: 2, name: /Round 1/ })).toBeInTheDocument();
    expect(await screen.findByText("½-½")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Next round" })).toHaveAttribute("href", `/${SLUG}?r=2`);
    expect(screen.queryByRole("link", { name: "Previous round" })).not.toBeInTheDocument();
  });

  it("shows the standings as the manager gave them", async () => {
    stubApi({ [PATHS.tournament]: tournament(), [PATHS.standings]: standings() });
    renderAt(`/${SLUG}?v=standings`, ROUTES);

    expect(await screen.findByRole("heading", { level: 2, name: "Standings" })).toBeInTheDocument();
    expect(screen.getByText("after round 1")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Buchholz" })).toBeInTheDocument();
    const rows = screen.getAllByRole("row").slice(1);
    expect(rows[0]).toHaveTextContent("Egger, Tobias");
    expect(rows[0]).toHaveTextContent("1");
    expect(rows[1]).toHaveTextContent("½");
  });

  it("says when the link points nowhere", async () => {
    stubApi({ [PATHS.tournament]: { status: 404 } });
    renderAt(`/${SLUG}`, ROUTES);
    expect(await screen.findByText("No such tournament")).toBeInTheDocument();
  });

  it("shows the watched players of this tournament as a strip", async () => {
    toggleWatch({ slug: SLUG, sectionId: SECTION, startRank: 3, name: "Dubois, Elise" });
    toggleWatch({ slug: "other", sectionId: "x", startRank: 1, name: "Somebody Else" });
    stubApi({
      [PATHS.tournament]: tournament(),
      [PATHS.round(2)]: round(2),
      [PATHS.player(3)]: player({ start_rank: 3, name: "Dubois, Elise", title: "WFM" }),
    });
    renderAt(`/${SLUG}`, ROUTES);

    await screen.findByRole("heading", { level: 1, name: "Club Open" });
    const strip = screen.getByText("Watching").parentElement!;
    const link = within(strip).getByRole("link", { name: /Dubois, Elise/ });
    expect(link).toHaveAttribute("href", `/${SLUG}/s/${SECTION}/p/3`);
    // The latest game, from the player's own page, comes along.
    await within(strip).findByText("R2");
    expect(link).toHaveTextContent("1-0");
    expect(screen.queryByText("Somebody Else")).not.toBeInTheDocument();
  });
});
