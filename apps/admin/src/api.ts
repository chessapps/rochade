import { createApi, type paths } from "@seebach/api-client";

const TOKEN_KEY = "seebach.staff-token";

export function staffToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function signIn(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function signOut(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export const api = createApi("", () => {
  const token = staffToken();
  return token ? { kind: "staff", token } : null;
});

type Json<T> = T extends { content: { "application/json": infer B } } ? B : never;

export type TournamentSummary = Json<
  paths["/api/tournaments"]["get"]["responses"]["200"]
>[number];
export type TournamentDetail = Json<
  paths["/api/tournaments/{tournament_id}"]["get"]["responses"]["200"]
>;
export type SectionSummary = NonNullable<TournamentDetail["sections"]>[number];
export type RoundSummary = NonNullable<SectionSummary["rounds"]>[number];
export type ImportPlan = Json<
  paths["/api/tournaments/{tournament_id}/imports/preview"]["post"]["responses"]["200"]
>;
export type ArbiterQueue = Json<
  paths["/api/tournaments/{tournament_id}/queue"]["get"]["responses"]["200"]
>;
export type QueueEntry = NonNullable<ArbiterQueue["entries"]>[number];
export type DeviceSummary = Json<
  paths["/api/tournaments/{tournament_id}/devices"]["get"]["responses"]["200"]
>[number];
export type GameResult = "white_win" | "draw" | "black_win";

export type ExportResult = Json<
  paths["/api/rounds/{round_id}/export"]["post"]["responses"]["200"]
>;

/** The API returns a structured domain error; surface its message, not "500". */
export function errorMessage(error: unknown): string {
  if (error && typeof error === "object" && "message" in error) {
    return String((error as { message: unknown }).message);
  }
  return "something went wrong";
}

export function errorDetails(error: unknown): Record<string, unknown> {
  if (error && typeof error === "object" && "details" in error) {
    return (error as { details: Record<string, unknown> }).details ?? {};
  }
  return {};
}
