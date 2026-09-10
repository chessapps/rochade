/**
 * Deleting a tournament takes its sections, rounds, results, audit log and
 * phone tokens with it, and nothing brings them back. So the arbiter types
 * the tournament's name before the button does anything, and the server
 * checks the same name again.
 */

import { useEffect, useState } from "react";
import { useNavigate } from "react-router";

import { errorMessage } from "../api";
import { useDeleteTournament } from "../queries";
import { ConfirmDialog } from "./Dialog";
import { useToast } from "./Toast";
import { Banner, Field, Input } from "./ui";

export function DeleteTournamentDialog({
  open,
  onClose,
  tournament,
}: {
  open: boolean;
  onClose: () => void;
  tournament: { id: string; name: string };
}) {
  const navigate = useNavigate();
  const toast = useToast();
  const [typed, setTyped] = useState("");
  useEffect(() => {
    if (!open) setTyped("");
  }, [open]);

  const remove = useDeleteTournament({
    onSuccess: (data) => {
      toast.success(`${data.name} deleted.`);
      onClose();
      void navigate("/?all", { replace: true });
    },
  });
  const matches = typed.trim() === tournament.name;

  return (
    <ConfirmDialog
      open={open}
      onClose={onClose}
      onConfirm={() => {
        if (matches && !remove.isPending) {
          remove.mutate({ tournamentId: tournament.id, confirmName: typed.trim() });
        }
      }}
      title="Delete this tournament?"
      subtitle={tournament.name}
      tone="danger"
      confirmLabel="Delete tournament"
      busy={remove.isPending}
      disabled={!matches}
    >
      <div className="flex flex-col gap-3">
        <p>
          Every section, round and result goes with it, along with the audit log and the phones'
          access. There is no undo: the only way back is importing the round files again.
        </p>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            if (matches && !remove.isPending) {
              remove.mutate({ tournamentId: tournament.id, confirmName: typed.trim() });
            }
          }}
        >
          <Field label="Type the tournament's name to confirm" hint={tournament.name}>
            <Input
              value={typed}
              onChange={(event) => setTyped(event.target.value)}
              placeholder={tournament.name}
              autoComplete="off"
              spellCheck={false}
              autoFocus
            />
          </Field>
        </form>
        {remove.isError && <Banner tone="error">{errorMessage(remove.error)}</Banner>}
      </div>
    </ConfirmDialog>
  );
}
