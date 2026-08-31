# Seebach — Digital Result Entry for Vega-run Tournaments

## Context

Greenfield (`C:\dev\seebach` holds only the UI sketch `enter_results.png`).

The original plan was a full tournament platform: own the player list, drive pairing engines as plugins, compute FIDE tiebreaks, publish public standings. That put the two longest-tail, highest-risk pieces — the pairing-engine plugin layer and FIDE C.07 tiebreak arithmetic — directly in front of the one genuinely novel thing: **players entering their own results on their phones instead of an arbiter retyping scoresheets.**

**v1 inverts that.** Vega stays the tournament manager. We become the digital result-entry layer that plugs into it via files:

```
  Vega                          Seebach                        Vega
  ─────                         ───────                        ─────
  set up tournament
  pair round N
  export TRF  ──────────────▶  import, open round N
                                players enter results (hall PWA)
                                arbiter reviews + confirms
                               export TRF  ─────────────────▶  import results
                                                               pair round N+1
                                                               export TRF ──▶ (loop)
```

Vega keeps doing what it is already good at and what arbiters already trust it for: pairings (which it computes via JaVaFo), tiebreaks, FIDE and national reports, and the public results view. We do the one thing it cannot: put a phone in every player's hand.

**Architectural upside:** the file round-trip *is* the plugin interface. v1 is engine-agnostic for free — Swiss-Manager or any other TRF-speaking manager works identically, with no plugin system built.

### Decisions

| Decision | Choice |
|---|---|
| Tournament setup & player list | **Vega owns it.** We only ever import. No player-list export direction in v1. |
| Pairings | **Vega owns it.** No pairing engine integration in v1. |
| Standings / tiebreaks | **Vega owns it.** No scoring module in v1. |
| Public results view | **Out of scope for v1** — Vega already publishes one. |
| Frontends | **Two**: arbiter admin app, hall PWA. |
| Result trust | Claim + arbiter release — a player entry is provisional until the arbiter confirms the round. |
| Hall access | QR-issued, device-bound, tournament-scoped token. Not IP restriction, not a shared password. |
| Submitter identity | Anonymous per board (the 3-screen sketch); audit records device + time. |
| Handoff UX | Manual download / upload, with a validation diff shown before any import commits. |
| Backend structure | CQRS — `commands/` and `queries/`, one file per use case. Anemic shared models, no value objects. |
| Auth (staff) | Self-hosted OIDC (Zitadel), passkeys + magic link. |
| Deployment | Cloud-first, fully containerised so the same stack can run on a venue box later. |

### Value beyond "digital scoresheets"

Worth naming, because it is free and it is the thing that sells the tool: a tournament can import **several Vega files as sections** (groups A/B/C) and the hall app searches across all of them at once. A player just types their name and finds their board — they do not need to know which group's list to look at. Vega cannot do this; it is one tournament per file.

---

## Milestone 0 — the spike that gates everything

**Nothing else starts until this passes.** TRF is a whole-tournament-state format, not a delta, so "export results to Vega" means handing Vega a complete TRF with round N filled in and expecting it to **merge into the existing tournament** rather than reject it or create a duplicate. Vega's TRF import was reworked in 10.5.0 and I am not willing to assume it round-trips cleanly.

Verify by hand, with real Vega and a real tournament — throwaway scripts only, no product code:

1. Vega exports TRF16 containing players and round-N pairings.
2. We can parse it and identify players, boards, colours and prior results unambiguously.
3. Vega **re-imports** a TRF we produced with round-N results filled in, merges it into the same tournament, and then pairs round N+1 correctly.
4. The round-trip is **lossless** for everything we did not touch.
5. **A mid-tournament re-pair.** Add a late entrant in Vega after round 2, re-pair, and export again — confirm we can tell the new file apart from the one we already hold and see which boards changed.
6. Forfeits, half-point byes and pairing-allocated byes survive the round-trip with the correct TRF result codes (`+ - H U Z`) — these are the codes most likely to be mishandled in either direction.

If (3) fails, the loop is broken and the arbiter is retyping results — which destroys the entire value proposition. Fallbacks to evaluate in that case, in order: Vega's own native import format; a narrower results-only exchange file; Swiss-Manager as the primary target instead.

**Prerequisite:** a licensed Vega install (v12 current) and one real completed tournament file to test against.

---

## Architecture

