import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { Board } from "./api";
import { BoardListScreen, DoneScreen, ResultChoiceScreen } from "./screens";

const board: Board = {
  game_id: "g3",
  section_id: "s1",
  section_name: "Open",
  round_number: 3,
  board: 3,
  white_name: "Meyer, Thomas",
  black_name: "Wagner, Elisabeth",
  white_result: " ",
  state: "empty",
  is_bye: false,
  entered: false,
};

describe("choosing a result", () => {
  it("shows both players by colour, names the winner on each button, and sends on one tap", async () => {
    const onChoose = vi.fn();
    render(<ResultChoiceScreen board={board} busy={false} onChoose={onChoose} onBack={vi.fn()} />);

    expect(screen.getByText("Meyer, Thomas")).toBeInTheDocument();
    expect(screen.getByText("Wagner, Elisabeth")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Black wins/ }));

    expect(onChoose).toHaveBeenCalledWith("black_win");
    expect(screen.getByRole("button", { name: /Black wins/ })).toHaveTextContent(
      "Wagner, Elisabeth wins",
    );
  });

  it("locks the buttons while a result is on its way", () => {
    render(<ResultChoiceScreen board={board} busy={true} onChoose={vi.fn()} onBack={vi.fn()} />);
    expect(screen.getByRole("button", { name: /White wins/ })).toBeDisabled();
  });
});

describe("the board list", () => {
  const boards: Board[] = [
    board,
    { ...board, game_id: "g12", board: 12, white_name: "Krause, Florian", black_name: null, is_bye: true },
    { ...board, game_id: "g1", board: 1, white_name: "Müller, Hans", black_name: "Schneider, Anna", white_result: "1", state: "claimed", entered: true },
  ];
  const list = (query: string) =>
    render(
      <BoardListScreen
        boards={boards}
        query={query}
        onQuery={vi.fn()}
        onPick={vi.fn()}
        pendingKeys={new Set()}
        offline={false}
        queued={0}
      />,
    );

  it("finds a board by its number as well as by a name", () => {
    list("12");
    expect(screen.getByText("Krause, Florian")).toBeInTheDocument();
    expect(screen.queryByText("Meyer, Thomas")).not.toBeInTheDocument();
  });

  it("shows the score once a result stands, and offers entry otherwise", () => {
    list("");
    expect(screen.getByText("1 – 0")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Board 3,.*open$/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Board 1,.*entered$/ })).toBeInTheDocument();
    // A bye is not something anyone enters.
    expect(screen.queryByRole("button", { name: /Board 12,/ })).not.toBeInTheDocument();
  });
});

describe("after sending", () => {
  it("offers to correct the result, and says so once corrected", async () => {
    const onCorrect = vi.fn();
    const { rerender } = render(
      <DoneScreen
        board={board}
        result="white_win"
        queued={false}
        corrected={false}
        onCorrect={onCorrect}
        onDone={vi.fn()}
      />,
    );
    expect(screen.getByText("Result sent")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Correct it/ }));
    expect(onCorrect).toHaveBeenCalled();

    rerender(
      <DoneScreen
        board={board}
        result="draw"
        queued={false}
        corrected={true}
        onCorrect={onCorrect}
        onDone={vi.fn()}
      />,
    );
    expect(screen.getByText("Correction sent")).toBeInTheDocument();
  });
});
