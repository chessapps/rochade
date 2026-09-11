/**
 * Every read and write the screens make, as hooks.
 *
 * The keys are narrow on purpose: releasing a round touches that round and its
 * tournament, not the device list. Polling lives here too, so a screen says
 * "watch this round" and nothing more.
 */

import {
  useMutation,
  useQueries,
  useQuery,
  useQueryClient,
  type UseMutationOptions,
} from "@tanstack/react-query";

import {
  api,
  ApiError,
  type Absence,
  type CreateSectionBody,
  type CreateTournamentBody,
  type GameResult,
  type PlayerBody,
  type RoundEvent,
  type RoundState,
} from "./api";

type Result<T> = { data?: T; error?: unknown; response: Response };

/** openapi-fetch reports errors as data; a hook wants them thrown. */
async function unwrap<T>(call: Promise<Result<T>>): Promise<T> {
  const { data, error, response } = await call;
  if (error !== undefined) throw new ApiError(error, response.status);
  if (data === undefined) throw new ApiError({ message: "empty response" }, response.status);
  return data;
}

export const keys = {
  tournaments: ["tournaments"] as const,
  tournament: (id: string) => ["tournament", id] as const,
  round: (id: string) => ["round", id] as const,
  roundFile: (id: string) => ["round", id, "file"] as const,
  events: (id: string) => ["round", id, "events"] as const,
  devices: (tournamentId: string) => ["devices", tournamentId] as const,
  standings: (tournamentId: string) => ["standings", tournamentId] as const,
  managers: ["managers"] as const,
  players: (sectionId: string) => ["players", sectionId] as const,
};

/** How often to look again. Claims arrive while a round is open; a frozen round never moves. */
export function pollInterval(state: RoundState | undefined): number | false {
  switch (state) {
    case "open":
      return 5_000;
    case "confirmed":
      return 30_000;
    default:
      return false;
  }
}

// --- reads -------------------------------------------------------------------

export function useTournaments() {
  return useQuery({
    queryKey: keys.tournaments,
    queryFn: () => unwrap(api.GET("/api/tournaments")),
  });
}

export function useTournament(id: string | undefined, poll = false) {
  return useQuery({
    queryKey: keys.tournament(id ?? ""),
    queryFn: () =>
      unwrap(
        api.GET("/api/tournaments/{tournament_id}", {
          params: { path: { tournament_id: id! } },
        }),
      ),
    enabled: Boolean(id),
    refetchInterval: poll ? 10_000 : false,
  });
}

export function useRound(id: string | undefined) {
  return useQuery({
    queryKey: keys.round(id ?? ""),
    queryFn: () => unwrap(api.GET("/api/rounds/{round_id}", { params: { path: { round_id: id! } } })),
    enabled: Boolean(id),
    refetchInterval: (query) => pollInterval(query.state.data?.state),
  });
}

export function useRoundEvents(id: string | undefined, state: RoundState | undefined) {
  return useQuery({
    queryKey: keys.events(id ?? ""),
    queryFn: () =>
      unwrap(api.GET("/api/rounds/{round_id}/events", { params: { path: { round_id: id! } } })),
    enabled: Boolean(id) && state !== undefined,
    // The board's own poll refetches this the moment a board moves; this is
    // only the slow backstop, and a frozen round has no more to say.
    refetchInterval: pollInterval(state) === false ? false : 30_000,
  });
}

/**
 * Every section's current round, in one stream for the tournament home: the
 * newest first. Shares the per-round cache with useRoundEvents, so opening a
 * round shows the same log this page already had.
 */
export type FeedEvent = RoundEvent & { round_id: string };

export function useLiveFeed(rounds: { id: string; state: RoundState }[]) {
  return useQueries({
    queries: rounds.map((round) => ({
      queryKey: keys.events(round.id),
      queryFn: () =>
        unwrap(api.GET("/api/rounds/{round_id}/events", { params: { path: { round_id: round.id } } })),
      refetchInterval: pollInterval(round.state) === false ? false : 10_000,
    })),
    combine: (results) => ({
      events: results
        .flatMap((result, index) =>
          (result.data ?? []).map((event): FeedEvent => ({ ...event, round_id: rounds[index]!.id })),
        )
        .sort((a, b) => b.at.localeCompare(a.at)),
      isPending: results.some((result) => result.isPending),
    }),
  });
}

export function useExportFile(roundId: string | undefined, enabled: boolean) {
  return useQuery({
    queryKey: keys.roundFile(roundId ?? ""),
    queryFn: () =>
      unwrap(api.GET("/api/rounds/{round_id}/export", { params: { path: { round_id: roundId! } } })),
    enabled: Boolean(roundId) && enabled,
    staleTime: Infinity,
  });
}

