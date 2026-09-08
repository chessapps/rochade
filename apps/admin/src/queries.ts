/**
 * Every read and write the screens make, as hooks.
 *
 * The keys are narrow on purpose: releasing a round touches that round and its
 * tournament, not the device list. Polling lives here too, so a screen says
 * "watch this round" and nothing more.
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationOptions,
} from "@tanstack/react-query";

import {
  api,
  ApiError,
  type CreateTournamentBody,
  type GameResult,
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
  managers: ["managers"] as const,
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

export interface ImportVars {
  tournamentId: string;
  section_name: string;
  content: string;
  filename: string;
  manager: string;
  force: boolean;
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
}
