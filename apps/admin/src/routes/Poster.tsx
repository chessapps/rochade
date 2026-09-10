/**
 * The QR code as something to tape to the wall: tournament name, one line of
 * instruction, the code. Printing hides everything else on the page.
 */

import { useLocation, useParams } from "react-router";

import { ArrowLeft, Printer } from "../components/icons";
import { QrCode } from "../components/QrCode";
import { Button } from "../components/ui";
import { useTournament } from "../queries";

interface PosterState {
  qr_payload: string;
  label: string;
}

export function Poster() {
  const { tournamentId = "" } = useParams();
  const tournament = useTournament(tournamentId);
  const state = useLocation().state as PosterState | null;

  if (!state?.qr_payload) {
    return (
      <div className="mx-auto flex max-w-md flex-col items-center gap-3 p-8 text-center">
        <p className="font-semibold">There is no code to show.</p>
        <p className="text-body-sm text-ink-2">
          A code is shown once, when it is issued. Issue one and open the poster from there.
        </p>
        <Button to={`/t/${tournamentId}/devices`} icon={<ArrowLeft />}>
          Back to phones
        </Button>
      </div>
    );
  }

  return (
    <div className="flex min-h-full flex-col items-center bg-white">
      <div className="no-print flex w-full max-w-3xl items-center gap-2 p-4">
        <Button to={`/t/${tournamentId}/devices`} tone="ghost" size="sm" icon={<ArrowLeft />}>
          Phones
        </Button>
        <span className="flex-1" />
        <Button tone="dark" icon={<Printer />} onClick={() => window.print()}>
          Print
        </Button>
      </div>
      <article className="flex flex-1 flex-col items-center justify-center gap-6 p-8 text-center">
        <h1 className="text-headline-lg sm:text-[2.5rem] sm:leading-tight">{tournament.data?.name ?? ""}</h1>
        <p className="text-body-lg text-ink-2 sm:text-2xl">Scan to enter your result</p>
        <QrCode value={state.qr_payload} size={360} />
        {state.label && <p className="text-label-md text-ink-2">{state.label}</p>}
        <p className="max-w-md text-body-sm text-ink-3">
          Find your board by name and tap the result. The arbiter checks every entry before
          it counts.
        </p>
      </article>
    </div>
  );
}
