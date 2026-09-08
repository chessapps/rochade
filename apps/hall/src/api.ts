import { createApi, type paths } from "@seebach/api-client";

import type { PendingClaim, SubmitOutcome } from "./queue";
import { deviceToken } from "./storage";

export type BoardList =
  paths["/api/tournaments/{tournament_id}/boards"]["get"]["responses"]["200"]["content"]["application/json"];
export type Board = NonNullable<BoardList["boards"]>[number];

const api = createApi("", () => {
  const token = deviceToken();
  return token ? { kind: "device", token } : null;
});

export async function fetchBoards(tournamentId: string): Promise<BoardList> {
  const { data, error } = await api.GET("/api/tournaments/{tournament_id}/boards", {
    params: { path: { tournament_id: tournamentId }, query: { q: "" } },
  });
  if (error || !data) throw new Error("could not load the board list");
  return data;
}

/**
 * Translating the response into the three outcomes the queue understands is
 * the whole contract: only a network failure is worth retrying, and only a
 * server refusal is worth showing the player.
 */
export async function submitClaim(claim: PendingClaim): Promise<SubmitOutcome> {
  try {
    const { response, error } = await api.POST("/api/games/{game_id}/claim", {
      params: { path: { game_id: claim.gameId } },
      body: { result: claim.result },
      headers: { "Idempotency-Key": claim.key },
    });
    if (response.ok) return { status: "accepted" };
    if (response.status >= 500) return { status: "unreachable" };
    return { status: "rejected", message: messageOf(error) };
  } catch {
    return { status: "unreachable" };
  }
}

function messageOf(error: unknown): string {
  if (error && typeof error === "object" && "message" in error) {
    return String((error as { message: unknown }).message);
  }
  return "the server refused this result";
}

export type Standings =
  paths["/api/tournaments/{tournament_id}/standings"]["get"]["responses"]["200"]["content"]["application/json"];
export type SectionStandings = NonNullable<Standings["sections"]>[number];

export async function fetchStandings(tournamentId: string): Promise<Standings> {
  const { data, error } = await api.GET("/api/tournaments/{tournament_id}/standings", {
    params: { path: { tournament_id: tournamentId } },
  });
  if (error || !data) throw new Error("could not load the standings");
  return data;
}

export type JoinedDevice =
  paths["/api/devices/join"]["post"]["responses"]["201"]["content"]["application/json"];

/**
 * Redeem a join code. The one call this app makes with no credentials at all:
 * it is how a phone that cannot scan the QR gets a device of its own.
 */
export async function joinWithCode(code: string): Promise<JoinedDevice> {
  const { data, error, response } = await api.POST("/api/devices/join", {
    body: { code, label: "" },
  });
  if (data) return data;
  if (response.status === 404) throw new Error("That code does not open anything.");
  throw new Error(messageOf(error) || "The code could not be used.");
}
