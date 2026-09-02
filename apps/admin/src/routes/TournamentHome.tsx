import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router";

import { errorMessage, type RoundSummary, type SectionSummary } from "../api";
import { countsOfRound, currentRound, nextAction, type NextAction } from "../boards";
import { ProgressBar } from "../components/ProgressBar";
import { ExportDialog, ReleaseDialog } from "../components/RoundDialogs";
import { RoundStepper } from "../components/RoundStepper";
import { RoundChip } from "../components/StateChip";
import { Banner, Button, Card, EmptyState, Skeleton, cx } from "../components/ui";
import { joinNonEmpty, plural, relativeTime } from "../format";
import { useDevices, useTournament } from "../queries";
import { useNow } from "../useNow";

export function TournamentHome() {
  const { tournamentId = "" } = useParams();
  const tournament = useTournament(tournamentId, true);
  const devices = useDevices(tournamentId);
  // Once a minute, so "last entry 4 min ago" stays true between fetches.
  const now = useNow(60_000);

  if (tournament.isPending) return <Skeleton rows={4} />;
  if (tournament.isError) {
    return <Banner tone="error">Could not load the tournament: {errorMessage(tournament.error)}</Banner>;
  }

  const detail = tournament.data;
  const sections = detail.sections ?? [];
  const open = sections
    .map(currentRound)
    .filter((round): round is RoundSummary => round !== null && round.state === "open");
  const entered = open.reduce((n, r) => n + r.claimed + r.confirmed, 0);
  const total = open.reduce((n, r) => n + r.boards, 0);
  const active = (devices.data ?? []).filter((d) => d.active);
  const lastSeen = (devices.data ?? [])
    .map((d) => d.last_seen_at)
    .filter((t): t is string => Boolean(t))
    .sort()
    .at(-1);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">{detail.name}</h1>
          <p className="text-sm text-slate-500">
            {joinNonEmpty([
              detail.city,
              open.length > 0 && `${entered} of ${plural(total, "board")} entered this round`,
              `${plural(active.length, "phone")} admitted`,
              lastSeen && `last entry ${relativeTime(lastSeen, now)}`,
            ])}
          </p>
        </div>
        <Link
          to={`/t/${tournamentId}/import`}
          className="inline-flex min-h-11 items-center rounded-lg border border-slate-300 bg-white px-4 text-sm font-medium hover:bg-slate-50"
        >
          Import a round…
        </Link>
      </div>

      {sections.length === 0 ? (
        <EmptyState
          title="No sections yet"
          action={
            <Link
              to={`/t/${tournamentId}/import`}
              className="inline-flex min-h-11 items-center rounded-lg bg-ink px-4 text-sm font-medium text-white hover:bg-slate-700"
            >
              Import the paired round
            </Link>
          }
        >
          Pair round 1 in your tournament manager, export it, and import the file here. Each
          file becomes a section; a tournament can hold several.
        </EmptyState>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {sections.map((section) => (
            <SectionCard key={section.id} section={section} tournamentId={tournamentId} />
          ))}
        </div>
      )}
    </div>
  );
}

function SectionCard({ section, tournamentId }: { section: SectionSummary; tournamentId: string }) {
  const navigate = useNavigate();
  const [dialog, setDialog] = useState<"release" | "export" | null>(null);
  const round = currentRound(section);
  const action = nextAction(section);
  const past = (section.rounds ?? [])
    .filter((r) => r.id !== round?.id)
    .sort((a, b) => b.number - a.number);

  const go = () => {
    switch (action.kind) {
      case "import":
        return navigate(`/t/${tournamentId}/import?section=${encodeURIComponent(section.name)}`);
      case "fix":
        return navigate(`/t/${tournamentId}/rounds/${action.round.id}?filter=attention`);
      case "release":
        return setDialog("release");
      case "export":
        return setDialog("export");
    }
  };

  return (
    <Card className="flex flex-col">
      <header className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 px-4 pt-4 sm:px-5">
        <h2 className="text-lg font-semibold">Section {section.name}</h2>
        <p className="text-sm text-slate-500">
          {joinNonEmpty([
            section.manager_label,
            plural(section.players, "player"),
            section.declared_rounds ? `${section.declared_rounds} rounds` : null,
          ])}
        </p>
      </header>

      <div className="flex flex-1 flex-col gap-4 px-4 py-4 sm:px-5">
        {round ? (
          <>
            <div className="flex items-baseline justify-between gap-3">
              <Link
                to={`/t/${tournamentId}/rounds/${round.id}`}
                className="text-base font-medium hover:underline"
              >
                Round {round.number}
              </Link>
              <RoundChip state={round.state} />
            </div>
            <RoundStepper round={round} />
            {round.state !== "exported" && <ProgressBar counts={countsOfRound(round)} />}
          </>
        ) : (
          <p className="text-sm text-slate-500">Nothing imported yet.</p>
        )}

        <div className="mt-auto flex flex-wrap items-center gap-2">
          <Button tone={toneOf(action)} size="lg" onClick={() => void go()} className="flex-1 sm:flex-none">
            {labelOf(action, section.manager_label)}
          </Button>
          {round && action.kind !== "fix" && (
            <Link
              to={`/t/${tournamentId}/rounds/${round.id}`}
              className="inline-flex min-h-12 items-center rounded-lg px-3 text-sm font-medium text-slate-600 hover:bg-slate-100"
            >
              View boards
            </Link>
          )}
        </div>

        {past.length > 0 && (
          <p className="flex flex-wrap items-center gap-1.5 text-xs text-slate-500">
            <span>Earlier:</span>
            {past.map((r) => (
              <Link
                key={r.id}
                to={`/t/${tournamentId}/rounds/${r.id}`}
                className={cx(
                  "rounded-md border px-2 py-0.5 tabular-nums hover:bg-slate-50",
                  r.state === "exported" ? "border-slate-200" : "border-amber-300 bg-amber-50",
                )}
              >
                R{r.number}
              </Link>
            ))}
          </p>
        )}
      </div>

      {round && (
        <>
          <ReleaseDialog
            round={round}
            tournamentId={tournamentId}
            open={dialog === "release"}
            onClose={() => setDialog(null)}
          />
          <ExportDialog
            round={round}
            tournamentId={tournamentId}
            managerLabel={section.manager_label}
            open={dialog === "export"}
            onClose={() => setDialog(null)}
          />
        </>
      )}
    </Card>
  );
}

function labelOf(action: NextAction, managerLabel: string): string {
  switch (action.kind) {
    case "import":
      return `Import round ${action.round_number}`;
    case "fix":
      return `Fix ${joinNonEmpty([
        action.round.disputed > 0 && `${action.round.disputed} disputed`,
        action.round.empty > 0 && `${action.round.empty} empty`,
      ])}`;
    case "release":
      return `Release round ${action.round.number}`;
    case "export":
      return `Export for ${managerLabel}`;
  }
}

function toneOf(action: NextAction): "primary" | "danger" | "success" {
  switch (action.kind) {
    case "fix":
      return action.round.disputed > 0 ? "danger" : "primary";
    case "export":
      return "success";
    default:
      return "primary";
  }
}
