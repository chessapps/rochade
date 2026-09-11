/**
 * The standings, as the manager last handed them over.
 *
 * Nothing on this page is computed here: the points, tiebreaks and ranks are
 * Swiss-Manager's own, read out of its player list when a round was imported
 * or when the list was dropped here on its own. The arbiter names the tiebreak
 * columns once, because the file numbers them and says no more.
 */

import { useState, type FormEvent } from "react";
import { useParams } from "react-router";

import { errorMessage, type SectionStandings } from "../api";
import { DropZone } from "../components/DropZone";
import { PageHeader } from "../components/PageHeader";
import { useToast } from "../components/Toast";
import { Banner, Button, Card, CardHeader, EmptyState, Input, Select, Skeleton } from "../components/ui";
import { plural } from "../format";
import { readText, sniff } from "../importFiles";
import { useImportStandings, useNameTiebreaks, useRecomputeStandings, useStandings, useTournament } from "../queries";
import { tiebreakLabel } from "../tiebreaks";

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
  const native = tournament.data?.native ?? false;

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        back={{ to: `/t/${tournamentId}`, label: tournament.data?.name ?? "Tournament" }}
        title="Standings"
        lead={
          native
            ? "Computed here at every release, with the tie-breaks the section was opened with. A correction to a released board moves the table at once."
            : "As the tournament manager computes them. They arrive with its player list: import a round with both files, or drop the player list here on its own after the last round."
        }
      />

      {sections.length === 0 ? (
        <EmptyState title="No standings yet">
          {native
            ? "The table appears when the first round is released."
            : "Standings come with Swiss-Manager's player list (Extras → Daten Import/Export → Spielerdaten). Import a round with both files, or drop the list below."}
        </EmptyState>
      ) : (
        sections.map((section) => (
          <SectionTable
            key={section.section_id}
            tournamentId={tournamentId}
            section={section}
            native={known.find((s) => s.id === section.section_id)?.native ?? native}
          />
        ))
      )}

      {known.length > 0 && !native && (
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
  native,
}: {
  tournamentId: string;
  section: SectionStandings;
  native: boolean;
}) {
  const columns = Math.max(section.tiebreak_columns, section.tiebreak_names.length);
  const names = Array.from({ length: columns }, (_, i) =>
    native ? tiebreakLabel(section.tiebreak_names[i] ?? `TB${i + 1}`) : section.tiebreak_names[i] || `TB${i + 1}`,
  );
  const inPlay = section.rounds_held > section.after_round;
  const recompute = useRecomputeStandings();
  const toast = useToast();

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
          <span className="text-body-sm text-ink-3">
            round {section.rounds_held} {section.stale ? "played, standings not yet updated" : "in play"}
          </span>
        )}
        {native && (
          <Button
            size="sm"
            busy={recompute.isPending}
            onClick={() =>
              recompute.mutate(
                { sectionId: section.section_id, tournamentId },
                {
                  onSuccess: (outcome) =>
                    outcome.computed
                      ? toast.success(`Standings after round ${outcome.after_round} recomputed.`)
                      : toast.info(`Not recomputed: ${outcome.reason}.`),
                  onError: (error) => toast.error(errorMessage(error)),
                },
              )
            }
          >
            Recompute
          </Button>
        )}
      </CardHeader>
      {section.stale && !native && (
        <Banner tone="warn" className="m-4 mb-0">
          Round {section.rounds_held} went back to {section.manager_label} after these standings
          were exported. Drop a fresh player list below to bring the table up to date.
        </Banner>
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line bg-subtle/90 text-left text-label-sm text-ink-2">
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
              <tr key={row.start_rank} className="border-b border-line hover:bg-subtle/60">
                <td className="px-3 py-1.5 text-right font-mono font-semibold text-ink-2 sm:px-4">
                  {row.rank}
                </td>
                <td className="px-2 py-1.5">
                  {row.title && <span className="mr-1.5 rounded-sm bg-subtle px-1 font-mono text-[11px] font-semibold text-ink-2">{row.title}</span>}
                  {row.name}
                </td>
                <td className="hidden px-2 py-1.5 text-ink-2 sm:table-cell">{row.federation}</td>
                <td className="hidden px-2 py-1.5 text-right font-mono text-ink-2 sm:table-cell">
                  {row.rating ?? ""}
                </td>
                <td className="px-2 py-1.5 text-right font-mono font-bold">{score(row.points)}</td>
                {names.map((name, i) => (
                  <td key={name} className="px-2 py-1.5 text-right font-mono text-ink-2">
                    {score(row.tiebreaks[i])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {columns > 0 && !native && (
        <TiebreakNames tournamentId={tournamentId} section={section} columns={columns} />
      )}
    </Card>
  );
}

/**
 * "2½" rather than "2.5": the way it is written on the wall. A value that is
 * not a whole or a half -- a Sonneborn-Berger of 2.75, a performance rating
 * -- is written as it is, trailing zeros dropped.
 */
export function score(value: number | null | undefined): string {
  if (value === null || value === undefined) return "";
  const doubled = value * 2;
  if (!Number.isInteger(doubled)) return String(Math.round(value * 100) / 100);
  const whole = Math.floor(value);
  const half = doubled % 2 !== 0;
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
      <div className="border-t border-line px-4 py-2 text-body-sm text-ink-2 sm:px-5">
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
      className="flex flex-wrap items-end gap-2 border-t border-line px-4 py-3 sm:px-5"
    >
      {names.map((name, i) => (
        <label key={i} className="flex flex-col gap-1 text-label-sm text-ink-3">
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
  const importStandings = useImportStandings();
  const toast = useToast();

  const take = (picked: FileList | null) => {
    const one = picked?.[0];
    if (!one) return;
    void readText(one).then((content) => setFile({ name: one.name, content }));
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
        <p className="text-body-sm text-ink-2">
          For the table after the last round, or a refresh before the next pairing: Extras →
          Daten Import/Export → <strong>Spielerdaten (Text-File)</strong>, and drop that file here.
          Only points, tiebreaks and ranks change; the players stay as the round import left them.
        </p>
        {sections.length > 1 && (
          <label className="flex items-center gap-2 text-sm">
            <span className="text-ink-2">Section</span>
            <Select value={section} onChange={(event) => setSection(event.target.value)} className="min-h-9 py-0">
              {sections.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </Select>
          </label>
        )}
        <DropZone
          compact
          accept=".txt,text/plain"
          inputLabel="player list file"
          onFiles={take}
          ready={ready}
          title={file ? file.name : "Drop the player list here, or click to choose it"}
          hint={!file && "Spielerdaten (Text-File)"}
        >
          {file && kind !== "players" && (
            <span className="text-body-sm text-rose-text">
              This is not the player list. Standings come with Spielerdaten.
            </span>
          )}
        </DropZone>
        <div className="flex justify-end">
          <Button tone="primary" onClick={run} disabled={!ready} busy={importStandings.isPending}>
            Import standings
          </Button>
        </div>
      </div>
    </Card>
  );
}
