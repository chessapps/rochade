/**
 * Open a section in a tournament Rochade pairs itself: how many rounds,
 * which tie-breaks decide the table, who has white on board one.
 */

import { useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router";

import { errorMessage } from "../api";
import { PageHeader } from "../components/PageHeader";
import { useToast } from "../components/Toast";
import { Banner, Button, Card, Field, Input, Select, cx } from "../components/ui";
import { useCreateSection, useTournament } from "../queries";
import { DEFAULT_TIEBREAKS, MAX_TIEBREAKS, TIEBREAKS, tiebreakLabel } from "../tiebreaks";

export function NewSection() {
  const { tournamentId = "" } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const tournament = useTournament(tournamentId);
  const create = useCreateSection();

  const [name, setName] = useState("");
  const [rounds, setRounds] = useState("5");
  const [tiebreaks, setTiebreaks] = useState<string[]>([...DEFAULT_TIEBREAKS]);
  const [colour, setColour] = useState<"" | "white" | "black">("");
  const [adding, setAdding] = useState("");

  const roundsNumber = Number(rounds);
  const ready = name.trim() !== "" && Number.isInteger(roundsNumber) && roundsNumber >= 1 && roundsNumber <= 30;
  const available = TIEBREAKS.filter((t) => !tiebreaks.includes(t.code));

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!ready || create.isPending) return;
    create.mutate(
      {
        tournamentId,
        name: name.trim(),
        declared_rounds: roundsNumber,
        tiebreaks,
        top_board_colour: colour || null,
      },
      {
        onSuccess: (data) => {
          toast.success(
            `Section ${data.name} opened${data.drawn_by_lot ? `: ${data.top_board_colour} on board one, drawn by lot` : ""}.`,
          );
          void navigate(`/t/${tournamentId}/players?section=${encodeURIComponent(data.section_id)}`);
        },
      },
    );
  };

  const move = (index: number, by: number) => {
    const next = [...tiebreaks];
    const target = index + by;
    if (target < 1 || target >= next.length) return;
    [next[index], next[target]] = [next[target]!, next[index]!];
    setTiebreaks(next);
  };

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        back={{ to: `/t/${tournamentId}`, label: tournament.data?.name ?? "Tournament" }}
        title="New section"
        lead="A section is one field paired on its own: an Open, a U12, a B group. Rochade pairs it with the Dutch system and ranks it with the tie-breaks you choose."
      />
      <Card as="div" className="p-4 sm:p-6">
        <form onSubmit={submit} className="flex max-w-xl flex-col gap-4">
          <Field label="Name" hint="Short: it goes on every board number and in the hall app.">
            <Input value={name} onChange={(e) => setName(e.target.value)} autoFocus required maxLength={120} />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Rounds">
              <Input type="number" min={1} max={30} value={rounds} onChange={(e) => setRounds(e.target.value)} required />
            </Field>
            <Field label="White on board 1, round 1">
              <Select value={colour} onChange={(e) => setColour(e.target.value as "" | "white" | "black")}>
                <option value="">Draw lots</option>
                <option value="white">The higher-ranked player</option>
                <option value="black">The lower-ranked player</option>
              </Select>
            </Field>
          </div>

          <fieldset className="flex flex-col gap-2">
            <legend className="text-sm font-medium text-ink-2">Tie-breaks, in order</legend>
            <ol className="flex flex-col gap-1.5" aria-label="tie-break order">
              {tiebreaks.map((code, index) => (
                <li
                  key={code}
                  className={cx(
                    "flex items-center gap-2 rounded border border-line px-3 py-1.5 text-sm",
                    index === 0 && "bg-subtle text-ink-2",
                  )}
                >
                  <span className="w-5 font-mono text-xs text-ink-3">{index + 1}.</span>
                  <span className="flex-1">
                    {tiebreakLabel(code)} <span className="font-mono text-xs text-ink-3">{code}</span>
                  </span>
                  {index > 0 && (
                    <>
                      <Button size="sm" tone="ghost" onClick={() => move(index, -1)} disabled={index === 1} aria-label={`move ${code} up`}>
                        ↑
                      </Button>
                      <Button size="sm" tone="ghost" onClick={() => move(index, 1)} disabled={index === tiebreaks.length - 1} aria-label={`move ${code} down`}>
                        ↓
                      </Button>
                      <Button size="sm" tone="ghost" onClick={() => setTiebreaks(tiebreaks.filter((t) => t !== code))} aria-label={`remove ${code}`}>
                        ×
                      </Button>
                    </>
                  )}
                </li>
              ))}
            </ol>
            {tiebreaks.length < MAX_TIEBREAKS && (
              <div className="flex items-center gap-2">
                <Select value={adding} onChange={(e) => setAdding(e.target.value)} aria-label="add a tie-break" className="min-h-9 py-0 text-sm">
                  <option value="">Add a tie-break…</option>
                  {available.map((t) => (
                    <option key={t.code} value={t.code}>
                      {t.label} ({t.code})
                    </option>
                  ))}
                </Select>
                <Button
                  size="sm"
                  onClick={() => {
                    if (!adding) return;
                    setTiebreaks([...tiebreaks, adding]);
                    setAdding("");
                  }}
                  disabled={!adding}
                >
                  Add
                </Button>
              </div>
            )}
            <p className="text-body-sm text-ink-3">
              Points come first and stay first. The default is FIDE's usual recommendation for an individual Swiss.
            </p>
          </fieldset>

          {create.isError && <Banner tone="error">{errorMessage(create.error)}</Banner>}
          <div className="flex justify-end gap-2">
            <Button to={`/t/${tournamentId}`}>Cancel</Button>
            <Button type="submit" tone="primary" busy={create.isPending} disabled={!ready}>
              Open the section
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
