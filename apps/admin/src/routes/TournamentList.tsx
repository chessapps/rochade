import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router";

import { errorMessage, type ManagerSummary, type TournamentSummary } from "../api";
import { Dialog } from "../components/Dialog";
import { Chip } from "../components/StateChip";
import { useToast } from "../components/Toast";
import { BookOpen, Calendar, Check, MapPin } from "../components/icons";
import { Banner, Button, EmptyState, Field, Input, Skeleton, cx } from "../components/ui";
import { dateRange } from "../format";
import { useCreateTournament, useManagers, useTournaments } from "../queries";

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
        <div className="flex flex-wrap items-center gap-2">
          <Button to="/guides/vega" icon={<BookOpen />}>
            How to run a round with Vega
          </Button>
          <Button tone="primary" onClick={() => setCreating(true)}>
            New tournament
          </Button>
        </div>
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
          manager one round at a time. New to the loop?{" "}
          <Link to="/guides/vega" className="font-medium text-accent hover:underline">
            Read how a round runs with Vega
          </Link>
          .
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
      <p className="mt-auto flex items-center justify-between gap-2 text-label-sm text-ink-3">
        <span>you are {tournament.role}</span>
        <span>{tournament.manager_label}</span>
      </p>
    </Link>
  );
}

/**
 * The programs a tournament can run on, in the order they are offered. What
 * the API lists is what can be chosen; the rest is announced and disabled.
 */
interface ProgramOption {
  key: string;
  label: string;
  blurb: string;
  available: boolean;
}

const BLURB: Record<string, string> = {
  swiss_manager: "Two text exports per round: Spielerdaten and Spielerauslosung.",
  vega: "Two files from the tournament folder per round: engine26.trf and SortedPairs.txt; the results go back as a TRF it imports.",
  gacrux:
    "Rochade pairs the rounds itself: Dutch system and FIDE tie-breaks by the Gacrux engine. No files.",
};

function programOptions(managers: ManagerSummary[] | undefined): ProgramOption[] {
  const known = new Map((managers ?? []).map((m) => [m.key, m]));
  return ["swiss_manager", "vega", "gacrux"]
    .filter((key) => known.has(key))
    .map((key) => {
      const m = known.get(key)!;
      return {
        key,
        label: m.label,
        blurb: BLURB[key] + (m.verified ? " Verified against the real program." : " Not yet verified."),
        available: true,
      };
    });
}

function CreateTournamentDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const toast = useToast();
  const managers = useManagers();
  const create = useCreateTournament({
    onSuccess: (data) => {
      toast.success(`${data.name} created.`);
      onClose();
      void navigate(`/t/${data.id}`);
    },
  });
  const [manager, setManager] = useState("");
  const [step, setStep] = useState<"program" | "details">("program");
  const [name, setName] = useState("");
  const [city, setCity] = useState("");
  const [federation, setFederation] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");

  const options = programOptions(managers.data);
  const chosen = options.find((o) => o.key === manager);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!name.trim() || !manager || create.isPending) return;
    create.mutate({
      name: name.trim(),
      manager,
      city: city.trim(),
      federation: federation.trim().toUpperCase(),
      start_date: start || null,
      end_date: end || start || null,
    });
  };

  const close = () => {
    onClose();
    setStep("program");
  };

  return (
    <Dialog
      open={open}
      onClose={close}
      title="New tournament"
      subtitle={
        step === "program"
          ? "Which program pairs it? Every round is imported from and exported to that one."
          : undefined
      }
      footer={
        step === "program" ? (
          <>
            <Button onClick={close}>Cancel</Button>
            <Button tone="primary" onClick={() => setStep("details")} disabled={!chosen?.available}>
              Continue
            </Button>
          </>
        ) : (
          <>
            <Button onClick={() => setStep("program")} disabled={create.isPending}>
              Back
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
        )
      }
    >
      {step === "program" ? (
        <fieldset className="flex flex-col gap-2">
          <legend className="sr-only">Pairing program</legend>
          {managers.isPending && <Skeleton rows={2} className="p-0" />}
          {managers.isError && (
            <Banner tone="error">Could not list the programs: {errorMessage(managers.error)}</Banner>
          )}
          {options.map((option) => (
            <ProgramChoice
              key={option.key}
              option={option}
              checked={manager === option.key}
              onChoose={() => setManager(option.key)}
            />
          ))}
        </fieldset>
      ) : (
        <form id="create-tournament" onSubmit={submit} className="flex flex-col gap-3">
          <p className="flex items-center gap-2 text-body-sm text-ink-2">
            Runs on <Chip tone="emerald">{chosen?.label}</Chip>
          </p>
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
            {chosen?.key === "gacrux"
              ? "Next: open a section, enter the players, and pair round 1 from the desk."
              : `Only the name matters here. Players, pairings and rounds come from ${chosen?.label}, one export per round.`}
          </p>
          {create.isError && <Banner tone="error">{errorMessage(create.error)}</Banner>}
        </form>
      )}
    </Dialog>
  );
}

function ProgramChoice({
  option,
  checked,
  onChoose,
}: {
  option: ProgramOption;
  checked: boolean;
  onChoose: () => void;
}) {
  return (
    <label
      className={cx(
        "flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors",
        checked ? "border-accent bg-accent-soft/40" : "border-line hover:border-line-strong",
        !option.available && "cursor-not-allowed opacity-60",
      )}
    >
      <input
        type="radio"
        name="program"
        value={option.key}
        checked={checked}
        disabled={!option.available}
        onChange={onChoose}
        className="sr-only"
      />
      <span
        aria-hidden
        className={cx(
          "mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full border [&>svg]:size-3",
          checked ? "border-accent bg-accent text-white" : "border-line-strong bg-card",
        )}
      >
        {checked && <Check />}
      </span>
      <span className="flex min-w-0 flex-col gap-0.5">
        <span className="flex items-center gap-2 font-semibold text-ink">
          {option.label}
          {!option.available && <Chip tone="neutral">Coming soon</Chip>}
        </span>
        <span className="text-body-sm text-ink-2">{option.blurb}</span>
      </span>
    </label>
  );
}
