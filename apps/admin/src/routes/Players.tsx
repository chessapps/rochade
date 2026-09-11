/**
 * The player list, one table per section. The same screen for every
 * tournament: a manager's list is read here and changed there, a section
 * Rochade pairs itself is entered here -- before round 1 in any order, after
 * it as late entries -- and players leave and return from here too.
 */

import { useState, type FormEvent } from "react";
import { useParams, useSearchParams } from "react-router";

import { errorMessage, type PlayerBody, type PlayerDetail, type PlayerList, type SectionSummary } from "../api";
import { ConfirmDialog, Dialog } from "../components/Dialog";
import { PageHeader } from "../components/PageHeader";
import { Chip } from "../components/StateChip";
import { useToast } from "../components/Toast";
import { Banner, Button, Card, CardHeader, EmptyState, Field, Input, Select, Skeleton, cx } from "../components/ui";
import { plural } from "../format";
import {
  useAddPlayer,
  usePlayers,
  useReinstatePlayer,
  useTournament,
  useUpdatePlayer,
  useWithdrawPlayer,
} from "../queries";

export function Players() {
  const { tournamentId = "" } = useParams();
  const [params] = useSearchParams();
  const tournament = useTournament(tournamentId);

  if (tournament.isPending) return <Skeleton rows={4} />;
  if (tournament.isError) {
    return <Banner tone="error">Could not load the tournament: {errorMessage(tournament.error)}</Banner>;
  }
  const detail = tournament.data;
  const sections = detail.sections ?? [];
  const wanted = params.get("section");
  const matching = sections.filter((s) => s.id === wanted);
  const shown = matching.length > 0 ? matching : sections;

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        back={{ to: `/t/${tournamentId}`, label: detail.name }}
        title="Players"
        lead={
          detail.native
            ? "Enter the field here. Before round 1 the order does not matter: the first pairing seeds it by rating. After that a new player is a late entry and takes the next number."
            : `The list as ${detail.manager_label} exported it. It is changed there and comes back with the next round's import.`
        }
        actions={
          detail.native ? (
            <Button tone="primary" size="sm" to={`/t/${tournamentId}/sections/new`}>
              New section…
            </Button>
          ) : undefined
        }
      />
      {sections.length === 0 ? (
        <EmptyState
          title="No sections yet"
          action={
            detail.native ? (
              <Button tone="primary" to={`/t/${tournamentId}/sections/new`}>
                Open the first section
              </Button>
            ) : undefined
          }
        >
          {detail.native
            ? "Players belong to a section: an Open, a U12, a B group."
            : `Import the paired round from ${detail.manager_label}; each file becomes a section.`}
        </EmptyState>
      ) : (
        shown.map((section) => (
          <SectionPlayers key={section.id} section={section} tournamentId={tournamentId} />
        ))
      )}
    </div>
  );
}