```
        ┌──────────────────┐   ┌─────────────────┐
        │  admin app       │   │   hall PWA      │
        │  (arbiter)       │   │   (players)     │
        └────────┬─────────┘   └────────┬────────┘
       OIDC JWT ─┤          device token ┤
                 ▼                       ▼
   ┌─────────────────────────────────────────────────┐
   │  FastAPI — CQRS, one file per use case            │
   │  commands/   ◀── all state mutation                │
   │  queries/    ◀── read shapes, SQL → DTO            │
   │  shared/ (anemic models + enums)                   │
   │  platform/ (mediator + pipeline, db, auth)         │
   │  trf/  ◀── the core asset                          │
   └───────────────────────┬─────────────────────────┘
                           ▼
                  ┌──────────────────┐   ┌──────────────┐
                  │ Postgres         │   │ Zitadel OIDC │
                  └──────────────────┘   └──────────────┘
```

Single deployable, `docker compose`: `postgres`, `api`, `zitadel`, `caddy`.

### Backend layout

```
src/seebach/
  shared/
    models.py               ALL SQLAlchemy models — Tournament, Section, Round,
                            Game, GameEvent, Device, TournamentMember.
                            Anemic: columns and relationships, no behaviour.
    enums.py                GameResult, ResultState, ResultKind, RoundState,
                            Colour, Role
  commands/
    create_tournament.py
    import_round.py         commit an import
    export_round.py         emit TRF with results, freeze the round
    claim_result.py         kiosk, idempotent
    set_result.py           arbiter override
    resolve_dispute.py
    release_round.py        arbiter confirms the round
    issue_device_token.py   returns QR payload
    revoke_device.py
  queries/
    get_tournament.py
    list_tournaments.py
    get_section.py
    preview_import.py       dry-run diff, nothing written
    get_board_list.py       hall app, across all sections
    get_arbiter_queue.py    unclaimed / claimed / disputed
    list_devices.py
  platform/
    mediator.py             dispatch + pipeline behaviours
    pipeline/               authorize, validate, idempotency, transaction, log
    db.py, auth/, errors.py, migrations/
  trf/                      LIBRARY — parser, serializer, passthrough model
```

**Models are anemic and shared.** One `models.py` for the whole schema, one `enums.py` beside it — columns, relationships and nothing else. The entities are heavily cross-referenced (an import writes tournament → section → round → game in one transaction), so per-slice models would only create import gymnastics. **No value objects** — plain columns, ints, strings and enums.

**All behaviour lives in the commands.** A command owns its own state mutation and validates its own preconditions. There is deliberately no shared transitions/rules module: most of these mutations are a single enum assignment, and a module that collects them would accrete every rule in the system until nothing could change safely. Where the same conditional genuinely appears twice, one file importing the other is fine.

**Shared code is allowed, extracted when a second caller actually appears.** Small modules named for what they do — `audit.py`, `locking.py` — sitting alongside the commands. Explicitly *not* a single `_common.py`: a file named after being shared rather than after doing something is a junk drawer, and accretes exactly the way a rules module would. The constraint is the same either way — share mechanics (appending a `game_event` row, loading a round `FOR UPDATE`), keep policy in the command that owns it.

**Invariants are enforced where they cannot be bypassed** — DB check constraints, plus a test that enumerates the legal `(from_state, action, to_state)` triples. Both beat a helper function that a command can simply forget to call.

**One file per use case**, holding its command or query, its handler and its route. Files may reference each other where it genuinely helps — the only mechanical rule is no import cycles. `trf/` stays a pure library (no DB, no FastAPI import), consumed like a third-party package.

The one real cost of the command/query split: import, preview and export are a single workflow for the arbiter but now sit in two folders.

**CQRS = two code paths, one database.** Commands use ORM entities and one transaction; queries go from SQL straight into a Pydantic DTO with no entity hydration. The mediator is ~100 lines, hand-rolled, and earns its place on two behaviours specifically: **idempotency** (kiosk claims arrive from an offline retry queue and must dedupe in one place) and **authorize** (every command is tournament- and role-scoped). It should not grow beyond that.

---

## The `trf/` library — the core asset

Everything now flows through TRF, so this is where v1 lives or dies. Two non-negotiable properties:

**1. Passthrough fidelity.** State bounces between the two systems every round, so we must never corrupt what we do not understand. Parse the fields we need into a typed model; retain every other line and field **verbatim** as opaque data; re-emit unchanged. Round-trip identity (`parse → serialize` is byte-stable for untouched input) is the primary test.

**2. Dialect awareness.** Vega writes TRF16/UTF-8 and reads TRF06 within that format's limits. The serializer targets a named dialect explicitly — never "TRF" generically.

Scope needed for v1 is a *subset*: `001` player lines with per-round triplets (opponent rank, colour `w`/`b`/`-`, result codes `1 = 0 + - W D L H U Z`), `012`/`022`/`032` headers, `XXR` rounds. We do not need the full engine-quirk matrix that a pairing integration would demand.

---

## Import / export cycle

