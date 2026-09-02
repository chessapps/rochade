/**
 * The two irreversible steps of a round, each behind a dialog that says what
 * it does. Shared by the tournament home and the round board so the wording
 * and the consent are the same wherever the button was.
 */

import { useState } from "react";
import { useNavigate } from "react-router";

import { errorMessage, type ExportResult, type RoundSummary } from "../api";
import { readyToRelease } from "../boards";
import { plural } from "../format";
import { useExportRound, useReleaseRound } from "../queries";
import { useSingleFlight } from "../useSingleFlight";
import { ConfirmDialog } from "./Dialog";
import { useToast } from "./Toast";
import { Banner } from "./ui";

export interface RoundRef {
  id: string;
  number: number;
  tournamentId: string;
}

export function ReleaseDialog({
  round,
  tournamentId,
  boards,
  open,
  onClose,
}: {
  round: RoundSummary;
  tournamentId: string;
  /** Board numbers still open, when the caller has them; the counts otherwise. */
  boards?: { empty: number[]; disputed: number[] };
  open: boolean;
  onClose: () => void;
}) {
  const toast = useToast();
  const release = useReleaseRound();
  const once = useSingleFlight();
  const ready = readyToRelease(round);
  const [acknowledged, setAcknowledged] = useState(false);

  const confirm = () =>
    once(async () => {
      const data = await release.mutateAsync({ roundId: round.id, tournamentId, force: !ready });
      toast.success(
        `Round ${data.round_number} released: ${plural(data.confirmed, "result")} confirmed.`,
      );
      onClose();
    });

  return (
    <ConfirmDialog
      open={open}
      onClose={() => {
        setAcknowledged(false);
        release.reset();
        onClose();
      }}
      onConfirm={confirm}
      title={`Release round ${round.number}`}
      confirmLabel={ready ? "Release" : "Release anyway"}
      tone={ready ? "primary" : "danger"}
      busy={release.isPending}
      disabled={!ready && !acknowledged}
    >
      <p>
        Releasing confirms every result the players entered — {plural(round.claimed, "board")} —
        and closes the round for entry. Phones can no longer change anything; you still can,
        here, until the round is exported.
      </p>
      {!ready && (
        <>
          <Banner tone="warn" className="mt-3">
            <p className="font-medium">
              {joinCounts(round.empty, round.disputed)} would be left without a confirmed result.
            </p>
            {boards && (
              <p className="mt-1 tabular-nums">
                {boards.empty.length > 0 && <>Empty: boards {boards.empty.join(", ")}. </>}
                {boards.disputed.length > 0 && <>Disputed: boards {boards.disputed.join(", ")}.</>}
              </p>
            )}
            <p className="mt-1">
              They stay open for you to set here, and go into the export blank if you do not.
              The release is recorded as forced.
            </p>
          </Banner>
          <label className="mt-3 flex items-start gap-2">
            <input
              type="checkbox"
              checked={acknowledged}
              onChange={(event) => setAcknowledged(event.target.checked)}
              className="mt-1"
            />
            <span>I know which boards are still open and want to release anyway.</span>
          </label>
        </>
      )}
      {release.isError && (
        <Banner tone="error" className="mt-3">
          {errorMessage(release.error)}
        </Banner>
      )}
    </ConfirmDialog>
  );
}

export function ExportDialog({
  round,
  tournamentId,
  managerLabel,
  open,
  onClose,
}: {
  round: RoundSummary;
  tournamentId: string;
  managerLabel: string;
  open: boolean;
  onClose: () => void;
}) {
  const navigate = useNavigate();
  const exportRound = useExportRound();
  const once = useSingleFlight();
  const unfinished = round.empty + round.disputed;

  const confirm = () =>
    once(async () => {
      const data = await exportRound.mutateAsync({
        roundId: round.id,
        tournamentId,
        force: unfinished > 0,
      });
      download(data);
      onClose();
      // The hand-off lives on the round board, with the file a click away.
      void navigate(`/t/${tournamentId}/rounds/${round.id}`, { state: { justExported: true } });
    });

  return (
    <ConfirmDialog
      open={open}
      onClose={() => {
        exportRound.reset();
        onClose();
      }}
      onConfirm={confirm}
      title={`Export round ${round.number} for ${managerLabel}`}
      confirmLabel="Export and freeze"
      tone="success"
      busy={exportRound.isPending}
    >
      <p>
        This writes the results into a file for {managerLabel} and freezes the round. From
        that point {managerLabel} owns it: nothing here can change a result again, which is
        what stops the two systems disagreeing.
      </p>
      {unfinished > 0 && (
        <Banner tone="warn" className="mt-3">
          {joinCounts(round.empty, round.disputed)} go into the file blank; you enter them in{" "}
          {managerLabel} by hand. The export is recorded as forced.
        </Banner>
      )}
      {exportRound.isError && (
        <Banner tone="error" className="mt-3">
          {errorMessage(exportRound.error)}
        </Banner>
      )}
    </ConfirmDialog>
  );
}

function joinCounts(empty: number, disputed: number): string {
  const parts = [
    empty > 0 ? `${plural(empty, "board")} with no result` : null,
    disputed > 0 ? `${plural(disputed, "disputed board")}` : null,
  ].filter(Boolean);
  return parts.join(" and ");
}

/**
 * The export is a file the arbiter hands to the manager, so it has to leave the
 * browser as one.
 */
export function download(file: Pick<ExportResult, "filename" | "content">): void {
  const blob = new Blob([file.content], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = file.filename;
  // Some mobile browsers only honour a click on an element in the document.
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
