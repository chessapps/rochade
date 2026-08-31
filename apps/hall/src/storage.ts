import { createStore, get, set } from "idb-keyval";

import type { PendingClaim, QueueStorage } from "./queue";
import type { BoardList } from "./api";

const store = createStore("seebach-hall", "state");

const QUEUE_KEY = "claim-queue";
const BOARDS_KEY = "board-list";

/**
 * IndexedDB rather than localStorage: the board list for a large open is a few
 * hundred kilobytes, and losing it because a quota was hit would strand every
 * phone in the hall the moment the network dips.
 */
export const queueStorage: QueueStorage = {
  async read() {
    return (await get<PendingClaim[]>(QUEUE_KEY, store)) ?? [];
  },
  async write(claims) {
    await set(QUEUE_KEY, claims, store);
  },
};

export async function cacheBoards(boards: BoardList): Promise<void> {
  await set(BOARDS_KEY, boards, store);
}

export async function cachedBoards(): Promise<BoardList | null> {
  return (await get<BoardList>(BOARDS_KEY, store)) ?? null;
}

const TOKEN_KEY = "seebach.device-token";
const TOURNAMENT_KEY = "seebach.tournament-id";

/**
 * The QR code lands the phone on /hall/<tournament>#t=<token>. The token is
 * moved out of the URL immediately so it does not survive in history or get
 * shared by a screenshot of the address bar.
 */
export function adoptCredentialFromUrl(location: Location, history: History): void {
  const hash = new URLSearchParams(location.hash.replace(/^#/, ""));
  const token = hash.get("t");
  const tournament = location.pathname.split("/").filter(Boolean).pop();

  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
    if (tournament) localStorage.setItem(TOURNAMENT_KEY, tournament);
    history.replaceState(null, "", location.pathname);
  }
}

export function deviceToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function tournamentId(): string | null {
  return localStorage.getItem(TOURNAMENT_KEY);
}

export function forgetCredential(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(TOURNAMENT_KEY);
}
