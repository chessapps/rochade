import { screen } from "@testing-library/react";

import { renderAt } from "../test-utils";
import { SwissManagerGuide } from "./SwissManagerGuide";

describe("the Swiss-Manager guide", () => {
  it("walks the round through both programs and names the exports", () => {
    renderAt("/guides/swiss-manager", "/guides/swiss-manager", <SwissManagerGuide />);
    expect(
      screen.getByRole("heading", { name: "Running a tournament with Swiss-Manager" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Export it for Rochade" })).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Import the results into Swiss-Manager" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Spielerdaten (Text-File)")).toBeInTheDocument();
    expect(screen.getByText("Spielerauslosung (Text-File)")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to the tournaments" })).toHaveAttribute("href", "/?all");
  });
});
