/**
 * The code a phone can type when scanning is not an option.
 *
 * The QR remains the way in for a hall full of players. This is for the phone
 * that cannot reach the camera link: a tester on another network, a helper
 * whose camera app will not focus, a player reading it off the arbiter's
 * screen. It grants exactly what the QR grants, so it is off until asked for
 * and one click to close.
 */

import { useState } from "react";

import { errorMessage } from "../api";
import { useSetJoinCode } from "../queries";
import { useToast } from "./Toast";
import { Banner, Button, Card, CardHeader } from "./ui";

export function JoinCode({
  tournamentId,
  code,
}: {
  tournamentId: string;
  code: string | null | undefined;
}) {
  const setCode = useSetJoinCode();
  const toast = useToast();
  const [copied, setCopied] = useState(false);

  const run = (enabled: boolean) => {
    setCode.mutate(
      { tournamentId, enabled },
      {
        onError: (error) => toast.error(errorMessage(error)),
        onSuccess: () => setCopied(false),
      },
    );
  };

  const copy = () => {
    if (!code) return;
    void navigator.clipboard?.writeText(code).then(
      () => {
        setCopied(true);
        toast.success("Code copied.");
      },
      () => toast.error("Could not copy the code."),
    );
  };

  return (
    <Card>
      <CardHeader
        title="Join code"
        aside={code ? "anyone with it can enter results" : undefined}
      />
      <div className="flex flex-col gap-3 p-4 sm:p-5">
        {code ? (
          <>
            <div className="flex flex-wrap items-center gap-3">
              <p
                className="rounded-xl bg-slate-900 px-5 py-3 font-mono text-3xl tracking-[0.35em] text-white"
                aria-label={`Join code ${code.split("").join(" ")}`}
              >
                {code}
              </p>
              <div className="flex flex-wrap gap-2">
                <Button onClick={copy}>{copied ? "Copied" : "Copy"}</Button>
                <Button onClick={() => run(true)} busy={setCode.isPending}>
                  New code
                </Button>
                <Button tone="danger" onClick={() => run(false)} disabled={setCode.isPending}>
                  Turn off
                </Button>
              </div>
            </div>
            <p className="text-sm text-slate-500">
              Players type this on the hall app's opening screen instead of scanning. Each
              phone that uses it gets its own entry in the list below, so one can be revoked
              without disturbing the rest. Turn it off when the round is under way.
            </p>
          </>
        ) : (
          <>
            <div>
              <Button tone="primary" onClick={() => run(true)} busy={setCode.isPending}>
                Open joining with a code
              </Button>
            </div>
            <p className="text-sm text-slate-500">
              Six characters a player can type instead of scanning — useful when the camera
              will not focus, or when testing from a phone that cannot reach the QR link.
            </p>
          </>
        )}
        {setCode.isError && <Banner tone="error">{errorMessage(setCode.error)}</Banner>}
      </div>
    </Card>
  );
}
