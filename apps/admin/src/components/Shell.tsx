/**
 * The frame around every screen: where am I (breadcrumb), where else can I go
 * (Rounds · Standings · Devices), and the way out. Nothing else lives up here.
 */

import type { ReactNode } from "react";
import { Link, NavLink, useNavigate, useParams } from "react-router";

import { useTournament, useTournaments } from "../queries";
import { Select, cx } from "./ui";

export function Shell({ onSignOut, children }: { onSignOut: () => void; children: ReactNode }) {
  const { tournamentId } = useParams();
  const tournaments = useTournaments();
  const tournament = useTournament(tournamentId);

  return (
    <div className="flex min-h-full flex-col">
      <header className="no-print sticky top-0 z-20 border-b border-slate-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-2 sm:px-6">
          <Link to="/?all" className="text-lg font-semibold tracking-tight">
            Seebach
          </Link>
          {tournamentId && (
            <>
              <span className="text-slate-300">/</span>
              <TournamentSwitcher
                current={tournamentId}
                name={tournament.data?.name}
                options={tournaments.data ?? []}
              />
              <nav className="flex gap-1 text-sm">
                <Tab to={`/t/${tournamentId}`} end>
                  Rounds
                </Tab>
                <Tab to={`/t/${tournamentId}/standings`}>Standings</Tab>
                <Tab to={`/t/${tournamentId}/devices`}>Devices</Tab>
              </nav>
            </>
          )}
          <span className="flex-1" />
          <button
            type="button"
            onClick={onSignOut}
            className="min-h-9 rounded-lg px-3 text-sm text-slate-600 hover:bg-slate-100"
          >
            Sign out
          </button>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-4 sm:px-6 sm:py-6">{children}</main>
    </div>
  );
}

function Tab({ to, end, children }: { to: string; end?: boolean; children: ReactNode }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        cx(
          "min-h-9 rounded-lg px-3 py-1.5 font-medium",
          isActive ? "bg-slate-100 text-ink" : "text-slate-600 hover:bg-slate-50",
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
  // One tournament is the usual day: show its name, no control to fiddle with.
  if (options.length <= 1) {
    return <span className="truncate font-medium">{name ?? "…"}</span>;
  }
  return (
    <Select
      aria-label="tournament"
      value={current}
      onChange={(event) => void navigate(`/t/${event.target.value}`)}
      className="min-h-9 max-w-56 truncate py-0 text-sm"
    >
      {options.map((option) => (
        <option key={option.id} value={option.id}>
          {option.name}
        </option>
      ))}
    </Select>
  );
}
