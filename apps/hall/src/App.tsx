import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { fetchBoards, submitClaim, type Board, type BoardList } from "./api";
import { ClaimQueue, type GameResult, type PendingClaim } from "./queue";
import {
  BoardListScreen,
  ConfirmScreen,
  DoneScreen,
  RejectedBanner,
  ResultChoiceScreen,
} from "./screens";
import { cacheBoards, cachedBoards, deviceToken, queueStorage, tournamentId } from "./storage";

type Screen =
  | { name: "list" }
  | { name: "choose"; board: Board }
  | { name: "confirm"; board: Board; result: GameResult }
  | { name: "done"; board: Board; result: GameResult; queued: boolean };

const REFRESH_MS = 20_000;

export function App() {
  const queue = useMemo(() => new ClaimQueue(queueStorage, submitClaim), []);
  const [screen, setScreen] = useState<Screen>({ name: "list" });
  const [boards, setBoards] = useState<BoardList | null>(null);
  const [query, setQuery] = useState("");
  const [offline, setOffline] = useState(!navigator.onLine);
  const [pending, setPending] = useState<PendingClaim[]>([]);
  const [rejected, setRejected] = useState<PendingClaim[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
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
  }, [queue, refresh, flush, syncQueueState]);

  const pendingKeys = useMemo(
    () => new Set(pending.map((claim) => claim.gameId)),
    [pending],
  );

  if (!deviceToken() || !tournamentId()) {
    return <NeedsToken />;
  }

  const confirm = async (board: Board, result: GameResult) => {
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
    });
    if (report.accepted > 0) void refresh();
  };

  return (
    <main className="h-full">
      <RejectedBanner
        claims={rejected}
        onDismiss={(key) => void queue.dismiss(key).then(syncQueueState)}
      />
      {error && <p className="bg-rose-900/80 px-4 py-2 text-sm">{error}</p>}

      {screen.name === "list" && (
        <BoardListScreen
          boards={boards?.boards ?? []}
          query={query}
          onQuery={setQuery}
          onPick={(board) => setScreen({ name: "choose", board })}
          pendingKeys={pendingKeys}
          offline={offline}
          queued={pending.length}
        />
      )}

      {screen.name === "choose" && (
        <ResultChoiceScreen
          board={screen.board}
          onChoose={(result) =>
            setScreen({ name: "confirm", board: screen.board, result })
          }
          onBack={() => setScreen({ name: "list" })}
        />
      )}

      {screen.name === "confirm" && (
        <ConfirmScreen
          board={screen.board}
          result={screen.result}
          busy={busy}
          onConfirm={() => void confirm(screen.board, screen.result)}
          onBack={() => setScreen({ name: "choose", board: screen.board })}
        />
      )}

      {screen.name === "done" && (
        <DoneScreen
          board={screen.board}
          result={screen.result}
          queued={screen.queued}
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

function NeedsToken() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center">
      <p className="text-4xl">📷</p>
      <h1 className="text-xl font-semibold">Scan the QR code</h1>
      <p className="max-w-xs text-slate-400">
        The arbiter has a QR code that admits this phone to the tournament for
        today. Nothing here works without it.
      </p>
    </div>
  );
}
