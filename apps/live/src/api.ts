/**
 * The public API, read without any credential. Every path here is under
 * /api/public and answers only for a published tournament.
 */

import { createApi, type paths } from "@rochade/api-client";

export const api = createApi("", () => null);

type Json<T> = T extends { content: { "application/json": infer B } } ? B : never;

export type TournamentSummary = Json<
  paths["/api/public/tournaments"]["get"]["responses"]["200"]
>[number];
export type Tournament = Json<paths["/api/public/tournaments/{slug}"]["get"]["responses"]["200"]>;
export type Section = Tournament["sections"][number];
export type RoundSummary = Section["rounds"][number];
export type Round = Json<
  paths["/api/public/tournaments/{slug}/sections/{section_id}/rounds/{number}"]["get"]["responses"]["200"]
>;
export type Board = Round["boards"][number];
export type Side = Board["white"];
export type Shown = Board["state"];
export type Standings = Json<
  paths["/api/public/tournaments/{slug}/sections/{section_id}/standings"]["get"]["responses"]["200"]
>;
export type StandingRow = Standings["rows"][number];
export type Player = Json<
  paths["/api/public/tournaments/{slug}/sections/{section_id}/players/{start_rank}"]["get"]["responses"]["200"]
>;
export type PlayerGame = Player["games"][number];

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (error && typeof error === "object" && "message" in error) {
    return String((error as { message: unknown }).message);
  }
  return "something went wrong";
}

type Result<T> = { data?: T; error?: unknown; response: Response };

/** openapi-fetch reports errors as data; a query wants them thrown. */
export async function unwrap<T>(call: Promise<Result<T>>): Promise<T> {
  const { data, error, response } = await call;
  if (error !== undefined) throw new ApiError(response.status, errorMessage(error));
  if (data === undefined) throw new ApiError(response.status, "empty response");
  return data;
}
