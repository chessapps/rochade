/**
 * Bring the paired round in. Two steps: choose the file, read the diff.
 *
 * Nothing is written until the arbiter has seen what the file changes. The
 * severity logic is in plan.ts; this screen only lays it out so that what
 * blocks is on top, what must be read is in the middle, and the roster diff
 * is folded away underneath.
 */

import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate, useParams, useSearchParams } from "react-router";

import { errorMessage, type ImportPlan, type ManagerSummary } from "../api";
import { Chip } from "../components/StateChip";
import { currentRound } from "../boards";
import { ConfirmDialog } from "../components/Dialog";
import { DropZone as Zone } from "../components/DropZone";
import { PageHeader } from "../components/PageHeader";
import { useToast } from "../components/Toast";
import { Banner, Button, Card, Field, Input, Skeleton, cx } from "../components/ui";
import { plural } from "../format";
import { canImport, headline, planNotes, type PlanNote, type Severity } from "../plan";
import {
  dropHint,
  isReady,
  joinContents,
  KIND_LABEL,
  missing,
  readText,
  rosterNote,
  primaryName,
  sniff,
  withFile,
  type PickedFile,
} from "../importFiles";
import { useImportRound, useManagers, usePreviewImport, useTournament } from "../queries";
import { useSingleFlight } from "../useSingleFlight";


