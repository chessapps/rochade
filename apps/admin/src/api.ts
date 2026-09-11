import { createApi, type paths } from "@rochade/api-client";

import { currentCredential } from "./auth";

/** Set by App once it knows the session, so a 401 can end it. */
let unauthorized: () => void = () => {};

export function onUnauthorized(handler: () => void): void {
  unauthorized = handler;
}

export const api = createApi("", currentCredential, { onUnauthorized: () => unauthorized() });

type Json<T> = T extends { content: { "application/json": infer B } } ? B : never;

export type TournamentSummary = Json<
  paths["/api/tournaments"]["get"]["responses"]["200"]
>[number];
export type TournamentDetail = Json<
  paths["/api/tournaments/{tournament_id}"]["get"]["responses"]["200"]
>;
export type SectionSummary = NonNullable<TournamentDetail["sections"]>[number];
export type RoundSummary = NonNullable<SectionSummary["rounds"]>[number];
export type RoundState = RoundSummary["state"];
export type RoundDetail = Json<paths["/api/rounds/{round_id}"]["get"]["responses"]["200"]>;
export type BoardDetail = NonNullable<RoundDetail["boards"]>[number];
export type ResultState = BoardDetail["state"];
export type RoundEvent = Json<
  paths["/api/rounds/{round_id}/events"]["get"]["responses"]["200"]
>[number];
export type ImportPlan = Json<
  paths["/api/tournaments/{tournament_id}/imports/preview"]["post"]["responses"]["200"]
>;
export type ImportResult = Json<
  paths["/api/tournaments/{tournament_id}/imports"]["post"]["responses"]["201"]
>;
export type DeviceSummary = Json<
  paths["/api/tournaments/{tournament_id}/devices"]["get"]["responses"]["200"]
>[number];
export type IssuedDevice = Json<
  paths["/api/tournaments/{tournament_id}/devices"]["post"]["responses"]["201"]
>;
export type TournamentStandings = Json<
  paths["/api/tournaments/{tournament_id}/standings"]["get"]["responses"]["200"]
>;
export type SectionStandings = NonNullable<TournamentStandings["sections"]>[number];
export type StandingRow = SectionStandings["rows"][number];
export type GameResult = "white_win" | "draw" | "black_win";
export type ManagerSummary = Json<
  paths["/api/managers"]["get"]["responses"]["200"]
>[number];
export type ExportResult = Json<
  paths["/api/rounds/{round_id}/export"]["post"]["responses"]["200"]
>;
export type CreateTournamentBody = NonNullable<
  paths["/api/tournaments"]["post"]["requestBody"]
>["content"]["application/json"];
export type AuthConfig = Json<paths["/api/auth/config"]["get"]["responses"]["200"]>;

// A tournament Rochade pairs itself.
export type PlayerList = Json<
  paths["/api/sections/{section_id}/players"]["get"]["responses"]["200"]
>;
export type PlayerDetail = PlayerList["players"][number];
export type PlayerBody = NonNullable<
  paths["/api/sections/{section_id}/players"]["post"]["requestBody"]
>["content"]["application/json"];
export type CreateSectionBody = NonNullable<
  paths["/api/tournaments/{tournament_id}/sections"]["post"]["requestBody"]
>["content"]["application/json"];
export type CreateSectionResult = Json<
  paths["/api/tournaments/{tournament_id}/sections"]["post"]["responses"]["201"]
>;
export type PairingPlan = Json<
  paths["/api/sections/{section_id}/pairings/preview"]["post"]["responses"]["200"]
>;
export type PairingBoard = NonNullable<PairingPlan["boards"]>[number];
export type Absence = NonNullable<
  NonNullable<
    paths["/api/sections/{section_id}/pairings"]["post"]["requestBody"]
  >["content"]["application/json"]["absent"]
>[number];
export type PairRoundResult = Json<
  paths["/api/sections/{section_id}/pairings"]["post"]["responses"]["201"]
>;
export type ComputeStandingsResult = Json<
  paths["/api/sections/{section_id}/standings"]["post"]["responses"]["200"]
>;

/** The API returns a structured domain error; surface its message, not "500". */
export function errorMessage(error: unknown): string {
  if (error && typeof error === "object" && "message" in error) {
    return String((error as { message: unknown }).message);
  }
  if (error instanceof Error) return error.message;
  return "something went wrong";
}

export function errorDetails(error: unknown): Record<string, unknown> {
  if (error && typeof error === "object" && "details" in error) {
    return (error as { details: Record<string, unknown> }).details ?? {};
  }
  return {};
}

/** An error thrown out of a mutation, carrying the API's structured body. */
export class ApiError extends Error {
  constructor(
    public readonly body: unknown,
    public readonly status?: number,
  ) {
    super(errorMessage(body));
  }

  get details(): Record<string, unknown> {
    return errorDetails(this.body);
  }
}
