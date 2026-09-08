import { useState, type FormEvent } from "react";
import { Navigate, Outlet, Route, Routes } from "react-router";

import { signIn, signOut, staffToken } from "./api";
import { Shell } from "./components/Shell";
import { Button, Input } from "./components/ui";
import { Devices } from "./routes/Devices";
import { ImportWizard } from "./routes/ImportWizard";
import { Poster } from "./routes/Poster";
import { RoundBoard } from "./routes/RoundBoard";
import { Standings } from "./routes/Standings";
import { TournamentHome } from "./routes/TournamentHome";
import { TournamentList } from "./routes/TournamentList";

export function App() {
  const [token, setToken] = useState(staffToken());

  if (!token) {
    return (
      <SignIn
        onSignIn={(value) => {
          signIn(value);
          setToken(value);
        }}
      />
    );
  }

  const leave = () => {
    signOut();
    setToken(null);
  };

  return (
    <Routes>
      <Route path="/t/:tournamentId/devices/poster" element={<Poster />} />
      <Route
        element={
          <Shell onSignOut={leave}>
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

function SignIn({ onSignIn }: { onSignIn: (token: string) => void }) {
  const [value, setValue] = useState("");
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (value.trim()) onSignIn(value.trim());
  };
  return (
    <form onSubmit={submit} className="mx-auto mt-24 flex max-w-sm flex-col gap-3 p-6">
      <h1 className="text-xl font-semibold">Seebach — arbiter</h1>
      <p className="text-sm text-slate-500">
        Sign in with your staff token. Passkeys arrive with the identity provider.
      </p>
      <Input
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder="staff token"
        autoFocus
        aria-label="staff token"
      />
      <Button type="submit" tone="primary" disabled={!value.trim()}>
        Sign in
      </Button>
    </form>
  );
}
