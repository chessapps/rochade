/**
 * The frame around every screen: who we are (the wordmark), where we are (the
 * tournament, then Rounds · Standings · Devices), whether the desk is live,
 * and the way out. Nothing else lives up here.
 */

import { useIsFetching } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Link, NavLink, useNavigate, useParams } from "react-router";

import type { Account } from "../auth";
import { pollInterval, useRound, useTournament, useTournaments } from "../queries";
import { Castle, LogOut } from "./icons";
import { Select, cx } from "./ui";

export function Shell({
  account,
  onSignOut,
  children,
}: {
  account?: Account;
  onSignOut: () => void;
  children: ReactNode;
}) {
  const { tournamentId, roundId } = useParams();
  const tournaments = useTournaments();
  const tournament = useTournament(tournamentId);

  return (
    <div className="flex min-h-full flex-col">
      <header className="no-print sticky top-0 z-20 border-b border-line bg-card/95 backdrop-blur">
        <div className="mx-auto flex min-h-14 max-w-[1240px] flex-wrap items-center gap-x-4 gap-y-2 px-4 py-2 sm:px-6">
          <Link to="/?all" className="group flex items-center gap-2.5">
            <span className="flex size-8 items-center justify-center rounded-lg bg-ink text-white transition-colors group-hover:bg-accent [&>svg]:size-4">
              <Castle />
            </span>
            <span className="flex items-baseline gap-1.5">
              <span className="text-base font-bold tracking-tight">Rochade</span>
              <span className="hidden rounded-sm border border-line bg-subtle px-1.5 py-0.5 text-label-sm text-ink-2 sm:inline">
                Arbiter desk
              </span>
            </span>
          </Link>

          {tournamentId && (
            <>
              <span aria-hidden className="hidden h-5 w-px bg-line sm:block" />
              <TournamentSwitcher
                current={tournamentId}
                name={tournament.data?.name}
                options={tournaments.data ?? []}
              />
              <nav className="flex gap-1 border-line sm:border-l sm:pl-3">
                <Tab to={`/t/${tournamentId}`} end>
                  Rounds
                </Tab>
                <Tab to={`/t/${tournamentId}/standings`}>Standings</Tab>
                <Tab to={`/t/${tournamentId}/devices`}>Devices</Tab>
              </nav>
            </>
          )}

          <span className="flex-1" />

          <LivePill roundId={roundId} />
          <span aria-hidden className="hidden h-5 w-px bg-line sm:block" />

          <div className="flex items-center gap-2">
            {account?.kind === "oidc" && (
              <span className="flex items-center gap-2" title={account.name}>
                <span
                  aria-hidden
                  className="flex size-7 items-center justify-center rounded-full bg-slate-800 font-mono text-[11px] font-semibold text-white"
                >
                  {initials(account.name)}
                </span>
                <span className="hidden max-w-40 truncate text-xs font-semibold text-ink md:inline">
                  {account.name}
                </span>
              </span>
            )}
            <button
              type="button"
              onClick={onSignOut}
              className="inline-flex min-h-9 items-center gap-1.5 rounded px-2.5 text-xs font-medium text-ink-2 hover:bg-subtle hover:text-ink [&>svg]:size-3.5"
            >
              <LogOut />
              Sign out
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-[1240px] flex-1 px-4 py-4 sm:px-6 sm:py-6">{children}</main>

      <footer className="no-print mt-auto border-t border-line bg-card py-3">
        <div className="mx-auto flex max-w-[1240px] flex-wrap items-center justify-between gap-2 px-4 font-mono text-[11px] text-ink-3 sm:px-6">
          <span>Rochade Arbiter Desk v{__APP_VERSION__}</span>
          <span>Results entered in the hall, released at the desk, exported to the manager.</span>
        </div>
      </footer>
    </div>
  );
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  const letters = (parts.length > 1 ? [parts[0]!, parts.at(-1)!] : parts).map((p) => p[0] ?? "");
  return letters.join("").toUpperCase().slice(0, 2) || "?";
}

/**
 * Whether the desk is talking to the API. On a round page it says how often;
 * the dot pulses while a request is in flight.
 */
function LivePill({ roundId }: { roundId: string | undefined }) {
  const fetching = useIsFetching() > 0;
  const round = useRound(roundId);
  const every = roundId && round.data ? pollInterval(round.data.state) : undefined;
  const label =
    every === false
      ? "Frozen"
      : every
        ? `Live · ${Math.round(every / 1000)}s`
        : "Live";
  return (
    <span className="hidden items-center gap-1.5 rounded-full border border-line bg-subtle px-2.5 py-1 font-mono text-[11px] font-medium text-ink-2 sm:flex">
      <span aria-hidden className="relative flex size-2">
        {fetching && (
          <span className="absolute inline-flex size-full animate-ping rounded-full bg-emerald-400 opacity-75" />
        )}
        <span
          className={cx(
            "relative inline-flex size-2 rounded-full",
            every === false ? "bg-round-exported" : "bg-state-confirmed",
          )}
        />
      </span>
      {label}
    </span>
  );
}

function Tab({ to, end, children }: { to: string; end?: boolean; children: ReactNode }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        cx(
          "inline-flex min-h-9 items-center rounded-md border px-3 text-xs transition-colors lg:min-h-8",
          isActive
            ? "border-blue-200 bg-blue-50 font-semibold text-blue-700"
            : "border-transparent font-medium text-ink-2 hover:bg-subtle hover:text-ink",
        )
      }
    >
      {children}
    </NavLink>
  );
}

function TournamentSwitcher({
  current,
  name,
  options,
}: {
  current: string;
  name: string | undefined;
  options: { id: string; name: string }[];
}) {
  const navigate = useNavigate();
  const pill =
    "flex min-h-9 items-center gap-2 rounded-md border border-line bg-subtle px-2.5 text-xs font-semibold text-ink lg:min-h-8";
  // One tournament is the usual day: show its name, no control to fiddle with.
  if (options.length <= 1) {
    return (
      <span className={pill}>
        <span aria-hidden className="size-2 rounded-full bg-state-confirmed" />
        <span className="max-w-56 truncate">{name ?? "…"}</span>
      </span>
    );
  }
  return (
    <Select
      aria-label="tournament"
      value={current}
      onChange={(event) => void navigate(`/t/${event.target.value}`)}
      className={cx(pill, "min-h-9 max-w-64 truncate py-0")}
    >
      {options.map((option) => (
        <option key={option.id} value={option.id}>
          {option.name}
        </option>
      ))}
    </Select>
  );
}