export function ImportWizard() {
  const { tournamentId = "" } = useParams();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  // Files dropped on the tournament home arrive here through router state.
  const handed = (useLocation().state as { files?: PickedFile[] } | null)?.files ?? [];
  const toast = useToast();
  const tournament = useTournament(tournamentId);
  const managers = useManagers();
  const preview = usePreviewImport();
  const commit = useImportRound();
  const once = useSingleFlight();

  const [section, setSection] = useState(params.get("section") ?? "");
  const [files, setFiles] = useState<PickedFile[]>(handed);
  const [plan, setPlan] = useState<ImportPlan | null>(null);
  const [acknowledged, setAcknowledged] = useState(false);
  const [forcing, setForcing] = useState(false);

  const sections = tournament.data?.sections ?? [];
  const existing = sections.find((s) => s.name === section);
  // From round two the pairings alone will do: the section names them.
  const rosterHeld = (existing?.players ?? 0) > 0;

  // The program was chosen when the tournament was created; nothing to ask.
  const manager = tournament.data?.manager;
  useEffect(() => {
    if (!section && sections.length === 0) setSection("A");
  }, [section, sections.length]);

  const selected = managers.data?.find((m) => m.key === manager);
  const latest = existing ? currentRound(existing) : null;
  const hint = !existing
    ? "new section"
    : latest === null
      ? "round 1 expected"
      : latest.state === "exported"
        ? `round ${latest.number + 1} expected`
        : `round ${latest.number} is not exported yet`;

  const runPreview = () => {
    if (!isReady(files, rosterHeld, manager)) return;
    preview.mutate(
      {
        tournamentId,
        section_name: section.trim(),
        content: joinContents(files),
        filename: primaryName(files),
        // Never forced: the preview must show the block that a forced commit
        // would step over, or the arbiter never reads it.
        force: false,
      },
      {
        onSuccess: (data) => {
          setPlan(data);
          setAcknowledged(false);
        },
      },
    );
  };

  const runImport = (force: boolean) =>
    once(async () => {
      if (!isReady(files, rosterHeld, manager)) return;
      const data = await commit.mutateAsync({
        tournamentId,
        section_name: section.trim(),
        content: joinContents(files),
        filename: primaryName(files),
        force,
      });
      toast.success(
        `Round ${data.round_number} imported: ${plural(data.boards, "board")}` +
          (data.claims_carried > 0
            ? `, ${plural(data.claims_carried, "entry", "entries")} kept.`
            : "."),
      );
      void navigate(`/t/${tournamentId}/rounds/${data.round_id}`, { replace: true });
    });

  if (tournament.isPending || managers.isPending) return <Skeleton rows={4} />;
  if (tournament.isError || managers.isError) {
    return (
      <Banner tone="error">
        Could not load what the import needs:{" "}
        {errorMessage(tournament.error ?? managers.error)}
      </Banner>
    );
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <PageHeader
        back={{ to: `/t/${tournamentId}`, label: tournament.data?.name ?? "Tournament" }}
        title={plan ? `What round ${plan.file_round} changes` : "Import the paired round"}
      />

      {!plan ? (
        <Card className="flex flex-col gap-4 p-4 sm:p-5">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <Field label="Section" hint={hint} className="w-32">
              <Input
                value={section}
                onChange={(event) => setSection(event.target.value)}
                list="section-names"
                placeholder="A"
                autoComplete="off"
              />
              <datalist id="section-names">
                {sections.map((s) => (
                  <option key={s.id} value={s.name} />
                ))}
              </datalist>
            </Field>
            <p className="flex items-center gap-2 pb-1 text-body-sm text-ink-2">
              Files from
              <Chip tone="emerald">{tournament.data?.manager_label ?? manager}</Chip>
            </p>
          </div>

          {selected && <ManagerNotice manager={selected} />}

          <DropZone
            files={files}
            rosterHeld={rosterHeld}
            manager={manager}
            onFile={(picked) => setFiles((held) => withFile(held, picked))}
            onClear={() => setFiles([])}
          />

          {preview.isError && <Banner tone="error">{errorMessage(preview.error)}</Banner>}

          <div className="flex justify-end">
            <Button
              tone="primary"
              size="lg"
              onClick={runPreview}
              busy={preview.isPending}
              disabled={!isReady(files, rosterHeld, manager) || !section.trim() || !manager}
            >
              Preview the changes
            </Button>
          </div>
        </Card>
      ) : (
        <PlanReview
          plan={plan}
          acknowledged={acknowledged}
          onAcknowledge={setAcknowledged}
          busy={commit.isPending}
          error={commit.isError ? errorMessage(commit.error) : null}
          onBack={() => {
            setPlan(null);
            commit.reset();
          }}
          onImport={() => (canImport(plan) ? void runImport(false) : setForcing(true))}
        />
      )}

      <ConfirmDialog
        open={forcing}
        onClose={() => setForcing(false)}
        onConfirm={() => {
          setForcing(false);
          void runImport(true);
        }}
        title="Import over the block?"
        confirmLabel="Import anyway"
        tone="danger"
      >
        <p>
          The preview says this file should not be imported as things stand. Importing anyway
          replaces what we hold for section {plan?.section_name} with the file, and is recorded
          as forced.
        </p>
        <ul className="mt-2 list-disc pl-5">
          {(plan?.blocked_by ?? []).map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      </ConfirmDialog>
    </div>
  );
}

function ManagerNotice({ manager }: { manager: ManagerSummary }) {
  const unverified =
    manager.exports_unplayed_round === "unverified" || manager.merges_on_import === "unverified";
  return (
    <Banner tone="info">
      {manager.export_howto && (
        <p>
          <span className="font-medium">In {manager.label}:</span> {manager.export_howto}
        </p>
      )}
      {unverified && (
        <p className="mt-1 text-amber-text">
          Not yet verified against the real program. What we believe about {manager.label}{" "}
          comes from its documentation, not from watching it work — run the round-trip spike
          before relying on this at an event.
        </p>
      )}
      {(manager.notes ?? []).map((note) => (
        <p key={note} className="mt-1 text-ink-3">
          {note}
        </p>
      ))}
    </Banner>
  );
}

function countLines(content: string): number {
  return content.split("\n").filter((line) => line.trim()).length;
}

function DropZone({
  files,
  rosterHeld,
  manager,
  onFile,
  onClear,
}: {
  files: PickedFile[];
  rosterHeld: boolean;
  manager: string | undefined;
  onFile: (file: PickedFile) => void;
  onClear: () => void;
}) {
  const take = (picked: FileList | null) => {
    for (const one of Array.from(picked ?? [])) {
      void readText(one).then((content) => onFile({ name: one.name, content, kind: sniff(content) }));
    }
  };
  const note = missing(files, rosterHeld, manager);
  const roster = rosterNote(files, rosterHeld);

  return (
    <div className="space-y-2">
      <Zone
        multiple
        accept=".trf,.txt,text/plain"
        onFiles={take}
        ready={files.length > 0 && note === null}
        title={manager === "vega" ? "Drop the exported file here" : "Drop the exported files here"}
        hint={dropHint(manager)}
      />

      {files.length > 0 && (
        <ul className="space-y-1">
          {files.map((file) => (
            <li
              key={file.kind + file.name}
              className="flex flex-wrap items-baseline justify-between gap-x-3 rounded border border-line bg-subtle px-3 py-2 text-sm"
            >
              <span className="font-mono text-xs font-medium [overflow-wrap:anywhere]">{file.name}</span>
              <span className="text-body-sm text-ink-2">
                {KIND_LABEL[file.kind]} ·{" "}
                {plural(countLines(file.content), "line")}
              </span>
            </li>
          ))}
        </ul>
      )}

      {note && files.length > 0 && <Banner tone="warn">{note}</Banner>}
      {roster && <Banner tone="info">{roster}</Banner>}
      {files.length > 0 && (
        <button
          type="button"
          onClick={onClear}
          className="text-body-sm text-ink-2 underline underline-offset-2 hover:text-ink"
        >
          Start the file choice again
        </button>
      )}
    </div>
  );
}

const SEVERITY_STYLE: Record<Severity, string> = {
  blocking: "border-rose-line bg-rose-soft text-rose-text",
  acknowledge: "border-amber-line bg-amber-soft text-amber-text",
  informational: "border-line bg-card text-ink-2",
};

function PlanReview({
  plan,
  acknowledged,
  onAcknowledge,
  busy,
  error,
  onBack,
  onImport,
}: {
  plan: ImportPlan;
  acknowledged: boolean;
  onAcknowledge: (value: boolean) => void;
  busy: boolean;
  error: string | null;
  onBack: () => void;
  onImport: () => void;
}) {
  const notes = useMemo(() => planNotes(plan), [plan]);
  const groups = useMemo(() => {
    const by: Record<Severity, PlanNote[]> = { blocking: [], acknowledge: [], informational: [] };
    for (const note of notes) by[note.severity].push(note);
    return by;
  }, [notes]);
  const blocked = !canImport(plan);
  const mustRead = groups.acknowledge.length > 0;
  const [showInfo, setShowInfo] = useState(false);

  return (
    <Card className="flex flex-col gap-4 p-4 sm:p-5">
      <div>
        <p className="text-headline-sm">{headline(plan)}</p>
        <p className="text-body-sm text-ink-2">
          {plan.section_exists
            ? `Replaces what we hold for section ${plan.section_name}.`
            : `Creates section ${plan.section_name}.`}
          {plan.is_expected_round ? " The round we expected." : ""}
        </p>
      </div>

      {groups.blocking.length > 0 && (
        <NoteList title="Why this should not be imported" notes={groups.blocking} />
      )}
      {groups.acknowledge.length > 0 && (
        <NoteList title="Read before importing" notes={groups.acknowledge} />
      )}
      {groups.informational.length > 0 && (
        <div>
          <button
            type="button"
            onClick={() => setShowInfo((v) => !v)}
            className="text-sm text-ink-2 underline-offset-2 hover:text-ink hover:underline"
            aria-expanded={showInfo}
          >
            {showInfo ? "Hide" : "Show"} {plural(groups.informational.length, "detail")} — players
            and kept entries
          </button>
          {showInfo && <NoteList notes={groups.informational} className="mt-2" />}
        </div>
      )}
      {notes.length === 0 && (
        <Banner tone="success">Nothing to note: the file matches what we expected.</Banner>
      )}

      {mustRead && !blocked && (
        <label className="flex items-start gap-2 text-sm">
          <input
            type="checkbox"
            checked={acknowledged}
            onChange={(event) => onAcknowledge(event.target.checked)}
            className="mt-1"
          />
          <span>I have read the changes above.</span>
        </label>
      )}

      {error && <Banner tone="error">{error}</Banner>}

      <div className="flex flex-wrap justify-end gap-2">
        <Button onClick={onBack} disabled={busy}>
          Back
        </Button>
        <Button
          tone={blocked ? "danger" : "primary"}
          size="lg"
          onClick={onImport}
          busy={busy}
          disabled={mustRead && !acknowledged && !blocked}
        >
          {blocked ? "Import anyway…" : `Import round ${plan.file_round}`}
        </Button>
      </div>
    </Card>
  );
}

function NoteList({
  title,
  notes,
  className,
}: {
  title?: string;
  notes: PlanNote[];
  className?: string;
}) {
  return (
    <div className={className}>
      {title && <h3 className="mb-2 text-sm font-semibold">{title}</h3>}
      <ul className="flex flex-col gap-1">
        {notes.map((note, index) => (
          <li
            key={index}
            className={cx("rounded border px-3 py-2 text-sm", SEVERITY_STYLE[note.severity])}
          >
            {note.text}
          </li>
        ))}
      </ul>
    </div>
  );
}
