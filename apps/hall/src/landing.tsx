/**
 * The front door of the site, shown to any browser that holds no device
 * credential: a phone that arrived without scanning, an arbiter looking for
 * the admin area, anyone who typed the domain.
 *
 * Two ways in, one for each kind of visitor. A player scans the QR code the
 * arbiter put up, or types the tournament's join code when the API says that
 * is allowed here; the field is not shown otherwise, so nobody stares at a
 * box nothing can be typed into. An arbiter follows the link to the admin
 * area and signs in there.
 */

import { useEffect, useState, type FormEvent } from "react";

import { fetchAuthConfig, joinWithCode } from "./api";
import { adoptCredential } from "./storage";

export const SITE_NAME = "Rochade";

export function Landing({ onJoined }: { onJoined: () => void }) {
  // Unknown until the API answers; the code field only appears once it says
  // yes. Should the API be unreachable the field is offered anyway: the
  // server refuses the code with a message, which beats hiding the door.
  const [codeAllowed, setCodeAllowed] = useState<boolean | null>(null);

  useEffect(() => {
    let live = true;
    fetchAuthConfig().then(
      (config) => live && setCodeAllowed(config.device_join),
      () => live && setCodeAllowed(true),
    );
    return () => {
      live = false;
    };
  }, []);

  return (
    <div className="mx-auto flex min-h-full w-full max-w-xl flex-col gap-8 overflow-y-auto p-5 sm:py-10">
      <header>
        <p className="text-xs font-semibold tracking-wide text-mute uppercase">{SITE_NAME}</p>
        <h1 className="mt-1 text-3xl font-bold leading-tight">
          Chess results, from the board to the arbiter.
        </h1>
        <p className="mt-3 text-base text-mute">
          Players enter each result on their own phone. The arbiter sees every board as it
          comes in, settles what two phones disagree about, and hands the round back to
          Swiss-Manager or Vega for the next pairing.
        </p>
      </header>

      <section aria-labelledby="players" className="rounded-md border-2 border-ink p-4 sm:p-5">
        <h2 id="players" className="text-xl font-bold">
          Playing today?
        </h2>
        <p className="mt-1 text-base text-mute">
          Scan the QR code the arbiter put up. It opens your tournament's board list on this
          phone, nothing to install and nothing to sign in to.
        </p>
        {codeAllowed === true && <JoinForm onJoined={onJoined} />}
        {codeAllowed === false && (
          <p className="mt-3 text-sm text-mute">
            There is no code to type here: the QR code is the way in.
          </p>
        )}
      </section>

      <section aria-labelledby="arbiters" className="rounded-md border-2 border-ink p-4 sm:p-5">
        <h2 id="arbiters" className="text-xl font-bold">
          Running a tournament?
        </h2>
        <p className="mt-1 text-base text-mute">
          The arbiter area is where a tournament is set up, each round's pairings are imported,
          the QR code is issued and the results are released and exported. Signing in takes a
          passkey or the password of your arbiter account.
        </p>
        <a
          href="/admin/"
          className="mt-4 block w-full rounded-md bg-ink py-3 text-center text-lg font-bold text-paper active:bg-neutral-800"
        >
          Open the arbiter area
        </a>
      </section>
    </div>
  );
}

function JoinForm({ onJoined }: { onJoined: () => void }) {
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const join = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const joined = await joinWithCode(code.trim());
      adoptCredential(joined.token, joined.tournament_id);
      onJoined();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The code could not be used.");
      setBusy(false);
    }
  };

  return (
    <form onSubmit={join} className="mt-4 flex flex-col gap-2">
      <label htmlFor="join-code" className="text-sm font-semibold">
        Or type the code the arbiter reads out
      </label>
      <input
        id="join-code"
        value={code}
        onChange={(event) => setCode(event.target.value.toUpperCase())}
        autoCapitalize="characters"
        autoCorrect="off"
        spellCheck={false}
        inputMode="text"
        placeholder="ABC123"
        className="w-full rounded-md border-2 border-ink bg-paper px-4 py-3 text-center font-mono text-3xl tracking-[0.3em] uppercase placeholder:text-neutral-300 focus:outline-none focus:ring-2 focus:ring-ink focus:ring-offset-1"
      />
      <button
        type="submit"
        disabled={busy || code.trim().length < 4}
        className="w-full rounded-md bg-ink py-4 text-xl font-bold text-paper active:bg-neutral-800 disabled:opacity-40"
      >
        {busy ? "Joining…" : "Join"}
      </button>
      {error && (
        <p role="alert" className="text-sm font-semibold">
          {error}
        </p>
      )}
    </form>
  );
}