export function useDevices(tournamentId: string | undefined) {
  return useQuery({
    queryKey: keys.devices(tournamentId ?? ""),
    queryFn: () =>
      unwrap(
        api.GET("/api/tournaments/{tournament_id}/devices", {
          params: { path: { tournament_id: tournamentId! } },
        }),
      ),
    enabled: Boolean(tournamentId),
    refetchInterval: 30_000,
  });
}

export function useStandings(tournamentId: string | undefined) {
  return useQuery({
    queryKey: keys.standings(tournamentId ?? ""),
    queryFn: () =>
      unwrap(
        api.GET("/api/tournaments/{tournament_id}/standings", {
          params: { path: { tournament_id: tournamentId! } },
        }),
      ),
    enabled: Boolean(tournamentId),
  });
}

export function usePlayers(sectionId: string | undefined) {
  return useQuery({
    queryKey: keys.players(sectionId ?? ""),
    queryFn: () =>
      unwrap(
        api.GET("/api/sections/{section_id}/players", {
          params: { path: { section_id: sectionId! } },
        }),
      ),
    enabled: Boolean(sectionId),
  });
}

export function useManagers() {
  return useQuery({
    queryKey: keys.managers,
    queryFn: () => unwrap(api.GET("/api/managers")),
    staleTime: Infinity,
  });
}

// --- writes ------------------------------------------------------------------

type Opts<TData, TVars> = Omit<UseMutationOptions<TData, ApiError, TVars>, "mutationFn">;

export function useCreateTournament(opts?: Opts<{ id: string; name: string }, CreateTournamentBody>) {
  const client = useQueryClient();
  return useMutation({
    ...opts,
    mutationFn: (body: CreateTournamentBody) => unwrap(api.POST("/api/tournaments", { body })),
    onSuccess: (data, vars, ctx, mutation) => {
      void client.invalidateQueries({ queryKey: keys.tournaments });
      opts?.onSuccess?.(data, vars, ctx, mutation);
    },
  });
}

/**
 * The one irreversible action: the tournament and everything under it. The
 * server wants the name typed back, so a wrong id can never take an event.
 */
export function useDeleteTournament(opts?: Opts<{ id: string; name: string }, { tournamentId: string; confirmName: string }>) {
  const client = useQueryClient();
  return useMutation({
    ...opts,
    mutationFn: ({ tournamentId, confirmName }) =>
      unwrap(
        api.DELETE("/api/tournaments/{tournament_id}", {
          params: { path: { tournament_id: tournamentId }, query: { confirm_name: confirmName } },
        }),
      ),
    onSuccess: (data, vars, ctx, mutation) => {
      client.removeQueries({ queryKey: keys.tournament(vars.tournamentId) });
      void client.invalidateQueries({ queryKey: keys.tournaments });
      opts?.onSuccess?.(data, vars, ctx, mutation);
    },
  });
}

export interface ImportVars {
  tournamentId: string;
  section_name: string;
  content: string;
  filename: string;
  force: boolean;
  /** How many rounds the tournament has, when the files do not say (Vega's never do). */
  declared_rounds?: number | null;
}

export function usePreviewImport() {
  return useMutation({
    mutationFn: ({ tournamentId, filename: _filename, ...body }: ImportVars) =>
      unwrap(
        api.POST("/api/tournaments/{tournament_id}/imports/preview", {
          params: { path: { tournament_id: tournamentId } },
          body,
        }),
      ),
  });
}

export function useImportRound() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ tournamentId, ...body }: ImportVars) =>
      unwrap(
        api.POST("/api/tournaments/{tournament_id}/imports", {
          params: { path: { tournament_id: tournamentId } },
          body,
        }),
      ),
    onSuccess: (_data, vars) => {
      void client.invalidateQueries({ queryKey: keys.tournament(vars.tournamentId) });
    },
  });
}

interface RoundVars {
  roundId: string;
  tournamentId: string;
}

export function useSetResult() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({
      gameId,
      white,
      black,
    }: RoundVars & { gameId: string; white: string; black: string }) =>
      unwrap(
        api.PUT("/api/games/{game_id}/result", {
          params: { path: { game_id: gameId } },
          body: { white_result: white, black_result: black, note: "" },
        }),
      ),
    onSettled: (_data, _error, vars) => invalidateRound(client, vars),
  });
}

export function useResolveDispute() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ gameId, result }: RoundVars & { gameId: string; result: GameResult }) =>
      unwrap(
        api.POST("/api/games/{game_id}/resolve", {
          params: { path: { game_id: gameId } },
          body: { result, note: "" },
        }),
      ),
    onSettled: (_data, _error, vars) => invalidateRound(client, vars),
  });
}

