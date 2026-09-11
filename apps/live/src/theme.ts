/**
 * Light or dark, and who decides.
 *
 * Three choices, one of which is "whatever the system says". The choice lives
 * in localStorage; the resolved theme lives on <html data-theme>, which is
 * what the CSS keys on. index.html sets that attribute before the first
 * paint from the same key, so a dark desk never flashes white on load.
 */

import { useEffect, useSyncExternalStore } from "react";

export type ThemeChoice = "light" | "dark" | "system";
export type Theme = "light" | "dark";

export const THEME_KEY = "rochade.theme";
const CHOICES: readonly ThemeChoice[] = ["light", "dark", "system"];

const listeners = new Set<() => void>();

export function readChoice(): ThemeChoice {
  try {
    const stored = localStorage.getItem(THEME_KEY);
    return CHOICES.includes(stored as ThemeChoice) ? (stored as ThemeChoice) : "system";
  } catch {
    return "system";
  }
}

export function systemTheme(): Theme {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

export function resolve(choice: ThemeChoice, system: Theme = systemTheme()): Theme {
  return choice === "system" ? system : choice;
}

/** Put the resolved theme on the document and tell the browser chrome. */
export function apply(choice: ThemeChoice): Theme {
  const theme = resolve(choice);
  const root = document.documentElement;
  root.dataset.theme = theme;
  root.style.colorScheme = theme;
  document
    .querySelector<HTMLMetaElement>('meta[name="theme-color"]')
    ?.setAttribute("content", theme === "dark" ? "#0b0f17" : "#f8fafc");
  return theme;
}

export function setChoice(choice: ThemeChoice): void {
  try {
    if (choice === "system") localStorage.removeItem(THEME_KEY);
    else localStorage.setItem(THEME_KEY, choice);
  } catch {
    // Private mode: the choice holds for this page and no longer.
  }
  apply(choice);
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  const media = window.matchMedia?.("(prefers-color-scheme: dark)");
  const onSystem = () => {
    if (readChoice() === "system") apply("system");
    listener();
  };
  const onStorage = (event: StorageEvent) => {
    if (event.key === THEME_KEY || event.key === null) {
      apply(readChoice());
      listener();
    }
  };
  media?.addEventListener("change", onSystem);
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(listener);
    media?.removeEventListener("change", onSystem);
    window.removeEventListener("storage", onStorage);
  };
}

/** The current choice and the theme it resolves to, kept live. */
export function useTheme(): { choice: ThemeChoice; theme: Theme; setChoice: typeof setChoice } {
  const choice = useSyncExternalStore(subscribe, readChoice, () => "system" as ThemeChoice);
  const theme = useSyncExternalStore(
    subscribe,
    () => resolve(readChoice()),
    () => "light" as Theme,
  );
  // The attribute is normally set before React runs; this covers a test or a
  // page that skipped the inline script.
  useEffect(() => {
    apply(choice);
  }, [choice]);
  return { choice, theme, setChoice };
}
