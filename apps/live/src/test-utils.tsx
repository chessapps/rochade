/**
 * Mount a screen the way main.tsx does, with the API stubbed. Tests hand in
 * what the API should answer per path; anything unexpected fails loudly
 * rather than hanging a query forever.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, type RenderResult } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter, Route, Routes } from "react-router";

import { api, type Player, type Round, type Standings, type Tournament, type TournamentSummary } from "./api";
import { _resetWatchCache } from "./watch";

export type Answer = unknown | { status: number };

/** Point `api.GET` at a table of answers by exact path; returns the paths asked for. */
export function stubApi(answers: Record<string, Answer>): string[] {
  const asked: string[] = [];
  vi.spyOn(api, "GET").mockImplementation((async (
    path: string,
    init?: { params?: { path?: Record<string, string | number> } },
  ) => {
    const resolved = path.replace(/\{(\w+)\}/g, (_, key: string) =>
      String(init?.params?.path?.[key] ?? key),
    );
    asked.push(resolved);
    if (!(resolved in answers)) {
      return { error: { message: `no stub for GET ${resolved}` }, response: new Response(null, { status: 500 }) };
    }
    const answer = answers[resolved];
    if (answer && typeof answer === "object" && "status" in answer && Object.keys(answer).length === 1) {
      const status = (answer as { status: number }).status;
      return { error: { message: `HTTP ${status}` }, response: new Response(null, { status }) };
    }
    return { data: answer, response: new Response(null, { status: 200 }) };
  }) as never);
  return asked;
}

export function renderAt(path: string, routes: { path: string; element: ReactElement }[]): RenderResult {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          {routes.map((route) => (
            <Route key={route.path} path={route.path} element={route.element} />
          ))}
          <Route path="*" element={<p data-testid="elsewhere" />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

export function clearWatchList(): void {
  localStorage.clear();
  _resetWatchCache();
}

// --- fixtures ---------------------------------------------------------------

export const SLUG = "club-open";
export const SECTION = "s-a";

export const side = (start_rank: number, name: string, title = "", rating: number | null = 2000) => ({
  start_rank,
  name,
  title,
  rating,
  federation: "SUI",
});

export function summary(overrides: Partial<TournamentSummary> = {}): TournamentSummary {
  return {
    slug: SLUG,
    name: "Club Open",
    city: "Zürich",
    federation: "SUI",
    start_date: "2026-09-12",
    end_date: "2026-09-13",
    sections: [{ id: SECTION, name: "A", rounds_held: 2, in_play: true, declared_rounds: 5 }],
    ...overrides,
  };
}

export function tournament(overrides: Partial<Tournament> = {}): Tournament {
  return {
    slug: SLUG,
    name: "Club Open",
    city: "Zürich",
    federation: "SUI",
    start_date: "2026-09-12",
    end_date: "2026-09-13",
    sections: [
      {
        id: SECTION,
        name: "A",
        players: 4,
        declared_rounds: 5,
        standings_after_round: 1,
        tiebreak_names: ["Buchholz"],
        rounds: [
          { number: 1, state: "exported", boards: 2, results_in: 2, updated_at: "2026-09-12T10:00:00Z" },
          { number: 2, state: "open", boards: 2, results_in: 1, updated_at: "2026-09-12T14:00:00Z" },
        ],
      },
    ],
    ...overrides,
  };
}

export function round(number: number, overrides: Partial<Round> = {}): Round {
  return {
    section_id: SECTION,
    section_name: "A",
    number,
    state: number === 2 ? "open" : "exported",
    boards:
      number === 2
        ? [
            { board: 1, white: side(1, "Baumann, Lukas", "FM", 2201), black: side(3, "Dubois, Elise", "WFM", 2098), result: "1-0", state: "preliminary", updated_at: "2026-09-12T14:00:00Z" },
            { board: 2, white: side(4, "Egger, Tobias", "", 2044), black: side(2, "Chen, Wei", "", 2150), result: "", state: "pending", updated_at: "2026-09-12T13:00:00Z" },
          ]
        : [
            { board: 1, white: side(1, "Baumann, Lukas", "FM", 2201), black: side(2, "Chen, Wei", "", 2150), result: "½-½", state: "confirmed", updated_at: "2026-09-12T10:00:00Z" },
            { board: 2, white: side(3, "Dubois, Elise", "WFM", 2098), black: side(4, "Egger, Tobias", "", 2044), result: "0-1", state: "confirmed", updated_at: "2026-09-12T10:00:00Z" },
          ],
    ...overrides,
  };
}

export function standings(overrides: Partial<Standings> = {}): Standings {
  return {
    section_id: SECTION,
    section_name: "A",
    manager_label: "Vega",
    after_round: 1,
    rounds_held: 2,
    stale: false,
    tiebreak_names: ["Buchholz"],
    tiebreak_columns: 1,
    rows: [
      { rank: 1, start_rank: 4, name: "Egger, Tobias", title: "", federation: "SUI", rating: 2044, points: 1, tiebreaks: [0.5] },
      { rank: 2, start_rank: 1, name: "Baumann, Lukas", title: "FM", federation: "SUI", rating: 2201, points: 0.5, tiebreaks: [0.5] },
      { rank: 2, start_rank: 2, name: "Chen, Wei", title: "", federation: "SUI", rating: 2150, points: 0.5, tiebreaks: [0.5] },
      { rank: 4, start_rank: 3, name: "Dubois, Elise", title: "WFM", federation: "FRA", rating: 2098, points: 0, tiebreaks: [1] },
    ],
    ...overrides,
  };
}

export function player(overrides: Partial<Player> = {}): Player {
  return {
    section_id: SECTION,
    section_name: "A",
    start_rank: 1,
    name: "Baumann, Lukas",
    title: "FM",
    rating: 2201,
    federation: "SUI",
    withdrawn_from_round: null,
    rank: 2,
    points: 0.5,
    tiebreaks: [0.5],
    tiebreak_names: ["Buchholz"],
    standings_after_round: 1,
    games: [
      { round_number: 1, board: 1, colour: "white", opponent: side(2, "Chen, Wei", "", 2150), result: "½-½", score: 0.5, state: "confirmed", updated_at: "2026-09-12T10:00:00Z" },
      { round_number: 2, board: 1, colour: "white", opponent: side(3, "Dubois, Elise", "WFM", 2098), result: "1-0", score: 1, state: "preliminary", updated_at: "2026-09-12T14:00:00Z" },
    ],
    ...overrides,
  };
}

export const PATHS = {
  list: "/api/public/tournaments",
  tournament: `/api/public/tournaments/${SLUG}`,
  round: (n: number) => `/api/public/tournaments/${SLUG}/sections/${SECTION}/rounds/${n}`,
  standings: `/api/public/tournaments/${SLUG}/sections/${SECTION}/standings`,
  player: (rank: number) => `/api/public/tournaments/${SLUG}/sections/${SECTION}/players/${rank}`,
};
