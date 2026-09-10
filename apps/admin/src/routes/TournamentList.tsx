import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router";

import { errorMessage, type TournamentSummary } from "../api";
import { Dialog } from "../components/Dialog";
import { useToast } from "../components/Toast";
import { Calendar, MapPin } from "../components/icons";
import { Banner, Button, EmptyState, Field, Input, Skeleton } from "../components/ui";
import { dateRange } from "../format";
import { useCreateTournament, useTournaments } from "../queries";

export function TournamentList() {
  const tournaments = useTournaments();
  const [creating, setCreating] = useState(false);
  // "Rochade" in the header links here with ?all, which is how an arbiter with
  // one tournament reaches the list to start another.
  const [params] = useSearchParams();
  const asked = params.has("all");

  if (tournaments.isPending) return <Skeleton rows={3} />;
  if (tournaments.isError) {
    return <Banner tone="error">Could not load tournaments: {errorMessage(tournaments.error)}</Banner>;
  }

  const list = tournaments.data;
  // One tournament is the usual day. Go straight to it; the list is a click away.
  if (list.length === 1 && !creating && !asked) {
    return <Navigate to={`/t/${list[0]!.id}`} replace />;
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-headline-md">Tournaments</h1>
        <Button tone="primary" onClick={() => setCreating(true)}>
          New tournament
        </Button>
      </div>

      {list.length === 0 ? (
        <EmptyState
          title="No tournaments yet"
          action={
            <Button tone="primary" onClick={() => setCreating(true)}>
              Create the first one
            </Button>
          }
        >
          A tournament here holds one or more sections, each imported from your tournament
          manager one round at a time.
        </EmptyState>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {list.map((tournament) => (
            <li key={tournament.id}>
              <TournamentCard tournament={tournament} />
            </li>
          ))}
        </ul>
      )}

      <CreateTournamentDialog open={creating} onClose={() => setCreating(false)} />
    </div>
  );
}

function TournamentCard({ tournament }: { tournament: TournamentSummary }) {
  const when = dateRange(tournament.start_date, tournament.end_date);
  return (
    <Link
      to={`/t/${tournament.id}`}
      className="flex h-full flex-col gap-3 rounded-lg border border-line bg-card p-4 transition-colors hover:border-line-strong hover:bg-subtle/40"
    >
      <p className="text-headline-sm">{tournament.name}</p>
      <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-body-sm text-ink-2 [&_svg]:size-3.5 [&_svg]:text-ink-3">
        {tournament.city && (
          <span className="flex items-center gap-1">
            <MapPin />
            {tournament.city}
          </span>
        )}
        {when && (
          <span className="flex items-center gap-1">
            <Calendar />
            {when}
          </span>
        )}
        {!tournament.city && !when && <span>&nbsp;</span>}
      </p>
      <p className="mt-auto text-label-sm text-ink-3">you are {tournament.role}</p>
    </Link>
  );
}

function CreateTournamentDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const toast = useToast();
  const create = useCreateTournament({
    onSuccess: (data) => {
      toast.success(`${data.name} created.`);
      onClose();
      void navigate(`/t/${data.id}`);
    },
  });
  const [name, setName] = useState("");
  const [city, setCity] = useState("");
  const [federation, setFederation] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!name.trim() || create.isPending) return;
    create.mutate({
      name: name.trim(),
      city: city.trim(),
      federation: federation.trim().toUpperCase(),
      start_date: start || null,
      end_date: end || start || null,
    });
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="New tournament"
      footer={
        <>
          <Button onClick={onClose} disabled={create.isPending}>
            Cancel
          </Button>
          <Button
            tone="primary"
            form="create-tournament"
            type="submit"
            busy={create.isPending}
            disabled={!name.trim()}
          >
            Create
          </Button>
        </>
      }
    >
      <form id="create-tournament" onSubmit={submit} className="flex flex-col gap-3">
        <Field label="Name">
          <Input value={name} onChange={(e) => setName(e.target.value)} autoFocus required />
        </Field>
        <div className="grid grid-cols-[1fr_6rem] gap-3">
          <Field label="City">
            <Input value={city} onChange={(e) => setCity(e.target.value)} />
          </Field>
          <Field label="Federation">
            <Input
              value={federation}
              onChange={(e) => setFederation(e.target.value)}
              placeholder="SUI"
              maxLength={8}
            />
          </Field>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="First day">
            <Input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
          </Field>
          <Field label="Last day">
            <Input type="date" value={end} min={start} onChange={(e) => setEnd(e.target.value)} />
          </Field>
        </div>
        <p className="text-body-sm text-ink-2">
          Only the name matters here. Players, pairings and rounds come from your tournament
          manager, one export per round.
        </p>
        {create.isError && <Banner tone="error">{errorMessage(create.error)}</Banner>}
      </form>
    </Dialog>
  );
}