/** Confirm entered boards before release: all of them, or the ones named. */
export function useConfirmBoards() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ roundId, gameIds }: RoundVars & { gameIds: string[] }) =>
      unwrap(
        api.POST("/api/rounds/{round_id}/confirm", {
          params: { path: { round_id: roundId } },
          body: { game_ids: gameIds, note: "" },
        }),
      ),
    onSettled: (_data, _error, vars) => invalidateRound(client, vars),
  });
}

/** The manager's player list on its own: only points, tiebreaks and ranks move. */
export function useImportStandings() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({
      tournamentId,
      sectionName,
      content,
    }: {
      tournamentId: string;
      sectionName: string;
      content: string;
    }) =>
      unwrap(
        api.POST("/api/tournaments/{tournament_id}/standings", {
          params: { path: { tournament_id: tournamentId } },
          body: { section_name: sectionName, content },
        }),
      ),
    onSettled: (_data, _error, vars) => {
      void client.invalidateQueries({ queryKey: keys.standings(vars.tournamentId) });
    },
  });
}

export function useNameTiebreaks() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({
      tournamentId,
      sectionName,
      names,
    }: {
      tournamentId: string;
      sectionName: string;
      names: string[];
    }) =>
      unwrap(
        api.PUT("/api/tournaments/{tournament_id}/sections/{section_name}/tiebreaks", {
          params: { path: { tournament_id: tournamentId, section_name: sectionName } },
          body: { names },
        }),
      ),
    onSettled: (_data, _error, vars) => {
      void client.invalidateQueries({ queryKey: keys.standings(vars.tournamentId) });
    },
  });
}

export function useReleaseRound() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ roundId, force }: RoundVars & { force: boolean }) =>
      unwrap(
        api.POST("/api/rounds/{round_id}/release", {
          params: { path: { round_id: roundId } },
          body: { force, note: "" },
        }),
      ),
    onSettled: (_data, _error, vars) => invalidateRound(client, vars),
  });
}

export function useExportRound() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ roundId, force }: RoundVars & { force: boolean }) =>
      unwrap(
        api.POST("/api/rounds/{round_id}/export", {
          params: { path: { round_id: roundId } },
          body: { force },
        }),
      ),
    onSuccess: (data, vars) => {
      // The file just produced is the file a re-download will produce.
      client.setQueryData(keys.roundFile(vars.roundId), data);
    },
    onSettled: (_data, _error, vars) => invalidateRound(client, vars),
  });
}

export function useIssueDevice() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ tournamentId, label }: { tournamentId: string; label: string }) =>
      unwrap(
        api.POST("/api/tournaments/{tournament_id}/devices", {
          params: { path: { tournament_id: tournamentId } },
          body: { label, base_url: window.location.origin },
        }),
      ),
    onSettled: (_data, _error, vars) => {
      void client.invalidateQueries({ queryKey: keys.devices(vars.tournamentId) });
    },
  });
}

export function useSetJoinCode() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ tournamentId, enabled }: { tournamentId: string; enabled: boolean }) =>
      unwrap(
        enabled
          ? api.POST("/api/tournaments/{tournament_id}/join-code", {
              params: { path: { tournament_id: tournamentId } },
            })
          : api.DELETE("/api/tournaments/{tournament_id}/join-code", {
              params: { path: { tournament_id: tournamentId } },
            }),
      ),
    onSettled: (_data, _error, vars) => {
      void client.invalidateQueries({ queryKey: keys.tournament(vars.tournamentId) });
    },
  });
}

export function useRevokeDevice() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ deviceId }: { deviceId: string; tournamentId: string }) =>
      unwrap(
        api.POST("/api/devices/{device_id}/revoke", { params: { path: { device_id: deviceId } } }),
      ),
    onSettled: (_data, _error, vars) => {
      void client.invalidateQueries({ queryKey: keys.devices(vars.tournamentId) });
    },
  });
}

/** Takes revoked devices off the list. Refused by the server for a live one. */
export function useRemoveDevices() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({ deviceIds }: { deviceIds: string[]; tournamentId: string }) => {
      for (const deviceId of deviceIds) {
        await unwrap(
          api.DELETE("/api/devices/{device_id}", { params: { path: { device_id: deviceId } } }),
        );
      }
    },
    onSettled: (_data, _error, vars) => {
      void client.invalidateQueries({ queryKey: keys.devices(vars.tournamentId) });
    },
  });
}

function invalidateRound(client: ReturnType<typeof useQueryClient>, vars: RoundVars): void {
  void client.invalidateQueries({ queryKey: keys.round(vars.roundId) });
  void client.invalidateQueries({ queryKey: keys.tournament(vars.tournamentId) });
  // A section Rochade pairs itself recomputes its table on release and on
  // every correction of a released board; the Standings tab must not lag.
  void client.invalidateQueries({ queryKey: keys.standings(vars.tournamentId) });
}

