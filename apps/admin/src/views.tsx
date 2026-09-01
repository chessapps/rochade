import { useState } from "react";

import type {
  ArbiterQueue,
  DeviceSummary,
  GameResult,
  ImportPlan,
  ManagerSummary,
  QueueEntry,
  RoundSummary,
  TournamentDetail,
} from "./api";
import { canImport, headline, planNotes, type Severity } from "./plan";

const SEVERITY_STYLE: Record<Severity, string> = {
  blocking: "border-rose-300 bg-rose-50 text-rose-900",
  acknowledge: "border-amber-300 bg-amber-50 text-amber-900",
  informational: "border-slate-200 bg-white text-slate-600",
};

const ROUND_STATE_LABEL: Record<string, string> = {
  open: "open for entry",
  confirmed: "released, ready to export",
  exported: "exported — frozen",
};

export function SignIn({ onSignIn }: { onSignIn: (token: string) => void }) {
  const [value, setValue] = useState("");
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        if (value.trim()) onSignIn(value.trim());
      }}
      className="mx-auto mt-24 flex max-w-sm flex-col gap-3 p-6"
    >
      <h1 className="text-xl font-semibold">Seebach — arbiter</h1>
      <p className="text-sm text-slate-500">
        Sign in with your staff token. Passkeys arrive with the identity provider.
      </p>
      <input
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder="staff token"
        className="rounded-lg border border-slate-300 px-3 py-2"
      />
      <button type="submit" className="rounded-lg bg-slate-900 px-4 py-2 text-white">
        Sign in
      </button>
    </form>
  );
}

