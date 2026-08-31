import { describe, expect, it } from "vitest";

import { ClaimQueue, type PendingClaim, type QueueStorage, type SubmitOutcome } from "./queue";

class MemoryStorage implements QueueStorage {
  claims: PendingClaim[] = [];
  async read(): Promise<PendingClaim[]> {
    return [...this.claims];
  }
  async write(claims: PendingClaim[]): Promise<void> {
    this.claims = [...claims];
  }
}

function keys(): () => string {
  let n = 0;
  return () => `key-${++n}`;
}

describe("the offline claim queue", () => {
  it("keeps a claim until the server acknowledges it", async () => {
    const storage = new MemoryStorage();
    let online = false;
    const seen: string[] = [];
    const queue = new ClaimQueue(
      storage,
      async (claim): Promise<SubmitOutcome> => {
        if (!online) return { status: "unreachable" };
        seen.push(claim.key);
        return { status: "accepted" };
      },
      keys(),
    );

    await queue.enqueue("game-1", "white_win");
    expect(await queue.flush()).toEqual({ accepted: 0, rejected: 0, pending: 1 });
    // Durable: it survives the app being closed and reopened.
    expect(storage.claims).toHaveLength(1);

    online = true;
    expect(await queue.flush()).toEqual({ accepted: 1, rejected: 0, pending: 0 });
    expect(seen).toEqual(["key-1"]);
    expect(storage.claims).toEqual([]);
  });

  it("submits one claim per board however many times it retries", async () => {
    const storage = new MemoryStorage();
    let attempts = 0;
    let online = false;
    const queue = new ClaimQueue(
      storage,
      async (): Promise<SubmitOutcome> => {
        attempts += 1;
        return online ? { status: "accepted" } : { status: "unreachable" };
      },
      keys(),
    );

    await queue.enqueue("game-1", "draw");
    await queue.flush();
    await queue.flush();
    await queue.flush();
    online = true;
    await queue.flush();

    expect(attempts).toBe(4);
    expect(queue.pending()).toEqual([]);
  });

  it("reuses the key when a player changes their mind before it is sent", async () => {
    const storage = new MemoryStorage();
    const sent: PendingClaim[] = [];
    const queue = new ClaimQueue(
      storage,
      async (claim): Promise<SubmitOutcome> => {
        sent.push(claim);
        return { status: "accepted" };
      },
      keys(),
    );

    await queue.enqueue("game-1", "white_win");
    await queue.enqueue("game-1", "black_win");
    expect(queue.pending()).toHaveLength(1);

    await queue.flush();
    expect(sent).toHaveLength(1);
    expect(sent[0]?.key).toBe("key-1");
    expect(sent[0]?.result).toBe("black_win");
  });

  it("submits three queued results exactly once when the network returns", async () => {
    const storage = new MemoryStorage();
    let online = false;
    const sent: string[] = [];
    const queue = new ClaimQueue(
      storage,
      async (claim): Promise<SubmitOutcome> => {
        if (!online) return { status: "unreachable" };
        sent.push(`${claim.gameId}:${claim.result}`);
        return { status: "accepted" };
      },
      keys(),
    );

    await queue.enqueue("game-1", "white_win");
    await queue.enqueue("game-2", "draw");
    await queue.enqueue("game-3", "black_win");
    await queue.flush();
    expect(sent).toEqual([]);

    online = true;
    const report = await queue.flush();

    expect(report).toEqual({ accepted: 3, rejected: 0, pending: 0 });
    expect(sent).toEqual([
      "game-1:white_win",
      "game-2:draw",
      "game-3:black_win",
    ]);
    expect(new Set(sent).size).toBe(3);
  });

  it("stops at the first network failure rather than burning the queue", async () => {
    const storage = new MemoryStorage();
    let calls = 0;
    const queue = new ClaimQueue(
      storage,
      async (): Promise<SubmitOutcome> => {
        calls += 1;
        return { status: "unreachable" };
      },
      keys(),
    );

    await queue.enqueue("game-1", "draw");
    await queue.enqueue("game-2", "draw");
    await queue.flush();

    expect(calls).toBe(1);
    expect(queue.pending()).toHaveLength(2);
  });

  it("keeps a rejected claim visible instead of silently dropping it", async () => {
    const storage = new MemoryStorage();
    const queue = new ClaimQueue(
      storage,
      async (): Promise<SubmitOutcome> => ({
        status: "rejected",
        message: "the arbiter has already confirmed this board",
      }),
      keys(),
    );

    await queue.enqueue("game-1", "white_win");
    const report = await queue.flush();

    expect(report).toEqual({ accepted: 0, rejected: 1, pending: 0 });
    expect(queue.rejected()[0]?.rejected).toContain("already confirmed");
    // A rejection is not retried -- retrying would fail identically forever.
    expect(await queue.flush()).toEqual({ accepted: 0, rejected: 0, pending: 0 });

    await queue.dismiss(queue.rejected()[0]!.key);
    expect(queue.rejected()).toEqual([]);
  });

  it("restores the queue from storage on load", async () => {
    const storage = new MemoryStorage();
    storage.claims = [
      { key: "key-9", gameId: "game-7", result: "draw", queuedAt: 1, attempts: 2 },
    ];
    const queue = new ClaimQueue(storage, async () => ({ status: "accepted" }), keys());

    await queue.load();
    expect(queue.pendingFor("game-7")?.key).toBe("key-9");
  });
});
