/**
 * Bring the paired round in. Two steps: choose the file, read the diff.
 *
 * Nothing is written until the arbiter has seen what the file changes. The
 * severity logic is in plan.ts; this screen only lays it out so that what
 * blocks is on top, what must be read is in the middle, and the roster diff
 * is folded away underneath.
 */

import { useEffect, useMemo, useState, type DragEvent } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";

import { errorMessage, type ImportPlan, type ManagerSummary } from "../api";
import { currentRound } from "../boards";
import { ConfirmDialog } from "../components/Dialog";
import { useToast } from "../components/Toast";
import { Banner, Button, Card, Field, Input, Select, Skeleton, cx } from "../components/ui";
import { plural } from "../format";
import { canImport, headline, planNotes, type PlanNote, type Severity } from "../plan";
import { useImportRound, useManagers, usePreviewImport, useTournament } from "../queries";
import { useSingleFlight } from "../useSingleFlight";

interface Picked {
  name: string;
  content: string;
}

export function ImportWizard() {
  const { tournamentId = "" } = useParams();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const toast = useToast();
  const tournament = useTournament(tournamentId);
  const managers = useManagers();
  const preview = usePreviewImport();
  const commit = useImportRound();
  const once = useSingleFlight();

  const [section, setSection] = useState(params.get("section") ?? "");
  const [manager, setManager] = useState("");
  const [file, setFile] = useState<Picked | null>(null);
  const [plan, setPlan] = useState<ImportPlan | null>(null);
  const [acknowledged, setAcknowledged] = useState(false);
  const [forcing, setForcing] = useState(false);

  const sections = tournament.data?.sections ?? [];
  const existing = sections.find((s) => s.name === section);

  // The section's own manager first; failing that, the one we have watched work.
  useEffect(() => {
    if (!managers.data || manager) return;
    const fallback = managers.data.find((m) => m.verified) ?? managers.data[0];
    setManager(existing?.manager ?? fallback?.key ?? "");
  }, [managers.data, existing, manager]);
  useEffect(() => {
    if (existing) setManager(existing.manager);
  }, [existing]);
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
    if (!file) return;
    preview.mutate(
      {
        tournamentId,
        section_name: section.trim(),
        content: file.content,
        filename: file.name,
        manager,
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
      if (!file) return;
      const data = await commit.mutateAsync({
        tournamentId,
        section_name: section.trim(),
        content: file.content,
        filename: file.name,
        manager,
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
      <header>
        <Link to={`/t/${tournamentId}`} className="text-sm text-slate-500 hover:underline">
          ← {tournament.data?.name ?? "Tournament"}
        </Link>
        <h1 className="mt-1 text-xl font-semibold">
          {plan ? `What round ${plan.file_round} changes` : "Import the paired round"}
        </h1>
      </header>

      {!plan ? (
        <Card className="flex flex-col gap-4 p-4 sm:p-5">
          <div className="grid gap-4 sm:grid-cols-[8rem_1fr]">
            <Field label="Section" hint={hint}>
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
            <Field label="Tournament manager">
              <Select
                value={manager}
                onChange={(event) => setManager(event.target.value)}
                disabled={Boolean(existing)}
              >
                {(managers.data ?? []).map((option) => (
                  <option key={option.key} value={option.key}>
                    {option.label}
                    {option.verified ? "" : " (unverified)"}
                  </option>
                ))}
              </Select>
            </Field>
          </div>

          {selected && <ManagerNotice manager={selected} />}

          <DropZone file={file} onFile={setFile} />

          {preview.isError && <Banner tone="error">{errorMessage(preview.error)}</Banner>}

          <div className="flex justify-end">
            <Button
              tone="primary"
              size="lg"
              onClick={runPreview}
              busy={preview.isPending}
              disabled={!file || !section.trim() || !manager}
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
        <p className="mt-1 text-amber-800">
          Not yet verified against the real program. What we believe about {manager.label}{" "}
          comes from its documentation, not from watching it work — run the round-trip spike
          before relying on this at an event.
        </p>
      )}
      {(manager.notes ?? []).map((note) => (
        <p key={note} className="mt-1 text-slate-500">
          {note}
        </p>
      ))}
    </Banner>
  );
}

function DropZone({ file, onFile }: { file: Picked | null; onFile: (file: Picked) => void }) {
  const [over, setOver] = useState(false);

  const take = (picked: File | undefined) => {
    if (!picked) return;
    void picked.text().then((content) => onFile({ name: picked.name, content }));
  };
  const onDrop = (event: DragEvent) => {
    event.preventDefault();
    setOver(false);
    take(event.dataTransfer.files[0]);
  };

  return (
    <label
      onDragOver={(event) => {
        event.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={onDrop}
      className={cx(
        "flex cursor-pointer flex-col items-center gap-2 rounded-xl border-2 border-dashed px-4 py-8 text-center transition-colors",
        over ? "border-accent bg-accent-soft/40" : "border-slate-300 hover:border-slate-400",
        file && "border-emerald-400 bg-emerald-50",
      )}
    >
      <input
        type="file"
        accept=".trf,.txt,text/plain"
        className="sr-only"
        onChange={(event) => take(event.target.files?.[0])}
      />
      {file ? (
        <>
          <p className="font-medium text-emerald-900">{file.name}</p>
          <p className="text-sm text-emerald-800">
            {plural(file.content.split(/\r?\n/).filter(Boolean).length, "line")} · choose another
            file to replace it
          </p>
        </>
      ) : (
        <>
          <p className="font-medium">Drop the exported file here</p>
          <p className="text-sm text-slate-500">or click to choose it — a .trf or .txt export</p>
        </>
      )}
    </label>
  );
}

const SEVERITY_STYLE: Record<Severity, string> = {
  blocking: "border-rose-300 bg-rose-50 text-rose-900",
  acknowledge: "border-amber-300 bg-amber-50 text-amber-900",
  informational: "border-slate-200 bg-white text-slate-600",
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
        <p className="text-lg font-medium">{headline(plan)}</p>
        <p className="text-sm text-slate-500">
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
            className="text-sm text-slate-600 underline-offset-2 hover:underline"
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
            className={cx("rounded-lg border px-3 py-2 text-sm", SEVERITY_STYLE[note.severity])}
          >
            {note.text}
          </li>
        ))}
      </ul>
    </div>
  );
}
