/**
 * The watch list: players a visitor wants to get back to quickly. Kept in
 * this browser only, as a plain list of where each player lives, so an
 * account could hold the same list one day without changing its shape.
 */

import { useSyncExternalStore } from "react";

export const WATCH_KEY = "rochade.live.watch";

export interface Watched {
  slug: string;
  sectionId: string;
  startRank: number;
  name: string;
}

const listeners = new Set<() => void>();
let cached: Watched[] | null = null;

export function readWatchList(): Watched[] {
  if (cached) return cached;
  try {
    const raw = localStorage.getItem(WATCH_KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    cached = Array.isArray(parsed) ? parsed.filter(isWatched) : [];
  } catch {
    cached = [];
  }
  return cached;
}

function isWatched(value: unknown): value is Watched {
  if (!value || typeof value !== "object") return false;
  const v = value as Record<string, unknown>;
  return (
    typeof v.slug === "string" &&
    typeof v.sectionId === "string" &&
    typeof v.startRank === "number" &&
    typeof v.name === "string"
  );
}

function write(list: Watched[]): void {
  cached = list;
  try {
    localStorage.setItem(WATCH_KEY, JSON.stringify(list));
  } catch {
    // Private mode: the list holds for this page and no longer.
  }
  for (const listener of listeners) listener();
}

export function same(a: Watched, b: Watched): boolean {
  return a.slug === b.slug && a.sectionId === b.sectionId && a.startRank === b.startRank;
}

export function isWatching(entry: Watched): boolean {
  return readWatchList().some((w) => same(w, entry));
}

export function toggleWatch(entry: Watched): boolean {
  const list = readWatchList();
  if (list.some((w) => same(w, entry))) {
    write(list.filter((w) => !same(w, entry)));
    return false;
  }
  write([...list, entry]);
  return true;
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  const onStorage = (event: StorageEvent) => {
    if (event.key === WATCH_KEY || event.key === null) {
      cached = null;
      listener();
    }
  };
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", onStorage);
  };
}

export function useWatchList(): Watched[] {
  return useSyncExternalStore(subscribe, readWatchList, () => []);
}

/** Test affordance: forget the cache so the next read hits storage. */
export function _resetWatchCache(): void {
  cached = null;
}