### Round lifecycle — freeze on export

```
        import TRF (round N pairings)
              │
              ▼
        ROUND_OPEN ──── players claim results ────┐
              │                                   │
              │◀──────────────────────────────────┘
        arbiter releases
              │
              ▼
      ROUND_CONFIRMED ── export TRF ──▶ ROUND_EXPORTED  (frozen, read-only)
                                              │
                                     import next TRF
                                              ▼
                                        next ROUND_OPEN
```

**Freeze-on-export is the divergence guard.** During a round we own results; between rounds Vega owns pairings. Without the freeze, an arbiter edits a result in Vega while a player edits it here and nobody can say which is right.

### Import — always preview first

`preview_import` is a dry run returning a diff, and **nothing is written until the arbiter accepts it**:

- Matched players, new players, withdrawn players
- Prior-round results that disagree with what we hold. **Expected, not an error** — an arbiter correcting an earlier round in Vega is normal, and Vega is authoritative. But it must be listed explicitly and acknowledged, never applied silently.
- Unparseable rows
- Which round this file represents, and whether it is the expected next one

**Import replaces, it does not merge.** Vega's TRF is authoritative for tournament state — players, pairings, results — so an import rebuilds our copy of the section rather than trying to reconcile field by field. The one thing that survives is `game_event`, which is append-only and ours alone. It is therefore anchored to a natural key (section, round, player pair), not to a surrogate game id that a rebuild would invalidate.

**No player identity model in v1.** Vega owns identity; each import is a self-contained document. We read a row, show the board, collect a result, and write it back into the row we read it from. There is no cross-round matching to do and no person registry to maintain — that arrives only if we ever take ownership of the player list.

**Re-importing a round that is already open** is the one place any matching is needed: a late entry arrives after round 3 is open, the arbiter re-pairs in Vega, and the new file has different boards while we already hold claimed results. This is allowed but never silent — the diff states exactly what survives and what is dropped. Claims carry over by **matching the player pair by name, not the board number**, since Vega renumbers boards on re-pairing. That match is scoped to a single round and a single file, which is why name is sufficient and nothing needs persisting. Dropped claims stay in the audit log.

### Export

`export_round` emits the full TRF with round-N results filled in and transitions the round to `ROUND_EXPORTED`. It refuses to run while any game is unconfirmed, with an explicit, logged force-override for the arbiter.

---

## Result trust model

```
EMPTY ──claim_result──▶ CLAIMED ──release_round──▶ CONFIRMED
  │                        │
  │                        └─conflicting claim─▶ DISPUTED ─resolve_dispute─▶ CONFIRMED
  └────────────set_result (arbiter)───────────────────────▶ CONFIRMED
```

- A claim on an already-`CLAIMED` game with a **different** result flips it to `DISPUTED` and pushes it to the arbiter's queue. Same result is an idempotent no-op.
- Every claim carries a client-generated **idempotency key**, handled by the pipeline behaviour, so an offline retry can never double-submit.
- `export_round` is gated on all games being `CONFIRMED`.
- The arbiter queue shows unclaimed / claimed / disputed at a glance, so confirming a round is a scan, not a data-entry session.

**`game_event`** is an append-only audit log — actor, action, payload, IP, user agent, timestamp. Never updated, never deleted. It is the only way to answer "who entered this wrong result".

---

## Auth

- **Staff: Zitadel**, self-hosted (single Go binary + the Postgres already in the stack, first-class passkeys and magic link, runs on a venue box later). The API only ever sees a standard OIDC JWT, so the IdP stays swappable. Passkeys primary — waiting on a magic-link email over venue WiFi is a real failure mode.
- The `authorize` pipeline behaviour validates the JWT and resolves a **per-tournament** role (`owner` | `arbiter` | `assistant`) from `tournament_member`.
- **Device tokens are app-issued and never touch the IdP.** `issue_device_token` mints a tournament- and day-scoped random token (stored hashed), rendered as a QR; the phone scans it and stores it in localStorage. Individually revocable, expires at end of playing day, every use logged. A leaked token is one click to kill and the damage is bounded to reversible claims.

---

## Frontends — `apps/` (pnpm workspace, Vite + React + TypeScript + Tailwind)

Shared `packages/api-client` generated from the FastAPI OpenAPI schema (`openapi-typescript` + `openapi-fetch`), so a contract change breaks the build rather than production.

**`apps/admin`** — import with diff preview, round status, arbiter result queue, manual result override, dispute resolution, round release, export with freeze warning, device management (QR issue / revoke / last-seen).

**`apps/hall`** — a PWA, the 3-screen flow from the sketch unchanged: compact scrollable board list with sticky search → result choice (1:0 / ½:½ / 0:1) → confirm. Dense rows, large tap targets, minimal white space, readable on a five-year-old Android in a badly lit hall. Shows the **current round across all sections**.