/** A pairing or an unpairing moves two rounds and the table at once. */
function invalidateSection(client: ReturnType<typeof useQueryClient>, tournamentId: string): void {
  void client.invalidateQueries({ queryKey: ["round"] });
  void client.invalidateQueries({ queryKey: keys.tournament(tournamentId) });
  void client.invalidateQueries({ queryKey: keys.standings(tournamentId) });
}

// --- a tournament Rochade pairs itself -----------------------------------------

interface SectionVars {
  sectionId: string;
  tournamentId: string;
}

export function useCreateSection() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ tournamentId, ...body }: CreateSectionBody & { tournamentId: string }) =>
      unwrap(
        api.POST("/api/tournaments/{tournament_id}/sections", {
          params: { path: { tournament_id: tournamentId } },
          body,
        }),
      ),
    onSettled: (_data, _error, vars) => {
      void client.invalidateQueries({ queryKey: keys.tournament(vars.tournamentId) });
    },
  });
}

export function useAddPlayer() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ sectionId, tournamentId: _t, ...body }: SectionVars & PlayerBody) =>
      unwrap(
        api.POST("/api/sections/{section_id}/players", {
          params: { path: { section_id: sectionId } },
          body,
        }),
      ),
    onSettled: (_data, _error, vars) => invalidatePlayers(client, vars),
  });
}

export function useUpdatePlayer() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({
      playerId,
      sectionId: _s,
      tournamentId: _t,
      ...body
    }: SectionVars & PlayerBody & { playerId: string }) =>
      unwrap(
        api.PUT("/api/players/{player_id}", { params: { path: { player_id: playerId } }, body }),
      ),
    onSettled: (_data, _error, vars) => invalidatePlayers(client, vars),
  });
}

export function useWithdrawPlayer() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ playerId, fromRound }: SectionVars & { playerId: string; fromRound: number | null }) =>
      unwrap(
        api.POST("/api/players/{player_id}/withdraw", {
          params: { path: { player_id: playerId } },
          body: { from_round: fromRound, note: "" },
        }),
      ),
    onSettled: (_data, _error, vars) => invalidatePlayers(client, vars),
  });
}

export function useReinstatePlayer() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ playerId }: SectionVars & { playerId: string }) =>
      unwrap(
        api.POST("/api/players/{player_id}/reinstate", {
          params: { path: { player_id: playerId } },
          body: { note: "" },
        }),
      ),
    onSettled: (_data, _error, vars) => invalidatePlayers(client, vars),
  });
}

/** What pairing the next round would do. A mutation, not a query: it runs the engine. */
export function usePreviewPairing() {
  return useMutation({
    mutationFn: ({ sectionId, absent }: SectionVars & { absent: Absence[] }) =>
      unwrap(
        api.POST("/api/sections/{section_id}/pairings/preview", {
          params: { path: { section_id: sectionId } },
          body: { absent },
        }),
      ),
  });
}

export function usePairRound() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ sectionId, absent }: SectionVars & { absent: Absence[] }) =>
      unwrap(
        api.POST("/api/sections/{section_id}/pairings", {
          params: { path: { section_id: sectionId } },
          body: { absent },
        }),
      ),
    onSettled: (_data, _error, vars) => {
      invalidateSection(client, vars.tournamentId);
      void client.invalidateQueries({ queryKey: keys.players(vars.sectionId) });
    },
  });
}

export function useUnpairRound() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ roundId }: RoundVars) =>
      unwrap(api.DELETE("/api/rounds/{round_id}", { params: { path: { round_id: roundId } } })),
    // The round is gone; the screen that showed it navigates away on
    // success and its query is dropped with it. Nothing is removed here,
    // so an observer still mounted does not refetch a 404 mid-transition.
    onSettled: (_data, _error, vars) => invalidateSection(client, vars.tournamentId),
  });
}

export function useRecomputeStandings() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ sectionId }: SectionVars) =>
      unwrap(
        api.POST("/api/sections/{section_id}/standings", {
          params: { path: { section_id: sectionId } },
        }),
      ),
    onSettled: (_data, _error, vars) => {
      void client.invalidateQueries({ queryKey: keys.standings(vars.tournamentId) });
    },
  });
}

function invalidatePlayers(client: ReturnType<typeof useQueryClient>, vars: SectionVars): void {
  void client.invalidateQueries({ queryKey: keys.players(vars.sectionId) });
  void client.invalidateQueries({ queryKey: keys.tournament(vars.tournamentId) });
}
