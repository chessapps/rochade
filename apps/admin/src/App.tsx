import { useEffect, useState, type FormEvent } from "react";
import { Navigate, Outlet, Route, Routes, useLocation, useNavigate } from "react-router";

import { api, errorMessage, onUnauthorized } from "./api";
import {
  completeSignIn,
  forget,
  signInWithIssuer,
  signInWithToken,
  signOut,
  startSession,
  type Account,
  type AuthConfig,
  type Session,
} from "./auth";
import { Shell } from "./components/Shell";
import { Button, Input } from "./components/ui";
import { Devices } from "./routes/Devices";
import { ImportWizard } from "./routes/ImportWizard";
import { Poster } from "./routes/Poster";
import { RoundBoard } from "./routes/RoundBoard";
import { Standings } from "./routes/Standings";
import { TournamentHome } from "./routes/TournamentHome";
import { TournamentList } from "./routes/TournamentList";

type State =
  | { status: "loading" }
  | { status: "failed"; message: string }
  | { status: "ready"; session: Session; notice?: string };

async function fetchConfig(): Promise<AuthConfig> {
  const { data, error } = await api.GET("/api/auth/config");
  if (error || !data) throw new Error(errorMessage(error ?? "the API did not answer"));
  return data;
}

export function App() {
  const [state, setState] = useState<State>({ status: "loading" });
  const location = useLocation();

  useEffect(() => {
    let live = true;
    startSession(fetchConfig).then(
      (session) => live && setState({ status: "ready", session }),
      (error: unknown) => live && setState({ status: "failed", message: errorMessage(error) }),
    );
    return () => {
      live = false;
    };
  }, []);

  useEffect(() => {
    if (state.status !== "ready") return;
    const { session } = state;
    onUnauthorized(() => {
      if (!session.account) return;
      void forget(session).then(() =>
        setState({
          status: "ready",
          session: { ...session, account: null },
          notice: "Your session ended. Sign in again to continue.",
        }),
      );
    });
    return () => onUnauthorized(() => {});
  }, [state]);

  if (state.status === "loading") return <Splash>Loading…</Splash>;
  if (state.status === "failed") {
    return (
      <Splash>
        <p className="text-red-700">Could not reach the API: {state.message}</p>
        <Button tone="primary" onClick={() => window.location.reload()}>
          Try again
        </Button>
      </Splash>
    );
  }

  const { session } = state;
  const signedIn = (account: Account) =>
    setState({ status: "ready", session: { ...session, account } });

  if (location.pathname === "/callback" && session.manager) {
    return <Callback session={session} onSignedIn={signedIn} />;
  }

  if (!session.account) {
    return (
      <SignIn
        session={session}
        notice={state.notice}
        returnTo={`${location.pathname}${location.search}`}
        onSignedIn={signedIn}
      />
    );
  }

  const leave = () => {
    void signOut(session).then(() =>
      setState({ status: "ready", session: { ...session, account: null } }),
    );
  };

  return (
    <Routes>
      <Route path="/t/:tournamentId/devices/poster" element={<Poster />} />
      <Route
        element={
          <Shell account={session.account} onSignOut={leave}>
            <Outlet />
          </Shell>
        }
      >
        <Route index element={<TournamentList />} />
        <Route path="/t/:tournamentId" element={<TournamentHome />} />
        <Route path="/t/:tournamentId/import" element={<ImportWizard />} />
        <Route path="/t/:tournamentId/rounds/:roundId" element={<RoundBoard />} />
        <Route path="/t/:tournamentId/standings" element={<Standings />} />
        <Route path="/t/:tournamentId/devices" element={<Devices />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

function Splash({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto mt-24 flex max-w-sm flex-col gap-3 p-6 text-sm text-slate-500">
      {children}
    </div>
  );
}

/** The issuer sent the browser back here with a code; turn it into a session. */
function Callback({
  session,
  onSignedIn,
}: {
  session: Session;
  onSignedIn: (account: Account) => void;
}) {
  const navigate = useNavigate();
  const [problem, setProblem] = useState<string | null>(null);

  useEffect(() => {
    if (!session.manager) return;
    completeSignIn(session.manager).then(
      ({ account, returnTo }) => {
        onSignedIn(account);
        navigate(returnTo, { replace: true });
      },
      (error: unknown) => setProblem(errorMessage(error)),
    );
    // Runs once for the code in the URL; a second run would try to redeem it again.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (problem) {
    return (
      <Splash>
        <p className="text-red-700">Sign-in failed: {problem}</p>
        <Button tone="primary" onClick={() => navigate("/", { replace: true })}>
          Back to sign in
        </Button>
      </Splash>
    );
  }
  return <Splash>Signing you in…</Splash>;
}

function SignIn({
  session,
  notice,
  returnTo,
  onSignedIn,
}: {
  session: Session;
  notice?: string;
  returnTo: string;
  onSignedIn: (account: Account) => void;
}) {
  const { config, manager } = session;
  const [value, setValue] = useState("");
  const [starting, setStarting] = useState(false);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (value.trim()) onSignedIn(signInWithToken(value.trim()));
  };

  const withIssuer = () => {
    if (!manager) return;
    setStarting(true);
    void signInWithIssuer(manager, returnTo === "/callback" ? "/" : returnTo);
  };

  return (
    <form onSubmit={submit} className="mx-auto mt-24 flex max-w-sm flex-col gap-3 p-6">
      <h1 className="text-xl font-semibold">Rochade — arbiter</h1>
      {notice && <p className="text-sm text-amber-700">{notice}</p>}
      {manager && (
        <>
          <p className="text-sm text-slate-500">
            Sign in with your arbiter account. A passkey or your password, at the identity
            provider.
          </p>
          <Button type="button" tone="primary" onClick={withIssuer} disabled={starting}>
            {starting ? "Redirecting…" : "Sign in"}
          </Button>
        </>
      )}
      {config.dev_auth && (
        <>
          <p className="text-sm text-slate-500">
            {manager ? "Or, for development, a" : "Sign in with your"} staff token.
            {manager ? "" : " Passkeys arrive with the identity provider."}
          </p>
          <Input
            value={value}
            onChange={(event) => setValue(event.target.value)}
            placeholder="staff token"
            autoFocus={!manager}
            aria-label="staff token"
          />
          <Button type="submit" tone={manager ? "secondary" : "primary"} disabled={!value.trim()}>
            {manager ? "Use token" : "Sign in"}
          </Button>
        </>
      )}
      {!manager && !config.dev_auth && (
        <p className="text-sm text-red-700">
          Staff sign-in is not configured on this API. Set ROCHADE_OIDC_ISSUER, or
          ROCHADE_DEV_AUTH_ENABLED for development.
        </p>
      )}
    </form>
  );
}
