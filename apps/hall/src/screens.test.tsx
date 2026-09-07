import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Board } from "./api";
import { ConfirmScreen } from "./screens";

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