export function SectionPanel({
  detail,
  onRelease,
  onExport,
  busy,
}: {
  detail: TournamentDetail;
  onRelease: (round: RoundSummary) => void;
  onExport: (round: RoundSummary) => void;
  busy: boolean;
}) {
  return (
    <div className="flex flex-col gap-4">
      {(detail.sections ?? []).map((section) => (
        <section key={section.id} className="rounded-xl border border-slate-200 bg-white">
          <header className="flex items-baseline justify-between border-b border-slate-100 px-4 py-3">
            <h2 className="font-semibold">Section {section.name}</h2>
            <p className="text-sm text-slate-500">
              {section.players} players
              {section.declared_rounds ? ` · ${section.declared_rounds} rounds` : ""}
            </p>
          </header>
          <table className="w-full text-sm">
            <thead className="text-left text-slate-500">
              <tr>
                <th className="px-4 py-2 font-medium">Round</th>
                <th className="px-4 py-2 font-medium">State</th>
                <th className="px-4 py-2 font-medium">Boards</th>
                <th className="px-4 py-2 font-medium" />
              </tr>
            </thead>
            <tbody>
              {(section.rounds ?? []).map((round) => (
                <tr key={round.id} className="border-t border-slate-100">
                  <td className="px-4 py-3 tabular-nums">{round.number}</td>
                  <td className="px-4 py-3">
                    {ROUND_STATE_LABEL[round.state] ?? round.state}
                  </td>
                  <td className="px-4 py-3 tabular-nums">
                    <BoardCounts round={round} />
                  </td>
                  <td className="px-4 py-3 text-right">
                    <RoundActions
                      round={round}
                      busy={busy}
                      onRelease={onRelease}
                      onExport={onExport}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ))}
      {(detail.sections ?? []).length === 0 && (
        <p className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-slate-500">
          No sections yet. Import a Vega file to begin.
        </p>
      )}
    </div>
  );
}

function BoardCounts({ round }: { round: RoundSummary }) {
  const parts = [
    round.disputed > 0 ? `${round.disputed} disputed` : null,
    round.empty > 0 ? `${round.empty} empty` : null,
    round.claimed > 0 ? `${round.claimed} entered` : null,
    round.confirmed > 0 ? `${round.confirmed} confirmed` : null,
  ].filter(Boolean);
  return (
    <span className={round.disputed > 0 ? "text-rose-700" : undefined}>
      {parts.length > 0 ? parts.join(" · ") : `${round.boards} boards`}
    </span>
  );
}

function RoundActions({
  round,
  busy,
  onRelease,
  onExport,
}: {
  round: RoundSummary;
  busy: boolean;
  onRelease: (round: RoundSummary) => void;
  onExport: (round: RoundSummary) => void;
}) {
  const ready = round.empty === 0 && round.disputed === 0;
  return (
    <span className="flex justify-end gap-2">
      {round.state === "open" && (
        <button
          type="button"
          disabled={busy}
          onClick={() => onRelease(round)}
          className={`rounded-lg px-3 py-1.5 text-white disabled:opacity-50 ${
            ready ? "bg-slate-900" : "bg-slate-400"
          }`}
        >
          {ready ? "Release" : "Release…"}
        </button>
      )}
      {round.state === "confirmed" && (
        <button
          type="button"
          disabled={busy}
          onClick={() => onExport(round)}
          className="rounded-lg bg-emerald-700 px-3 py-1.5 text-white disabled:opacity-50"
        >
          Export for Vega
        </button>
      )}
    </span>
  );
}

export function ImportPanel({
  plan,
  section,
  onSection,
  managers,
  manager,
  onManager,
  onFile,
  onPreview,
  onImport,
  onCancel,
  busy,
}: {
  plan: ImportPlan | null;
  section: string;
  onSection: (value: string) => void;
  managers: ManagerSummary[];
  manager: string;
  onManager: (value: string) => void;
  onFile: (file: File) => void;
  onPreview: () => void;
  onImport: (force: boolean) => void;
  onCancel: () => void;
  busy: boolean;
}) {
  const selected = managers.find((m) => m.key === manager);
  const [acknowledged, setAcknowledged] = useState(false);
  const notes = plan ? planNotes(plan) : [];
  const mustRead = notes.some((note) => note.severity === "acknowledge");
  const blocked = plan ? !canImport(plan) : false;

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4">
      <h2 className="font-semibold">Import a Vega file</h2>

      <div className="mt-3 flex flex-wrap items-end gap-3">
        <label className="flex flex-col text-sm">
          <span className="text-slate-500">Manager</span>
          <select
            value={manager}
            onChange={(event) => onManager(event.target.value)}
            className="mt-1 rounded-lg border border-slate-300 px-3 py-2"
          >
            {managers.map((option) => (
              <option key={option.key} value={option.key}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col text-sm">
          <span className="text-slate-500">Section</span>
          <input
            value={section}
            onChange={(event) => onSection(event.target.value)}
            className="mt-1 w-28 rounded-lg border border-slate-300 px-3 py-2"
          />
        </label>
        <label className="flex flex-col text-sm">
          <span className="text-slate-500">TRF file</span>
          <input
            type="file"
            accept=".trf,.txt,text/plain"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) onFile(file);
            }}
            className="mt-1 text-sm"
          />
        </label>
        <button
          type="button"
          onClick={onPreview}
          disabled={busy}
          className="rounded-lg border border-slate-300 px-4 py-2 disabled:opacity-50"
        >
          Preview
        </button>
      </div>

      {selected && <ManagerNotice manager={selected} />}

      {plan && (
        <div className="mt-4 border-t border-slate-100 pt-4">
          <p className="font-medium">{headline(plan)}</p>
          <p className="text-sm text-slate-500">
            {plan.section_exists
              ? `Replacing what we hold for section ${plan.section_name}.`
              : `Creating section ${plan.section_name}.`}
          </p>

          <ul className="mt-3 flex flex-col gap-1">
            {notes.map((note, index) => (
              <li
                key={index}
                className={`rounded-lg border px-3 py-2 text-sm ${SEVERITY_STYLE[note.severity]}`}
              >
                {note.text}
              </li>
            ))}
          </ul>

          {mustRead && !blocked && (
            <label className="mt-3 flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={acknowledged}
                onChange={(event) => setAcknowledged(event.target.checked)}
              />
              I have read the changes above.
            </label>
          )}

          <div className="mt-4 flex gap-2">
            <button
              type="button"
              onClick={() => onImport(blocked)}
              disabled={busy || (mustRead && !acknowledged && !blocked)}
              className="rounded-lg bg-slate-900 px-4 py-2 text-white disabled:opacity-40"
            >
              {blocked ? "Import anyway" : "Import"}
            </button>
            <button
              type="button"
              onClick={onCancel}
              className="rounded-lg border border-slate-300 px-4 py-2"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </section>
  );
}

function ManagerNotice({ manager }: { manager: ManagerSummary }) {
  const unverified =
    manager.exports_unplayed_round === "unverified" || manager.merges_on_import === "unverified";
  return (
    <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
      <p className="text-slate-600">
        Reads <code>{manager.reads_format}</code>, writes <code>{manager.writes_format}</code>.
      </p>
      {unverified && (
        <p className="mt-1 text-amber-800">
          Not yet verified against the real program. What we believe about{" "}
          {manager.label} comes from its documentation, not from watching it work — run
          the round-trip spike before relying on this at an event.
        </p>
      )}
      {(manager.notes ?? []).map((note) => (
        <p key={note} className="mt-1 text-slate-500">
          {note}
        </p>
      ))}
    </div>
  );
}

export function QueuePanel({
  queue,
  onSet,
  onResolve,
  busy,
}: {
  queue: ArbiterQueue;
  onSet: (entry: QueueEntry, white: string, black: string) => void;
  onResolve: (entry: QueueEntry, result: GameResult) => void;
  busy: boolean;
}) {
  const entries = queue.entries ?? [];
  return (
    <section className="rounded-xl border border-slate-200 bg-white">
      <header className="flex items-baseline justify-between border-b border-slate-100 px-4 py-3">
        <h2 className="font-semibold">Needs attention</h2>
        <p className="text-sm text-slate-500">
          {queue.disputed} disputed · {queue.empty} empty · {queue.claimed} entered
        </p>
      </header>
      {entries.length === 0 ? (
        <p className="px-4 py-8 text-center text-slate-500">
          Nothing outstanding. Every open board has a result.
        </p>
      ) : (
        <ul>
          {entries.map((entry) => (
            <li
              key={entry.game_id}
              className="flex flex-wrap items-center gap-3 border-t border-slate-100 px-4 py-3"
            >
              <span className="w-24 shrink-0 text-sm text-slate-500 tabular-nums">
                {entry.section_name} · R{entry.round_number} · B{entry.board}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate">{entry.white_name}</span>
                <span className="block truncate text-slate-500">
                  {entry.black_name ?? "bye"}
                </span>
              </span>
              <StateBadge entry={entry} />
              <BoardControls
                entry={entry}
                busy={busy}
                onSet={onSet}
                onResolve={onResolve}
              />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function StateBadge({ entry }: { entry: QueueEntry }) {
  if (entry.state === "disputed") {
    return (
      <span className="rounded-lg bg-rose-100 px-2 py-1 text-xs text-rose-800">
        disputed: "{entry.white_result}" vs "{entry.disputed_white_result}"
      </span>
    );
  }
  if (entry.state === "claimed") {
    return (
      <span className="rounded-lg bg-amber-100 px-2 py-1 text-xs text-amber-800">
        entered "{entry.white_result}"
      </span>
    );
  }
  if (entry.state === "confirmed") {
    return (
      <span className="rounded-lg bg-emerald-100 px-2 py-1 text-xs text-emerald-800">
        confirmed
      </span>
    );
  }
  return <span className="rounded-lg bg-slate-100 px-2 py-1 text-xs">no result</span>;
}

const OVERRIDES: { label: string; white: string; black: string }[] = [
  { label: "1:0", white: "1", black: "0" },
  { label: "½:½", white: "=", black: "=" },
  { label: "0:1", white: "0", black: "1" },
  { label: "+:-", white: "+", black: "-" },
  { label: "-:+", white: "-", black: "+" },
  { label: "-:-", white: "-", black: "-" },
];

function BoardControls({
  entry,
  busy,
  onSet,
  onResolve,
}: {
  entry: QueueEntry;
  busy: boolean;
  onSet: (entry: QueueEntry, white: string, black: string) => void;
  onResolve: (entry: QueueEntry, result: GameResult) => void;
}) {
  if (entry.state === "disputed") {
    return (
      <span className="flex gap-1">
        {(["white_win", "draw", "black_win"] as GameResult[]).map((result, index) => (
          <button
            key={result}
            type="button"
            disabled={busy}
            onClick={() => onResolve(entry, result)}
            className="rounded-lg border border-rose-300 px-2 py-1 text-sm disabled:opacity-50"
          >
            {["1:0", "½:½", "0:1"][index]}
          </button>
        ))}
      </span>
    );
  }
  return (
    <span className="flex flex-wrap gap-1">
      {OVERRIDES.map((option) => (
        <button
          key={option.label}
          type="button"
          disabled={busy || entry.is_bye}
          onClick={() => onSet(entry, option.white, option.black)}
          className="rounded-lg border border-slate-300 px-2 py-1 text-sm disabled:opacity-40"
        >
          {option.label}
        </button>
      ))}
    </span>
  );
}

export function DevicePanel({
  devices,
  onIssue,
  onRevoke,
  issued,
  onDismissIssued,
  busy,
}: {
  devices: DeviceSummary[];
  onIssue: (label: string) => void;
  onRevoke: (device: DeviceSummary) => void;
  issued: { label: string; qr_payload: string; token: string } | null;
  onDismissIssued: () => void;
  busy: boolean;
}) {
  const [label, setLabel] = useState("");
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4">
      <h2 className="font-semibold">Devices in the hall</h2>
      <p className="mt-1 text-sm text-slate-500">
        Each token admits one phone to this tournament for today. Revoking is
        immediate and every claim it made stays in the audit log.
      </p>

      <div className="mt-3 flex gap-2">
        <input
          value={label}
          onChange={(event) => setLabel(event.target.value)}
          placeholder="label, e.g. by board 1"
          className="flex-1 rounded-lg border border-slate-300 px-3 py-2"
        />
        <button
          type="button"
          disabled={busy}
          onClick={() => {
            onIssue(label);
            setLabel("");
          }}
          className="rounded-lg bg-slate-900 px-4 py-2 text-white disabled:opacity-50"
        >
          Issue QR
        </button>
      </div>

      {issued && (
        <div className="mt-3 rounded-lg border border-emerald-300 bg-emerald-50 p-3">
          <p className="text-sm font-medium text-emerald-900">
            Shown once — this token cannot be recovered.
          </p>
          <code className="mt-2 block overflow-x-auto rounded bg-white p-2 text-xs">
            {issued.qr_payload}
          </code>
          <button
            type="button"
            onClick={onDismissIssued}
            className="mt-2 rounded-lg border border-emerald-300 px-3 py-1 text-sm"
          >
            Done
          </button>
        </div>
      )}

      <ul className="mt-4">
        {devices.map((device) => (
          <li
            key={device.id}
            className="flex items-center gap-3 border-t border-slate-100 py-2 text-sm"
          >
            <span className="flex-1">{device.label || "unlabelled"}</span>
            <span className="text-slate-500">
              {device.last_seen_at
                ? `seen ${new Date(device.last_seen_at).toLocaleTimeString()}`
                : "never used"}
            </span>
            {device.active ? (
              <button
                type="button"
                disabled={busy}
                onClick={() => onRevoke(device)}
                className="rounded-lg border border-rose-300 px-3 py-1 text-rose-700 disabled:opacity-50"
              >
                Revoke
              </button>
            ) : (
              <span className="rounded-lg bg-slate-100 px-3 py-1 text-slate-500">
                {device.revoked_at ? "revoked" : "expired"}
              </span>
            )}
          </li>
        ))}
        {devices.length === 0 && (
          <li className="py-4 text-center text-slate-500">No devices yet.</li>
        )}
      </ul>
    </section>
  );
}

export function FreezeWarning({
  round,
  onConfirm,
  onCancel,
}: {
  round: RoundSummary;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="fixed inset-0 flex items-center justify-center bg-black/40 p-4">
      <div className="max-w-md rounded-xl bg-white p-5">
        <h2 className="text-lg font-semibold">Export round {round.number} to Vega</h2>
        <p className="mt-2 text-sm text-slate-600">
          This writes the results into the file and freezes the round. From that
          point Vega owns it: nothing here can change a result again, which is
          what stops the two systems disagreeing.
        </p>
        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-lg border border-slate-300 px-4 py-2"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className="rounded-lg bg-emerald-700 px-4 py-2 text-white"
          >
            Export and freeze
          </button>
        </div>
      </div>
    </div>
  );
}
