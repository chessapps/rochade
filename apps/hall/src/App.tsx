import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  fetchBoards,
  fetchStandings,
  submitClaim,
  type Board,
  type BoardList,
  type Standings,
} from "./api";
import { Landing } from "./landing";
import { ClaimQueue, type GameResult, type PendingClaim } from "./queue";
import {
  BoardListScreen,
  DoneScreen,
  RejectedBanner,
  ResultChoiceScreen,
  StandingsScreen,
  ViewTabs,
  type View,
} from "./screens";
import {
  cacheBoards,
  cachedBoards,
  deviceToken,
  queueStorage,
  tournamentId,
} from "./storage";

type Screen =
  | { name: "list" }
  | { name: "choose"; board: Board; correcting?: boolean }
  | { name: "done"; board: Board; result: GameResult; queued: boolean; corrected: boolean };

const REFRESH_MS = 20_000;

export function App() {
  const queue = useMemo(() => new ClaimQueue(queueStorage, submitClaim), []);
  const [screen, setScreen] = useState<Screen>({ name: "list" });
  const [boards, setBoards] = useState<BoardList | null>(null);
  const [standings, setStandings] = useState<Standings | null>(null);
  const [view, setView] = useState<View>("boards");
  const [query, setQuery] = useState("");
  const [offline, setOffline] = useState(!navigator.onLine);
  const [pending, setPending] = useState<PendingClaim[]>([]);
  const [rejected, setRejected] = useState<PendingClaim[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Read once and then held: joining with a code flips this without a reload,
  // which on a phone would throw away the queue's in-flight work.
  const [admitted, setAdmitted] = useState(() => Boolean(deviceToken() && tournamentId()));
  const mounted = useRef(true);

  const syncQueueState = useCallback(() => {
    setPending(queue.pending());
    setRejected(queue.rejected());
  }, [queue]);

  const refresh = useCallback(async () => {
    const tournament = tournamentId();
    if (!tournament) return;
    try {
      const listing = await fetchBoards(tournament);
      if (!mounted.current) return;
      setBoards(listing);
      setOffline(false);
      setError(null);
      await cacheBoards(listing);
    } catch {
      if (mounted.current) setOffline(true);
      return;
    }
    // The table is a nicety; a failure here must not mark the phone offline.
    try {
      const table = await fetchStandings(tournament);
      if (mounted.current) setStandings(table);
    } catch {
      /* keep whatever we had */
    }
  }, []);

  const flush = useCallback(async () => {
    const report = await queue.flush();
    syncQueueState();
    // Only re-read the board list when something actually landed; a phone with
    // nothing to send should not add load to a venue network already in trouble.
    if (report.accepted > 0) await refresh();
  }, [queue, refresh, syncQueueState]);

  useEffect(() => {
    if (!admitted) return;
    mounted.current = true;
    const unsubscribe = queue.subscribe(syncQueueState);

    void (async () => {
      await queue.load();
      syncQueueState();
      const cached = await cachedBoards();
      if (cached && mounted.current) setBoards(cached);
      await refresh();
      await flush();
    })();

    const online = () => {
      setOffline(false);
      void flush();
    };
    const gone = () => setOffline(true);
    window.addEventListener("online", online);
    window.addEventListener("offline", gone);
    const timer = window.setInterval(() => {
      void refresh();
      void flush();
    }, REFRESH_MS);

    return () => {
      mounted.current = false;
      unsubscribe();
      window.removeEventListener("online", online);
      window.removeEventListener("offline", gone);
      window.clearInterval(timer);
    };
  }, [admitted, queue, refresh, flush, syncQueueState]);

  const pendingKeys = useMemo(
    () => new Set(pending.map((claim) => claim.gameId)),
    [pending],
  );
  const hasStandings = (standings?.sections ?? []).length > 0;

  if (!admitted) {
    return <Landing onJoined={() => setAdmitted(true)} />;
  }

  const confirm = async (board: Board, result: GameResult, correcting = false) => {
    setBusy(true);
    // Queued first, sent second: an entry that reached the phone must survive
    // whatever the network does next.
    await queue.enqueue(board.game_id, result);
    const report = await queue.flush();
    syncQueueState();
    setBusy(false);
    setScreen({
      name: "done",
      board,
      result,
      queued: report.accepted === 0,
      corrected: correcting,
    });
    if (report.accepted > 0) void refresh();
  };

  return (
    <main className="mx-auto h-full w-full max-w-3xl">
      <RejectedBanner
        claims={rejected}
        onDismiss={(key) => void queue.dismiss(key).then(syncQueueState)}
      />
      {error && (
        <p role="alert" className="border-b-2 border-ink px-3 py-2 text-sm font-semibold">
          {error}
        </p>
      )}

      {screen.name === "list" && view === "boards" && (
        <BoardListScreen
          boards={boards?.boards ?? []}
          tournamentName={boards?.tournament_name}
          query={query}
          onQuery={setQuery}
          onPick={(board) => setScreen({ name: "choose", board })}
          pendingKeys={pendingKeys}
          offline={offline}
          queued={pending.length}
          tabs={<ViewTabs view={view} onView={setView} hasStandings={hasStandings} />}
        />
      )}

      {screen.name === "list" && view === "standings" && (
        <StandingsScreen
          sections={standings?.sections ?? []}
          tournamentName={boards?.tournament_name}
          query={query}
          onQuery={setQuery}
          tabs={<ViewTabs view={view} onView={setView} hasStandings={hasStandings} />}
        />
      )}

      {screen.name === "choose" && (
        <ResultChoiceScreen
          board={screen.board}
          busy={busy}
          correcting={screen.correcting ?? false}
          onChoose={(result) => void confirm(screen.board, result, screen.correcting)}
          onBack={() => setScreen({ name: "list" })}
        />
      )}

      {screen.name === "done" && (
        <DoneScreen
          board={screen.board}
          result={screen.result}
          queued={screen.queued}
          corrected={screen.corrected}
          onCorrect={() => setScreen({ name: "choose", board: screen.board, correcting: true })}
          onDone={() => {
            setQuery("");
            setScreen({ name: "list" });
            setError(null);
          }}
        />
      )}
    </main>
  );
}