function SectionPlayers({ section, tournamentId }: { section: SectionSummary; tournamentId: string }) {
  const players = usePlayers(section.id);
  const [editing, setEditing] = useState<PlayerDetail | null>(null);
  const [leaving, setLeaving] = useState<PlayerDetail | null>(null);
  const toast = useToast();
  const reinstate = useReinstatePlayer();

  if (players.isPending) return <Skeleton rows={3} />;
  if (players.isError) {
    return <Banner tone="error">Could not load section {section.name}: {errorMessage(players.error)}</Banner>;
  }
  const list = players.data;
  const rows = list.players ?? [];
  const active = rows.filter((p) => p.withdrawn_from_round === null).length;

  return (
    <Card>
      <CardHeader
        title={`Section ${section.name}`}
        aside={
          rows.length === 0
            ? "nobody entered yet"
            : `${plural(active, "player")}${rows.length > active ? `, ${rows.length - active} withdrawn` : ""}${
                list.seeded ? " · seeded" : ""
              }`
        }
      >
        {list.editable && <AddPlayerForm list={list} tournamentId={tournamentId} />}
      </CardHeader>
      {!list.editable && (
        <p className="border-b border-line px-4 py-2 text-body-sm text-ink-2 sm:px-5">
          Read-only: this list comes from {section.manager_label}.
        </p>
      )}
      {rows.length === 0 ? (
        <div className="p-4">
          <EmptyState title="No players yet">
            {list.editable ? "Add the first player above." : "The next import fills this in."}
          </EmptyState>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line bg-subtle/90 text-left text-label-sm text-ink-2">
                <th className="w-10 px-3 py-2 text-right sm:px-4">No.</th>
                <th className="px-2 py-2">Name</th>
                <th className="hidden px-2 py-2 sm:table-cell">Fed</th>
                <th className="px-2 py-2 text-right">Rating</th>
                <th className="hidden px-2 py-2 md:table-cell">FIDE id</th>
                <th className="px-2 py-2">Status</th>
                {list.editable && <th className="px-2 py-2 text-right">Actions</th>}
              </tr>
            </thead>
            <tbody>
              {rows.map((player) => {
                const out = player.withdrawn_from_round !== null;
                return (
                  <tr key={player.id} className={cx("border-b border-line", out && "text-ink-3")}>
                    <td className="px-3 py-1.5 text-right font-mono font-semibold text-ink-2 sm:px-4">
                      {player.start_rank}
                    </td>
                    <td className="px-2 py-1.5">
                      {player.title && (
                        <span className="mr-1.5 rounded-sm bg-subtle px-1 font-mono text-[11px] font-semibold text-ink-2">
                          {player.title}
                        </span>
                      )}
                      {player.name}
                    </td>
                    <td className="hidden px-2 py-1.5 sm:table-cell">{player.federation}</td>
                    <td className="px-2 py-1.5 text-right font-mono">{player.rating ?? "—"}</td>
                    <td className="hidden px-2 py-1.5 font-mono text-xs md:table-cell">{player.fide_id}</td>
                    <td className="px-2 py-1.5">
                      {out ? (
                        <Chip tone="rose">withdrawn from round {player.withdrawn_from_round}</Chip>
                      ) : (
                        <Chip tone="emerald">in</Chip>
                      )}
                    </td>
                    {list.editable && (
                      <td className="px-2 py-1.5 text-right whitespace-nowrap">
                        <Button size="sm" tone="ghost" onClick={() => setEditing(player)}>
                          Edit
                        </Button>
                        {out ? (
                          <Button
                            size="sm"
                            tone="ghost"
                            busy={reinstate.isPending && reinstate.variables?.playerId === player.id}
                            onClick={() =>
                              reinstate.mutate(
                                { playerId: player.id, sectionId: section.id, tournamentId },
                                {
                                  onSuccess: () => toast.success(`${player.name} is back in.`),
                                  onError: (error) => toast.error(errorMessage(error)),
                                },
                              )
                            }
                          >
                            Reinstate
                          </Button>
                        ) : (
                          <Button size="sm" tone="ghost" onClick={() => setLeaving(player)}>
                            Withdraw…
                          </Button>
                        )}
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {editing && (
        <EditPlayerDialog
          player={editing}
          sectionId={section.id}
          tournamentId={tournamentId}
          onClose={() => setEditing(null)}
        />
      )}
      {leaving && (
        <WithdrawDialog
          player={leaving}
          list={list}
          sectionId={section.id}
          tournamentId={tournamentId}
          onClose={() => setLeaving(null)}
        />
      )}
    </Card>
  );
}

const EMPTY: PlayerBody = { name: "", title: "", rating: null, federation: "", fide_id: "", sex: "", birth_date: "" };

function AddPlayerForm({ list, tournamentId }: { list: PlayerList; tournamentId: string }) {
  const [open, setOpen] = useState(false);
  const [body, setBody] = useState<PlayerBody>(EMPTY);
  const add = useAddPlayer();
  const toast = useToast();
  const close = () => {
    add.reset();
    setBody(EMPTY);
    setOpen(false);
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!body.name?.trim() || add.isPending) return;
    add.mutate(
      { sectionId: list.section_id, tournamentId, ...body },
      {
        onSuccess: (player) => {
          toast.success(
            `${player.name} entered as number ${player.start_rank}${list.seeded ? " (late entry)" : ""}.`,
          );
          setBody(EMPTY);
        },
      },
    );
  };

  return (
    <>
      <Button tone="primary" size="sm" onClick={() => setOpen(true)}>
        Add player…
      </Button>
      <Dialog
        open={open}
        onClose={close}
        title={`Add a player to section ${list.section_name}`}
        subtitle={list.seeded ? "Round 1 is paired: this is a late entry and takes the next number." : undefined}
        busy={add.isPending}
        footer={
          <>
            <Button onClick={close} disabled={add.isPending}>
              Done
            </Button>
            <Button tone="primary" form="add-player" type="submit" busy={add.isPending} disabled={!body.name?.trim()}>
              Add
            </Button>
          </>
        }
      >
        <form id="add-player" onSubmit={submit}>
          <PlayerFields body={body} onChange={setBody} autoFocus />
          {add.isError && (
            <Banner tone="error" className="mt-3">
              {errorMessage(add.error)}
            </Banner>
          )}
        </form>
      </Dialog>
    </>
  );
}

function EditPlayerDialog({
  player,
  sectionId,
  tournamentId,
  onClose,
}: {
  player: PlayerDetail;
  sectionId: string;
  tournamentId: string;
  onClose: () => void;
}) {
  const [body, setBody] = useState<PlayerBody>({
    name: player.name,
    title: player.title,
    rating: player.rating,
    federation: player.federation,
    fide_id: player.fide_id,
    sex: player.sex,
    birth_date: player.birth_date,
  });
  const update = useUpdatePlayer();
  const toast = useToast();

  const submit = (event: FormEvent) => {
    event.preventDefault();
    update.mutate(
      { playerId: player.id, sectionId, tournamentId, ...body },
      {
        onSuccess: () => {
          toast.success(`${body.name} updated.`);
          onClose();
        },
      },
    );
  };

  return (
    <Dialog
      open
      onClose={onClose}
      title={`Edit ${player.name}`}
      subtitle={`Number ${player.start_rank}`}
      busy={update.isPending}
      footer={
        <>
          <Button onClick={onClose} disabled={update.isPending}>
            Cancel
          </Button>
          <Button tone="primary" form="edit-player" type="submit" busy={update.isPending}>
            Save
          </Button>
        </>
      }
    >
      <form id="edit-player" onSubmit={submit}>
        <PlayerFields body={body} onChange={setBody} />
        {update.isError && (
          <Banner tone="error" className="mt-3">
            {errorMessage(update.error)}
          </Banner>
        )}
      </form>
    </Dialog>
  );
}

function PlayerFields({
  body,
  onChange,
  autoFocus,
}: {
  body: PlayerBody;
  onChange: (body: PlayerBody) => void;
  autoFocus?: boolean;
}) {
  const set = (patch: Partial<PlayerBody>) => onChange({ ...body, ...patch });
  return (
    <div className="flex flex-col gap-3">
      <Field label="Name" hint="Last name, first name — as it should read on the board.">
        <Input value={body.name} onChange={(e) => set({ name: e.target.value })} autoFocus={autoFocus} required />
      </Field>
      <div className="grid grid-cols-3 gap-3">
        <Field label="Rating">
          <Input
            type="number"
            min={0}
            max={4000}
            value={body.rating ?? ""}
            onChange={(e) => set({ rating: e.target.value === "" ? null : Number(e.target.value) })}
          />
        </Field>
        <Field label="Title">
          <Input value={body.title ?? ""} onChange={(e) => set({ title: e.target.value })} placeholder="FM" maxLength={8} />
        </Field>
        <Field label="Federation">
          <Input value={body.federation ?? ""} onChange={(e) => set({ federation: e.target.value })} placeholder="SUI" maxLength={8} />
        </Field>
      </div>
      <div className="grid grid-cols-3 gap-3">
        <Field label="FIDE id">
          <Input value={body.fide_id ?? ""} onChange={(e) => set({ fide_id: e.target.value })} maxLength={16} />
        </Field>
        <Field label="Sex">
          <Select value={body.sex ?? ""} onChange={(e) => set({ sex: e.target.value })}>
            <option value="">—</option>
            <option value="m">m</option>
            <option value="w">w</option>
          </Select>
        </Field>
        <Field label="Born" hint="YYYY/MM/DD">
          <Input value={body.birth_date ?? ""} onChange={(e) => set({ birth_date: e.target.value })} placeholder="1990/04/02" maxLength={10} />
        </Field>
      </div>
    </div>
  );
}

function WithdrawDialog({
  player,
  list,
  sectionId,
  tournamentId,
  onClose,
}: {
  player: PlayerDetail;
  list: PlayerList;
  sectionId: string;
  tournamentId: string;
  onClose: () => void;
}) {
  const withdraw = useWithdrawPlayer();
  const toast = useToast();
  const nextRound = list.rounds_held + 1;
  return (
    <ConfirmDialog
      open
      onClose={onClose}
      tone="danger"
      title={`Withdraw ${player.name}?`}
      confirmLabel={`Withdraw from round ${nextRound}`}
      busy={withdraw.isPending}
      onConfirm={() =>
        withdraw.mutate(
          { playerId: player.id, sectionId, tournamentId, fromRound: null },
          {
            onSuccess: () => {
              toast.success(`${player.name} withdrawn from round ${nextRound}.`);
              onClose();
            },
            onError: (error) => toast.error(errorMessage(error)),
          },
        )
      }
    >
      <p>
        They are left out of every pairing from round {nextRound} on, and the rounds they miss count
        as absences in the table. A board already paired is settled with a result, not by this.
        They can be reinstated as long as their next round is not paired yet.
      </p>
    </ConfirmDialog>
  );
}
