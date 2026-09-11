/**
 * Pairing the next round, behind a look at what it does. The engine runs
 * once for the preview and once for the pairing; it is deterministic, so
 * the boards shown are the boards written unless the roster changed in
 * between, which is exactly what the look is for.
 *
 * A player who is not there tonight is marked absent here, for this round
 * only, with what it is worth to them: half a point or none.
 */

import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router";

import {
  errorMessage,
  type Absence,
  type PairingPlan,
  type PlayerDetail,
  type SectionSummary,
} from "../api";
import { plural } from "../format";
import { usePairRound, usePlayers, usePreviewPairing } from "../queries";
import { useSingleFlight } from "../useSingleFlight";
import { Dialog } from "./Dialog";
import { useToast } from "./Toast";
import { Banner, Button, Select, Skeleton } from "./ui";

export function PairDialog({
  section,
  tournamentId,
  roundNumber,
  open,
  onClose,
}: {
  section: Pick<SectionSummary, "id" | "name">;
  tournamentId: string;
  roundNumber: number;
  open: boolean;
  onClose: () => void;
}) {
  const navigate = useNavigate();
  const toast = useToast();
  const preview = usePreviewPairing();
  const pairRound = usePairRound();
  const players = usePlayers(open ? section.id : undefined);
  const once = useSingleFlight();
  const [absent, setAbsent] = useState<Absence[]>([]);
  const absentKey = useMemo(() => absent.map((a) => `${a.start_rank}${a.result}`).join(","), [absent]);

  // A fresh look every time the dialog opens or the absences change; the
  // plan is not cached, and a stale one must not sit under the skeleton.
  useEffect(() => {
    if (!open) return;
    preview.reset();
    preview.mutate({ sectionId: section.id, tournamentId, absent });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, absentKey]);

  const plan: PairingPlan | undefined = preview.data;
  const blocked = (plan?.blocked_by ?? []).length > 0;

  const close = () => {
    preview.reset();
    pairRound.reset();
    setAbsent([]);
    onClose();
  };

  const confirm = () =>
    once(async () => {
      const data = await pairRound.mutateAsync({ sectionId: section.id, tournamentId, absent });
      toast.success(
        `Round ${data.round_number} paired: ${plural(data.boards, "board")}${
          data.byes > 0 ? `, ${plural(data.byes, "bye")}` : ""
        }.`,
      );
      close();
      void navigate(`/t/${tournamentId}/rounds/${data.round_id}`);
    });

  const active = (players.data?.players ?? []).filter(
    (p) => p.withdrawn_from_round === null || p.withdrawn_from_round > roundNumber,
  );

  return (
    <Dialog
      open={open}
      onClose={close}
      wide
      busy={pairRound.isPending}
      title={`Pair round ${roundNumber} of section ${section.name}`}
      subtitle={
        plan?.seeds
          ? "The first pairing seeds the start numbers by rating; they are final from then on."
          : `The pairing stands on round ${roundNumber - 1}'s results, which become read-only.`
      }
      footer={
        <>
          <Button onClick={close} disabled={pairRound.isPending}>
            Cancel
          </Button>
          <Button
            tone="primary"
            onClick={confirm}
            busy={pairRound.isPending}
            disabled={!plan || blocked || preview.isPending}
          >
            Pair round {roundNumber}
          </Button>
        </>
      }
    >
      {active.length > 0 && (
        <AbsentTonight players={active} absent={absent} onChange={setAbsent} roundNumber={roundNumber} />
      )}
      {preview.isPending && <Skeleton rows={4} className="p-0" />}
      {preview.isError && <Banner tone="error">{errorMessage(preview.error)}</Banner>}
      {plan && !preview.isPending && <PlanView plan={plan} />}
      {pairRound.isError && (
        <Banner tone="error" className="mt-3">
          {errorMessage(pairRound.error)}
        </Banner>
      )}
    </Dialog>
  );
}

