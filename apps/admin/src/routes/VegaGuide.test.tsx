import { screen } from "@testing-library/react";

import { renderAt } from "../test-utils";
import { VegaGuide } from "./VegaGuide";

describe("the Vega guide", () => {
  it("walks the round through both programs and names the files", () => {
    renderAt("/guides/vega", "/guides/vega", <VegaGuide />);
    expect(screen.getByRole("heading", { name: "Running a tournament with Vega" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Hand the round to Rochade" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Import the results into Vega" })).toBeInTheDocument();
    expect(screen.getAllByText("engine26.trf").length).toBeGreaterThan(0);
    expect(screen.getAllByText("SortedPairs.txt").length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "Back to the tournaments" })).toHaveAttribute("href", "/?all");
  });
});
