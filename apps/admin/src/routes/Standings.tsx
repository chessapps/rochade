/**
 * The standings, as the manager last handed them over.
 *
 * Nothing on this page is computed here: the points, tiebreaks and ranks are
 * Swiss-Manager's own, read out of its player list when a round was imported
 * or when the list was dropped here on its own. The arbiter names the tiebreak
 * columns once, because the file numbers them and says no more.
 */

import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router";

import { errorMessage, type SectionStandings } from "../api";
import { useToast } from "../components/Toast";
import { Banner, Button, Card, CardHeader, EmptyState, Input, Skeleton, cx } from "../components/ui";
import { plural } from "../format";
import { sniff } from "../importFiles";
import { useImportStandings, useNameTiebreaks, useStandings, useTournament } from "../queries";

export function Standings() {
  const { tournamentId = "" } = useParams();
  const tournament = useTournament(tournamentId);
  const standings = useStandings(tournamentId);

  if (standings.isPending) return <Skeleton rows={6} />;
  if (standings.isError) {
    return <Banner tone="error">Could not load the standings: {errorMessage(standings.error)}</Banner>;
  }

  const sections = standings.data.sections ?? [];
  const known = tournament.data?.sections ?? [];

  return (
    <div className="flex flex-col gap-4">
      <header>
        <Link to={`/t/${tournamentId}`} className="text-sm text-slate-500 hover:underline">
          ← {tournament.data?.name ?? "Tournament"}
        </Link>
        <h1 className="mt-1 text-xl font-semibold">Standings</h1>
        <p className="mt-1 max-w-2xl text-sm text-slate-500">
          As the tournament manager computes them. They arrive with its player list: import a
          round with both files, or drop the player list here on its own after the last round.
        </p>
      </header>

      {sections.length === 0 ? (
        <EmptyState title="No standings yet">
          Standings come with Swiss-Manager's player list (Extras → Daten Import/Export →
          Spielerdaten). Import a round with both files, or drop the list below.
        </EmptyState>
      ) : (
        sections.map((section) => (
          <SectionTable key={section.section_id} tournamentId={tournamentId} section={section} />
        ))
      )}

      {known.length > 0 && (
        <ImportStandingsCard
          tournamentId={tournamentId}
          sections={known.map((s) => s.name)}
          initial={sections[0]?.section_name ?? known[0]?.name ?? ""}
        />
      )}
    </div>
  );
}