/** Who sits this round out. Folded away: most rounds nobody does. */
function AbsentTonight({
  players,
  absent,
  onChange,
  roundNumber,
}: {
  players: PlayerDetail[];
  absent: Absence[];
  onChange: (absent: Absence[]) => void;
  roundNumber: number;
}) {
  const [picking, setPicking] = useState("");
  const byRank = new Map(players.map((p) => [p.start_rank, p]));
  const free = players.filter((p) => !absent.some((a) => a.start_rank === p.start_rank));
  return (
    <details className="mb-3 rounded-lg border border-line bg-subtle/60 px-3 py-2" open={absent.length > 0}>
      <summary className="cursor-pointer text-sm font-semibold text-ink">
        Absent in round {roundNumber}
        {absent.length > 0 && <span className="ml-2 font-normal text-ink-2">({absent.length})</span>}
      </summary>
      <ul className="mt-2 flex flex-col gap-1.5">
        {absent.map((entry) => (
          <li key={entry.start_rank} className="flex flex-wrap items-center gap-2 text-sm">
            <span className="flex-1">
              <span className="mr-1.5 font-mono text-xs text-ink-3">{entry.start_rank}</span>
              {byRank.get(entry.start_rank)?.name ?? `player ${entry.start_rank}`}
            </span>
            <Select
              value={entry.result}
              aria-label={`points for ${byRank.get(entry.start_rank)?.name ?? entry.start_rank}`}
              className="min-h-8 py-0 text-xs"
              onChange={(event) =>
                onChange(
                  absent.map((a) =>
                    a.start_rank === entry.start_rank ? { ...a, result: event.target.value as Absence["result"] } : a,
                  ),
                )
              }
            >
              <option value="H">half a point</option>
              <option value="Z">no points</option>
            </Select>
            <Button
              size="sm"
              tone="ghost"
              aria-label={`${byRank.get(entry.start_rank)?.name ?? entry.start_rank} is playing after all`}
              onClick={() => onChange(absent.filter((a) => a.start_rank !== entry.start_rank))}
            >
              ×
            </Button>
          </li>
        ))}
      </ul>
      {free.length > 0 && (
        <div className="mt-2 flex items-center gap-2">
          <Select
            value={picking}
            onChange={(event) => setPicking(event.target.value)}
            aria-label="mark a player absent"
            className="min-h-8 py-0 text-xs"
          >
            <option value="">Mark absent…</option>
            {free.map((p) => (
              <option key={p.id} value={String(p.start_rank)}>
                {p.start_rank}. {p.name}
              </option>
            ))}
          </Select>
          <Button
            size="sm"
            disabled={!picking}
            onClick={() => {
              if (!picking) return;
              onChange([...absent, { start_rank: Number(picking), result: "Z" }]);
              setPicking("");
            }}
          >
            Add
          </Button>
        </div>
      )}
    </details>
  );
}

function PlanView({ plan }: { plan: PairingPlan }) {
  const blocked = plan.blocked_by ?? [];
  const warnings = plan.warnings ?? [];
  const withdrawn = plan.withdrawn ?? [];
  const byes = plan.byes ?? [];
  const boards = plan.boards ?? [];
  return (
    <div className="flex flex-col gap-3">
      {blocked.length > 0 && (
        <Banner tone="error">
          <p className="font-semibold">This round cannot be paired yet.</p>
          <ul className="mt-1 list-disc pl-5">
            {blocked.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </Banner>
      )}
      {warnings.map((warning) => (
        <Banner key={warning} tone="warn">
          {warning}
        </Banner>
      ))}
      {boards.length > 0 && (
        <table className="w-full text-sm" aria-label={`round ${plan.round_number} boards`}>
          <thead>
            <tr className="border-b border-line text-left text-label-sm text-ink-2">
              <th className="w-10 py-1.5 pr-2 text-right">Brd</th>
              <th className="py-1.5 pr-2">White</th>
              <th className="py-1.5 pr-2">Black</th>
            </tr>
          </thead>
          <tbody>
            {boards.map((board) => (
              <tr key={board.board} className="border-b border-line">
                <td className="py-1.5 pr-2 text-right font-mono font-semibold">{board.board}</td>
                <td className="py-1.5 pr-2">
                  <span className="mr-1.5 font-mono text-xs text-ink-3">{board.white_rank}</span>
                  {board.white_name}
                </td>
                <td className="py-1.5 pr-2">
                  <span className="mr-1.5 font-mono text-xs text-ink-3">{board.black_rank}</span>
                  {board.black_name}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {byes.length > 0 && (
        <p className="text-body-sm text-ink-2">
          {byes.map((bye) => `${bye.name} (${bye.start_rank}): ${byeLabel(bye.result)}`).join(" · ")}
        </p>
      )}
      {withdrawn.length > 0 && (
        <p className="text-body-sm text-ink-3">
          Withdrawn: {withdrawn.map((p) => `${p.name} (${p.start_rank})`).join(", ")}.
        </p>
      )}
      {blocked.length === 0 && (
        <p className="text-body-sm text-ink-2">
          {plural(plan.players_in, "player")} in, {plural(boards.length, "board")}
          {byes.length > 0 ? `, ${plural(byes.length, "bye")}` : ""}.
        </p>
      )}
    </div>
  );
}

function byeLabel(code: string): string {
  switch (code) {
    case "U":
      return "bye, one point";
    case "H":
      return "absent, half a point";
    case "Z":
      return "absent, no points";
    default:
      return `bye (${code})`;
  }
}
