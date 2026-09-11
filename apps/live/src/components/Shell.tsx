/**
 * The frame around every public page: the wordmark, the way back to the
 * list, and the theme switch. Nothing to sign into.
 */

import type { ReactNode } from "react";
import { Link } from "react-router";

import { Castle } from "./icons";
import { ThemeSwitch } from "./ThemeSwitch";

export function Shell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-full flex-col">
      <header className="sticky top-0 z-20 border-b border-line bg-card/95 backdrop-blur">
        <div className="mx-auto flex min-h-14 max-w-[1100px] items-center gap-4 px-4 py-2 sm:px-6">
          <Link to="/" className="group flex items-center gap-2.5">
            <span className="flex size-8 items-center justify-center rounded-lg bg-ink text-on-ink transition-colors group-hover:bg-accent [&>svg]:size-4">
              <Castle />
            </span>
            <span className="flex items-baseline gap-1.5">
              <span className="text-base font-bold tracking-tight">Rochade</span>
              <span className="rounded-sm border border-line bg-subtle px-1.5 py-0.5 text-label-sm text-ink-2">
                Live
              </span>
            </span>
          </Link>
          <span className="flex-1" />
          <ThemeSwitch />
        </div>
      </header>

      <main className="mx-auto w-full max-w-[1100px] flex-1 px-4 py-4 sm:px-6 sm:py-6">{children}</main>

      <footer className="mt-auto border-t border-line bg-card py-3">
        <div className="mx-auto flex max-w-[1100px] flex-wrap items-center justify-between gap-2 px-4 font-mono text-[11px] text-ink-3 sm:px-6">
          <span>Rochade Live v{__APP_VERSION__}</span>
          <span>Results as they come in. Preliminary until the arbiter confirms them.</span>
        </div>
      </footer>
    </div>
  );
}