function SectionTable({
  tournamentId,
  section,
}: {
  tournamentId: string;
  section: SectionStandings;
}) {
  const columns = Math.max(section.tiebreak_columns, section.tiebreak_names.length);
  const names = Array.from({ length: columns }, (_, i) => section.tiebreak_names[i] || `TB${i + 1}`);
  const inPlay = section.rounds_held > section.after_round;

  return (
    <Card>
      <CardHeader
        title={`Section ${section.section_name}`}
        aside={
          section.after_round === 0
            ? "starting order"
            : `after round ${section.after_round} · ${section.manager_label}`
        }
      >
        {inPlay && (
          <span className="text-xs text-slate-500">
            round {section.rounds_held} {section.stale ? "played, standings not yet updated" : "in play"}
          </span>
        )}
      </CardHeader>
      {section.stale && (
        <Banner tone="warn" className="m-4 mb-0">
          Round {section.rounds_held} went back to {section.manager_label} after these standings
          were exported. Drop a fresh player list below to bring the table up to date.
        </Banner>
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-xs tracking-wide text-slate-500 uppercase">
              <th className="w-10 px-3 py-2 text-right sm:px-4">#</th>
              <th className="px-2 py-2">Name</th>
              <th className="hidden px-2 py-2 sm:table-cell">Fed</th>
              <th className="hidden px-2 py-2 text-right sm:table-cell">Rating</th>
              <th className="px-2 py-2 text-right">Pts</th>
              {names.map((name) => (
                <th key={name} className="px-2 py-2 text-right whitespace-nowrap">
                  {name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {section.rows.map((row) => (
              <tr key={row.start_rank} className="border-b border-slate-100 tabular-nums">
                <td className="px-3 py-1.5 text-right font-semibold text-slate-500 sm:px-4">
                  {row.rank}
                </td>
                <td className="px-2 py-1.5">
                  {row.title && <span className="mr-1 text-xs text-slate-500">{row.title}</span>}
                  {row.name}
                </td>
                <td className="hidden px-2 py-1.5 text-slate-500 sm:table-cell">{row.federation}</td>
                <td className="hidden px-2 py-1.5 text-right text-slate-500 sm:table-cell">
                  {row.rating ?? ""}
                </td>
                <td className="px-2 py-1.5 text-right font-semibold">{score(row.points)}</td>
                {names.map((name, i) => (
                  <td key={name} className="px-2 py-1.5 text-right text-slate-600">
                    {score(row.tiebreaks[i])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {columns > 0 && (
        <TiebreakNames tournamentId={tournamentId} section={section} columns={columns} />
      )}
    </Card>
  );
}

/** "2½" rather than "2.5": the way it is written on the wall. */
export function score(value: number | null | undefined): string {
  if (value === null || value === undefined) return "";
  const whole = Math.floor(value);
  const half = value - whole >= 0.5;
  if (whole === 0 && half) return "½";
  return `${whole}${half ? "½" : ""}`;
}

function TiebreakNames({
  tournamentId,
  section,
  columns,
}: {
  tournamentId: string;
  section: SectionStandings;
  columns: number;
}) {
  const [editing, setEditing] = useState(false);
  const [names, setNames] = useState<string[]>(() =>
    Array.from({ length: columns }, (_, i) => section.tiebreak_names[i] ?? ""),
  );
  const save = useNameTiebreaks();
  const toast = useToast();

  const submit = (event: FormEvent) => {
    event.preventDefault();
    save.mutate(
      { tournamentId, sectionName: section.section_name, names },
      {
        onSuccess: () => {
          toast.success("Tiebreak names saved.");
          setEditing(false);
        },
        onError: (error) => toast.error(errorMessage(error)),
      },
    );
  };

  if (!editing) {
    return (
      <div className="border-t border-slate-100 px-4 py-2 text-xs text-slate-500 sm:px-5">
        The file numbers the tiebreak columns and does not say which system each is.{" "}
        <button
          type="button"
          onClick={() => setEditing(true)}
          className="underline underline-offset-2 hover:text-ink"
        >
          {section.tiebreak_names.length > 0 ? "Rename them" : "Name them"}
        </button>
        {" "}from your tournament settings.
      </div>
    );
  }

  return (
    <form
      onSubmit={submit}
      className="flex flex-wrap items-end gap-2 border-t border-slate-100 px-4 py-3 sm:px-5"
    >
      {names.map((name, i) => (
        <label key={i} className="flex flex-col gap-1 text-xs text-slate-500">
          TB{i + 1}
          <Input
            value={name}
            onChange={(event) =>
              setNames((held) => held.map((n, j) => (j === i ? event.target.value : n)))
            }
            placeholder={["Buchholz", "Buchholz cut 1", "Sonneborn-Berger", "Wins"][i] ?? ""}
            className="w-40"
            aria-label={`name of tiebreak ${i + 1}`}
          />
        </label>
      ))}
      <Button type="submit" tone="primary" size="sm" busy={save.isPending}>
        Save names
      </Button>
      <Button size="sm" tone="ghost" onClick={() => setEditing(false)} disabled={save.isPending}>
        Cancel
      </Button>
    </form>
  );
}

function ImportStandingsCard({
  tournamentId,
  sections,
  initial,
}: {
  tournamentId: string;
  sections: string[];
  initial: string;
}) {
  const [section, setSection] = useState(initial);
  const [file, setFile] = useState<{ name: string; content: string } | null>(null);
  const [over, setOver] = useState(false);
  const importStandings = useImportStandings();
  const toast = useToast();

  const take = (picked: FileList | null) => {
    const one = picked?.[0];
    if (!one) return;
    void one.text().then((content) => setFile({ name: one.name, content }));
  };
  const kind = file ? sniff(file.content) : null;
  const ready = kind === "players" && section.trim() !== "";

  const run = () =>
    file &&
    importStandings.mutate(
      { tournamentId, sectionName: section, content: file.content },
      {
        onSuccess: (outcome) => {
          toast.success(
            `Standings after round ${outcome.after_round}: ${plural(outcome.players_updated, "player")} updated.` +
              ((outcome.unknown_start_numbers ?? []).length > 0
                ? ` Start numbers not in this section: ${(outcome.unknown_start_numbers ?? []).join(", ")}.`
                : ""),
          );
          setFile(null);
        },
        onError: (error) => toast.error(errorMessage(error)),
      },
    );

  return (
    <Card>
      <CardHeader title="Import standings on their own" />
      <div className="flex flex-col gap-3 p-4 sm:p-5">
        <p className="text-sm text-slate-500">
          For the table after the last round, or a refresh before the next pairing: Extras →
          Daten Import/Export → <strong>Spielerdaten (Text-File)</strong>, and drop that file here.
          Only points, tiebreaks and ranks change; the players stay as the round import left them.
        </p>
        {sections.length > 1 && (
          <label className="flex items-center gap-2 text-sm">
            <span className="text-slate-600">Section</span>
            <select
              value={section}
              onChange={(event) => setSection(event.target.value)}
              className="min-h-9 rounded-lg border border-slate-300 bg-white px-2"
            >
              {sections.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </label>
        )}
        <label
          onDragOver={(event) => {
            event.preventDefault();
            setOver(true);
          }}
          onDragLeave={() => setOver(false)}
          onDrop={(event) => {
            event.preventDefault();
            setOver(false);
            take(event.dataTransfer.files);
          }}
          className={cx(
            "flex cursor-pointer flex-col items-center gap-1 rounded-xl border-2 border-dashed px-4 py-6 text-center text-sm transition-colors",
            over ? "border-accent bg-accent-soft/40" : "border-slate-300 hover:border-slate-400",
            ready && "border-emerald-400 bg-emerald-50",
          )}
        >
          <input
            type="file"
            accept=".txt,text/plain"
            className="sr-only"
            aria-label="player list file"
            onChange={(event) => take(event.target.files)}
          />
          {file ? (
            <span className="font-medium">{file.name}</span>
          ) : (
            <span className="font-medium">Drop the player list here, or click to choose it</span>
          )}
          {file && kind !== "players" && (
            <span className="text-rose-700">
              This is not the player list. Standings come with Spielerdaten.
            </span>
          )}
        </label>
        <div className="flex justify-end">
          <Button tone="primary" onClick={run} disabled={!ready} busy={importStandings.isPending}>
            Import standings
          </Button>
        </div>
      </div>
    </Card>
  );
}
