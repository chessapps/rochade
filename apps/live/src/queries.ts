/**
 * The public reads, as hooks. A round or a standings table that can still
 * change is asked again every 20 seconds while the tab is visible; a
 * tournament with nothing in play is not asked again at all.
 */

import { useQuery } from "@tanstack/react-query";

import { api, unwrap } from "./api";

export const POLL_MS = 20_000;

export const keys = {
  tournaments: ["public", "tournaments"] as const,
  tournament: (slug: string) => ["public", "tournament", slug] as const,
  round: (slug: string, sectionId: string, number: number) =>
    ["public", "round", slug, sectionId, number] as const,
  standings: (slug: string, sectionId: string) => ["public", "standings", slug, sectionId] as const,
  player: (slug: string, sectionId: string, startRank: number) =>
    ["public", "player", slug, sectionId, startRank] as const,
};

export function useTournaments() {
  return useQuery({
    queryKey: keys.tournaments,
    queryFn: () => unwrap(api.GET("/api/public/tournaments")),
  });
}

export function useTournament(slug: string, live = false) {
  return useQuery({
    queryKey: keys.tournament(slug),
    queryFn: () =>
      unwrap(api.GET("/api/public/tournaments/{slug}", { params: { path: { slug } } })),
    enabled: Boolean(slug),
    refetchInterval: live ? POLL_MS : false,
  });
}

export function useRound(slug: string, sectionId: string, number: number, live = false) {
  return useQuery({
    queryKey: keys.round(slug, sectionId, number),
    queryFn: () =>
      unwrap(
        api.GET("/api/public/tournaments/{slug}/sections/{section_id}/rounds/{number}", {
          params: { path: { slug, section_id: sectionId, number } },
        }),
      ),
    enabled: Boolean(slug && sectionId && number > 0),
    refetchInterval: live ? POLL_MS : false,
    // A round picker switches boards without a blank flash in between.
    placeholderData: (previous) => previous,
  });
}

export function useStandings(slug: string, sectionId: string, live = false) {
  return useQuery({
    queryKey: keys.standings(slug, sectionId),
    queryFn: () =>
      unwrap(
        api.GET("/api/public/tournaments/{slug}/sections/{section_id}/standings", {
          params: { path: { slug, section_id: sectionId } },
        }),
      ),
    enabled: Boolean(slug && sectionId),
    refetchInterval: live ? POLL_MS : false,
  });
}

export function usePlayer(slug: string, sectionId: string, startRank: number, live = false) {
  return useQuery({
    queryKey: keys.player(slug, sectionId, startRank),
    queryFn: () =>
      unwrap(
        api.GET("/api/public/tournaments/{slug}/sections/{section_id}/players/{start_rank}", {
          params: { path: { slug, section_id: sectionId, start_rank: startRank } },
        }),
      ),
    enabled: Boolean(slug && sectionId && startRank > 0),
    refetchInterval: live ? POLL_MS : false,
  });
}
