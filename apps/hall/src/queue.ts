/**
 * The offline claim queue.
 *
 * Venue WiFi will fail mid-round; the app must not lose entries when it does.
 * Every claim is written to durable storage *before* it is sent, carries a
 * client-generated idempotency key, and is only dropped once the server has
 * acknowledged it. A retry can therefore never double-submit, and a browser
 * closed mid-round comes back with the queue intact.
 */

export type GameResult = "white_win" | "draw" | "black_win";

export interface PendingClaim {
  /** Also the Idempotency-Key. Generated once, kept across every retry. */
  key: string;
  gameId: string;
  result: GameResult;
  queuedAt: number;
  attempts: number;
  /** Set when the server refused it outright, so the UI can say so. */
  rejected?: string;
}

export interface QueueStorage {
  read(): Promise<PendingClaim[]>;
  write(claims: PendingClaim[]): Promise<void>;
}

export type SubmitOutcome =
  | { status: "accepted" }
  | { status: "rejected"; message: string }
  | { status: "unreachable" };

export type Submit = (claim: PendingClaim) => Promise<SubmitOutcome>;

export interface FlushReport {
  accepted: number;
  rejected: number;
  pending: number;
}

export class ClaimQueue {
  private claims: PendingClaim[] = [];
  private loaded = false;
  private flushing = false;
  private readonly listeners = new Set<() => void>();

  constructor(
    private readonly storage: QueueStorage,
    private readonly submit: Submit,
    private readonly newKey: () => string = defaultKey,
  ) {}

  async load(): Promise<void> {
    if (this.loaded) return;
    this.claims = await this.storage.read();
    this.loaded = true;
    this.announce();
  }

  subscribe(listener: () => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  pending(): PendingClaim[] {
    return this.claims.filter((claim) => !claim.rejected);
  }

  rejected(): PendingClaim[] {
    return this.claims.filter((claim) => claim.rejected);
  }

  pendingFor(gameId: string): PendingClaim | undefined {
    return this.pending().find((claim) => claim.gameId === gameId);
  }

  /**
   * Queue a claim. Replacing an unsent claim for the same board keeps its key,
   * so a player who changes their mind before the network returns still ends
   * up submitting exactly one claim.
   */
  async enqueue(gameId: string, result: GameResult): Promise<PendingClaim> {
    await this.load();
    const existing = this.pendingFor(gameId);
    const claim: PendingClaim = existing
      ? { ...existing, result, queuedAt: Date.now(), attempts: 0 }
      : {
          key: this.newKey(),
          gameId,
          result,
          queuedAt: Date.now(),
          attempts: 0,
        };

    this.claims = [...this.claims.filter((c) => c.key !== claim.key), claim];
    await this.persist();
    return claim;
  }

  async flush(): Promise<FlushReport> {
    await this.load();
    if (this.flushing) return this.report(0, 0);
    this.flushing = true;

    let accepted = 0;
    let rejected = 0;
    try {
      for (const claim of this.pending()) {
        const outcome = await this.submit({ ...claim, attempts: claim.attempts + 1 });
        if (outcome.status === "unreachable") {
          // Stop at the first network failure: the rest will fail the same way,
          // and burning through the queue only inflates attempt counts.
          this.bump(claim);
          break;
        }
        if (outcome.status === "accepted") {
          this.claims = this.claims.filter((c) => c.key !== claim.key);
          accepted += 1;
        } else {
          this.mark(claim, outcome.message);
          rejected += 1;
        }
      }
      await this.persist();
    } finally {
      this.flushing = false;
    }
    return this.report(accepted, rejected);
  }

  async dismiss(key: string): Promise<void> {
    this.claims = this.claims.filter((claim) => claim.key !== key);
    await this.persist();
  }

  private bump(claim: PendingClaim): void {
    this.claims = this.claims.map((c) =>
      c.key === claim.key ? { ...c, attempts: c.attempts + 1 } : c,
    );
  }

  private mark(claim: PendingClaim, message: string): void {
    this.claims = this.claims.map((c) =>
      c.key === claim.key ? { ...c, rejected: message } : c,
    );
  }

  private report(accepted: number, rejected: number): FlushReport {
    return { accepted, rejected, pending: this.pending().length };
  }

  private async persist(): Promise<void> {
    await this.storage.write(this.claims);
    this.announce();
  }

  private announce(): void {
    for (const listener of this.listeners) listener();
  }
}

function defaultKey(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}
