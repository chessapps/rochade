import { Navigate, Outlet, Route, Routes } from "react-router";

import { Shell } from "./components/Shell";
import { Player } from "./routes/Player";
import { Tournament } from "./routes/Tournament";
import { TournamentList } from "./routes/TournamentList";

export function App() {
  return (
    <Routes>
      <Route
        element={
          <Shell>
            <Outlet />
          </Shell>
        }
      >
        <Route index element={<TournamentList />} />
        <Route path="/:slug" element={<Tournament />} />
        <Route path="/:slug/s/:sectionId/p/:startRank" element={<Player />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
