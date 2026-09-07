import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Board } from "./api";
import { BoardListScreen, ConfirmScreen } from "./screens";

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

describe("the confirmation", () => {
  it("names the winner, both players and the score before anything is sent", () => {
    render(
      <ConfirmScreen board={board} result="black_win" busy={false} onConfirm={vi.fn()} onBack={vi.fn()} />,
    );

    expect(screen.getByText("Black wins")).toBeInTheDocument();
    expect(screen.getByText("Wagner, Elisabeth wins")).toBeInTheDocument();
    expect(screen.getByText("Meyer, Thomas")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Confirm 0 : 1" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Wrong, change it" })).toBeInTheDocument();
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
    expect(screen.getByRole("button", { name: /Board 3,/ })).toHaveTextContent("enter");
    // A bye is not something anyone enters.
    expect(screen.queryByRole("button", { name: /Board 12,/ })).not.toBeInTheDocument();
  });
});