**Offline-first, and this is not optional**: the board list is cached in IndexedDB, claims are queued with idempotency keys and retried in the background, and anything not yet acknowledged by the server is visibly marked pending. Venue WiFi *will* fail mid-round; the app must not lose entries when it does.

---

## Build order

| Milestone | Deliverable |
|---|---|
| **M0** | **Vega round-trip spike.** Go/no-go for the whole design. Throwaway code only. |
| **M1** | Repo skeleton, `docker compose`, Alembic baseline, mediator + pipeline, CI (ruff, mypy, pytest), and `trf/` parse + serialize with passthrough fidelity. |
| **M2** | Import: `preview_import` diff → `import_round` populating tournament / section / round / game. Arbiter can load a Vega file and see the boards. |
| **M3** | Device tokens + QR issue/revoke, hall PWA with the 3 screens and the offline queue. **Players can enter results.** |
| **M4** | Arbiter queue, dispute resolution, `release_round`, `export_round` with freeze. **Loop closes — full round-trip working.** |
| **M5** | Pilot at a real club event, on a section that does not matter, running in parallel with paper scoresheets. |

Zitadel can be deferred until M4 — M1–M3 can run with a single bootstrapped arbiter account — if it turns out to be a distraction early.

---

## Verification

- **Unit** — `pytest` on `trf/`, pure and fixture-free. Hypothesis property tests for round-trip identity: parse → serialize is byte-stable for input we did not modify.
- **Corpus** — real TRF files from several completed tournaments checked into the repo as golden fixtures, including messy ones (byes, forfeits, withdrawals, late entries).
- **Handler tests** — each command and query exercised directly through the mediator against a testcontainers Postgres, bypassing HTTP. This is the main test tier; one file per use case makes it the natural unit.
- **Loop test** — the full cycle in one integration test: import round 1 → claim results → dispute → resolve → release → export → assert the exported TRF parses and carries exactly the confirmed results.
- **Differential against Vega** — the manual leg, once per milestone: take our exported TRF into real Vega, confirm it merges and pairs the next round correctly.
- **End-to-end** — Playwright (`webapp-testing` skill) against the compose stack: arbiter imports a file and issues a device QR, hall app claims a result, arbiter releases, export downloads.
- **Offline drill** — hall PWA throttled offline: submit three results, restore the network, assert exactly three claims arrive and no duplicates.

---

## Risks

1. **The Vega merge-import (M0).** The single existential risk. Everything is blocked on it, which is why it is milestone zero.
2. **Manual handoff under time pressure.** Two file operations per round, in a hall, between rounds. Mitigated by explicit round state in the UI ("round 3 ready to export", "round 4 pairings loaded"), the import diff, and freeze-on-export. Still the most likely place a real event goes wrong.
3. **Divergence between the two systems.** An arbiter editing results in Vega after we exported. Freeze-on-export plus the import diff surfacing prior-round mismatches is the guard; it detects rather than prevents.
4. **Anonymous claims.** Bounded by device revocation, the audit log, and the arbiter release gate. If abuse appears in practice, the escalation path is a per-board PIN printed on the pairing slip.
5. **Churn during an open round.** Between-round churn is free — Vega handles it and we absorb a fresh state. What is *not* free: a no-show forfeit (nobody is at the board to enter it, so the arbiter must, which makes `set_result` with forfeit kinds an M4 requirement, not a nice-to-have), and a mid-round re-pair that invalidates boards we already hold claims on.
6. **TRF16 vs TRF06 dialects** — Vega writes one and reads the other within limits. The serializer must target a named dialect, never "TRF" generically.

---

## Explicitly deferred to v2+

Kept out of v1 on purpose, with the seams left in place so they can be added without a rewrite:

- **Pairing engines** (bbpPairings, JaVaFo, Berger round-robin) behind a `PairingEngine` port. Note that the Vega file loop is already the `AWAITING_EXTERNAL` case of that port — modelling the import/export cycle as a round state machine now means adding a real engine later is a new state, not a redesign.
- **Scoring / FIDE C.07 tiebreaks.** The hardest piece by a wide margin: ~20 systems, Article 16's asymmetric handling of unplayed games, and regulations that are versioned law (the pre-2023 "virtual opponent" was removed in Sep 2023, with further revisions in Apr and Aug 2024). Needs per-tournament pinned regulation editions when it does land.
- **Public results frontend** with live SSE — only worth building once we compute standings ourselves.
- **chess-results.com export**, additional interchange adapters (Swiss-Manager), and owning the player list / tournament setup.
