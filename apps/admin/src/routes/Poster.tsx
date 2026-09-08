/**
 * The QR code as something to tape to the wall: tournament name, one line of
 * instruction, the code. Printing hides everything else on the page.
 */

import { Link, useLocation, useParams } from "react-router";

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
        <p className="font-medium">There is no code to show.</p>
        <p className="text-sm text-slate-500">
          A code is shown once, when it is issued. Issue one and open the poster from there.
        </p>
        <Link to={`/t/${tournamentId}/devices`} className="text-sm underline">
          Back to phones
        </Link>
      </div>
    );
  }

  return (
    <div className="flex min-h-full flex-col items-center bg-white">
      <div className="no-print flex w-full max-w-3xl items-center gap-2 p-4">
        <Link to={`/t/${tournamentId}/devices`} className="text-sm text-slate-500 hover:underline">
          ← Phones
        </Link>
        <span className="flex-1" />
        <Button tone="primary" onClick={() => window.print()}>
          Print
        </Button>
      </div>
      <article className="flex flex-1 flex-col items-center justify-center gap-6 p-8 text-center">
        <h1 className="text-3xl font-bold sm:text-4xl">{tournament.data?.name ?? ""}</h1>
        <p className="text-xl text-slate-700 sm:text-2xl">Scan to enter your result</p>
        <QrCode value={state.qr_payload} size={360} />
        {state.label && <p className="text-base text-slate-500">{state.label}</p>}
        <p className="max-w-md text-sm text-slate-400">
          Find your board by name and tap the result. The arbiter checks every entry before
          it counts.
        </p>
      </article>
    </div>
  );
}
