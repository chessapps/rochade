# Seebach — Digital Result Entry for Managed Tournaments

## Context

The original plan was a full tournament platform: own the player list, drive pairing engines as plugins, compute FIDE tiebreaks, publish public standings. That put the two longest-tail, highest-risk pieces — the pairing-engine plugin layer and FIDE C.07 tiebreak arithmetic — directly in front of the one genuinely novel thing: **players entering their own results on their phones instead of an arbiter retyping scoresheets.**

**v1 inverts that.** An existing manager — Vega, Swiss-Manager — stays the tournament manager. We become the digital result-entry layer that plugs into it:

```
  manager                       Seebach                       manager
  ───────                       ───────                       ───────
  set up tournament
  pair round N
  export      ──────────────▶  import, open round N
                                players enter results (hall PWA)
                                arbiter reviews + confirms
                               export      ─────────────────▶  import results
                                                               pair round N+1
                                                               export ──▶ (loop)
```

The manager keeps doing what it is already good at and what arbiters already trust it for: pairings, tiebreaks, FIDE and national reports, and the public results view. We do the one thing it cannot: put a phone in every player's hand.

**Which manager is an adapter choice, not an architecture.** Both Vega and Swiss-Manager must work, and eventually so must our own implementation — so the thing they plug into is a **port**, described under *The manager port* below. Note that both Vega and Swiss-Manager compute their Swiss pairings by delegating to JaVaFo, which is why a "pairing engine plugin" for either of them would be circular, and why the seam belongs at the manager rather than at the engine.

### Decisions

| Decision | Choice |
|---|---|
| Which manager | **A port with adapters.** Vega and Swiss-Manager both, our own later. Not a hardcoded choice. |
| Tournament setup & player list | **The manager owns it.** We only ever import. No player-list export direction in v1. |
| Pairings | **The manager owns it.** No pairing engine integration in v1 — and note both target managers delegate to JaVaFo anyway. |
| Standings / tiebreaks | **The manager owns it.** No scoring module in v1. |
| Public results view | **Out of scope for v1** — the managers already publish one. |
| Frontends | **Two**: arbiter admin app, hall PWA. |
| Result trust | Claim + arbiter release — a player entry is provisional until the arbiter confirms the round. |
| Hall access | QR-issued, device-bound, tournament-scoped token. Not IP restriction, not a shared password. |
| Submitter identity | Anonymous per board (the 3-screen sketch); audit records device + time. |
| Handoff UX | Manual download / upload, with a validation diff shown before any import commits. |
| Backend structure | CQRS — `commands/` and `queries/`, one file per use case. Anemic shared models, no value objects. |
| Auth (staff) | Self-hosted OIDC (Zitadel), passkeys + magic link. |
| Deployment | Cloud-first, fully containerised so the same stack can run on a venue box later. |

### Value beyond "digital scoresheets"

Worth naming, because it is free and it is the thing that sells the tool: a tournament can import **several manager files as sections** (groups A/B/C) and the hall app searches across all of them at once. A player just types their name and finds their board — they do not need to know which group's list to look at. Once sections carry their own adapter, those sections need not even come from the same program. Vega cannot do this; it is one tournament per file.

---

## The arbiter's round — the contract v1 is built around

v1 is **one feature: entering results.** Everything else a tournament needs —
setup, player list, pairings, tiebreaks, reports, the public view — stays in
the program the arbiter already runs. Those programs are *plugins* to us: each
one is an adapter behind the manager port, and Swiss-Manager is simply the
first one we verify against. Nothing in the loop below is allowed to depend on
which program is on the other end.

The loop, from the arbiter's chair:

```
  manager                              Seebach
  ───────                              ───────
  1  set up the tournament, as always
  2  pair round N, as always
  3  export the round            ───▶  import — the boards appear
                                       players enter results (hall app)
                                       arbiter reviews, releases the round
  4  import the results          ◀───  export — the round is frozen
  5  pair round N+1  (= step 2)
```

**Friction budget: two file operations per round, and nothing else.** Steps
1, 2 and 5 are what the arbiter does today without us. Steps 3 and 4 are the
whole cost of using Seebach. Anything a round needs beyond those two — a
setting to re-enter, a dialog to acknowledge, a second tournament file to
switch to — is either a defect to design away or, if the program leaves no
choice, a fact the adapter declares in `Capabilities` so the admin app can
tell the arbiter *before* they commit to it. It is never something discovered
in a hall between rounds.

That budget is the selection criterion for the inbound format. Ranked:

1. **Merges into the open tournament, all result codes intact.** Step 4 is one
   menu item. This is what TRF16 import promises and what check 3 tests.
2. **Merges, but lossy.** PGN results import merges by construction and
   cannot express `+ - H U Z`; the export would have to hand the arbiter a
   short list of forfeits and byes to set by hand. Tolerable for a pilot, not
   for v1.
3. **Full snapshot that opens as a new tournament.** The results are in, but
   the arbiter continues in a different file each round and anything the
   program keeps outside the file (tiebreak configuration, rating-list
   links) is at risk. Acceptable only if nothing better exists, and then only
   with the adapter saying so.

The file we hand back is the **whole tournament**, not a list of round-N
results. TRF has no "results only" form, and a manager that rebuilds its
cross-table from a snapshot needs every round present. `export_round` already
works this way: it patches the result cells of round N into the file it
imported and re-emits everything else byte-for-byte, so whatever the manager
wrote and we never modelled goes back to it unchanged.

**Why TRF16 is the interchange format.** It is the one format both target
programs export *and* import, and it does not require FIDE identities: the
FIDE-ID column is optional, and Swiss-Manager took our seed file with that
column blank on every row. A club event with no rated players travels through
it exactly as a FIDE-rated one does.

---

## Milestone 0 — the spike that gates everything

**Context.** M1–M4 are built and the loop closes, but every TRF the system has ever read or written was produced by us. M0 is the only thing that can tell us whether a real tournament manager will take our file back. It is unrun, and it still gates the pilot.

Two things changed the shape of it:

- **Swiss-Manager is available now**, and **both Swiss-Manager and Vega must work** — different clubs run different programs. The interchange format therefore has to become a seam rather than a hardcoded assumption.
- The version history on swiss-manager.at lists TRF only as an export, so the
  earlier draft of this plan assumed the inbound leg would need PGN or XML.
  **The running build says otherwise**: `Datei → FIDE-Datenformat importieren
  TRF16` exists in 15.0.0.3, and it read our seed with every result code, title,
  rating and federation intact (see `spikes/FINDINGS.md`). What is *not* yet
  known is whether that import **merges into the tournament that is already
  open** or creates a second one — which is the difference between rank 1 and
  rank 3 in the friction ranking above, and is what check 3 decides.

So M0 splits into two legs that may need different formats:

- **Outbound** — can the manager emit the round that has been *paired but not played*?
- **Inbound** — will it take our results back, merge them, and pair the next round?

### The checks

Run against Swiss-Manager first (it is installed), then Vega. Record pass/fail per program.

| # | Check | Leg |
|---|---|---|
| 1 | The export contains a round with pairings and **no results**. A FIDE rating export describes completed games; if that is all we get there is no open board to enter and the loop cannot start. **Cheapest check, run it first — a "no" here redirects the whole spike.** | out |
| 2 | We parse it and identify players, boards, colours and prior results unambiguously. | out |
| 3 | The manager takes our results back, **merges into the same tournament** rather than duplicating or rejecting it, and pairs round N+1 correctly. Try each candidate format in turn: TRF16, then PGN results, then XML player-results. | in |
| 4 | Round-trip is **lossless** for everything we did not touch (`inspect_export.py` checks this automatically). | out |
| 5 | **Mid-tournament re-pair.** Add a late entrant after round 2, re-pair, export again — confirm we can tell the new file from the one we hold and see which boards changed. | out |
| 6 | Forfeits, half-point byes and pairing-allocated byes survive with the right codes (`+ - H U Z`). Note that **PGN cannot express these** — if the inbound leg lands on PGN, this is where it leaks. | both |
| 7 | **Column drift.** TRF26 exists and we target TRF16. Check a player row against the ruler `inspect_export.py` prints. TRF06 was deactivated in Swiss-Manager on 2023-11-02, so `Dialect.TRF06` may be dead weight. | out |

If check 3 fails for every format, the arbiter is retyping results and the value proposition is gone.

### The spike kit — `spikes/`, throwaway, not product code

| File | Purpose |
|---|---|
| `inspect_export.py` | Point at any manager export; reports checks 1, 2, 4 and 7 in one pass, including a column ruler for TRF16/26 drift. Reads *through the real adapter*, so a pass is evidence about the shipped code. |
| `fill_results.py` | Take an export, fill round N with results, emit TRF16. Uses `seebach.trf` deliberately — that library is what is under test. |
| `to_pgn_results.py` | The same results as a headers-only PGN, for `File / Import PGN-File (results)`. Must report what it drops: PGN has no forfeit or bye vocabulary. |
| `compare_exports.py` | Diff two manager exports for check 5 — players added/removed, which boards moved. |
| `README.md` | The recipe below, plus a checklist with a column per program to fill in. |

All four are written, linted, and validated against the two golden fixtures. Running `inspect_export.py` on `round3_messy.trf` immediately caught a real export bug -- see below.

### The synthetic tournament to key in

Nine players, so there is always a bye. Declare five rounds, play two, pair the third.

- **R1** — normal results, plus one **forfeit** (`+`/`-`) and the pairing-allocated **bye** (`U`).
- **R2** — one player takes a **half-point bye** (`H`); another **withdraws** afterwards (should show as `Z` in R3).
- **R3** — **paired, not played.** This is the export that matters.
- Then add a **tenth player**, re-pair R3, export again → `compare_exports.py` for check 5.

---

## The manager port — the standard interface, and adapters behind it

**The port is not "which file format".** It is *who owns the pairings and the standings*. File interchange is merely how two of the three adapters happen to talk; the third will not use files at all.

```
                       ┌───────────────────────────┐
   import_round  ────▶ │      Manager (port)       │
   export_round  ────▶ │  read_round / write_results │
                       └─────────────┬─────────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              ▼                      ▼                      ▼
        vega.py                swiss_manager.py         seebach.py  (v2)
     TRF16 in / TRF16 out   TRF16 in / M0 decides out   no files at all —
     merges (unverified)    (PGN? XML? TRF?)            pairs in process
```

Two abstractions, kept apart on purpose:

- **Formats** are libraries — `trf/` today, perhaps `pgn/` tomorrow. Pure, no database, no framework. They know byte layouts and nothing about any program.
- **Adapters** are the port's implementations. They compose formats and encode one program's actual behaviour: which round it exports, whether it merges on import, what it silently drops, which encoding it writes.

That split is what lets "our own implementation" be an adapter rather than a special case. It reads a round from the database and writes results back to it; it satisfies the same interface with no file anywhere. This is the `PairingEngine` port the plan already deferred to v2 — it turns out to be the same port, not a second one.

### Shape

```
src/seebach/
  interchange/
    document.py     RoundDocument, PairingRow, ManagerFile — format-neutral
    port.py         the Manager protocol + Capabilities + a registry
    vega.py         adapter
    swiss_manager.py adapter
    formats/
      trf.py        thin wrapper over the existing seebach.trf
      pgn.py        headers-only PGN results, only if M0 asks for it
  trf/              unchanged, still pure
```

`Capabilities` is part of the interface, not a footnote: **an adapter must declare what it cannot do** — whether it exports an unplayed round, whether it merges on import, which result codes survive the trip. The admin app reads those to decide what to warn about, so a lossy path (PGN cannot express `+ - H U Z`) is visible before an arbiter commits to it rather than discovered at a real event.

### Sequencing — and the one risk worth naming

Building the port now means designing it against a single implementation, which is the classic way to get a port wrong. Two things make it acceptable here: extracting the Vega adapter is a **pure refactor already covered by 125 tests**, and I know enough about the second implementation's shape (different format in than out, PGN lossiness, merge behaviour unknown) to design for two genuinely different cases rather than one.

So: build the port and the Vega adapter now, and let M0 fill in the Swiss-Manager adapter's inbound leg. Expect the port to need one revision once that adapter is real — that is normal and cheap, not a failure.

1. **Extract the port** with `vega.py` as its only adapter. Refactor only, no behaviour change; the existing tests must pass untouched.
2. **Run M0** (below). It decides the Swiss-Manager adapter's inbound format and fills in its `Capabilities`.
3. **Write `swiss_manager.py`** against what M0 found.
4. **`seebach.py`** stays v2, but the port is shaped so it fits without redesign.

### Files this touches

- New: `src/seebach/interchange/` as above.
- `src/seebach/features/imports/import_round.py` — `build_plan` calls `manager.read_round()` instead of `parse()`. The `_Existing`/`ImportPlan` diffing is format-neutral already and does not move.
- `src/seebach/features/rounds/export_round.py` — calls `manager.write_results()`; `ExportRound.dialect` widens into the adapter's choice.
- `src/seebach/shared/models.py` + a migration — `Section.manager` records which adapter owns it, since a tournament may hold sections from different programs.
- `apps/admin` — a manager picker on import, and surface `Capabilities` warnings in the existing import-diff panel (`src/plan.ts` already splits notes into blocking / acknowledge / informational; a lossy export is an `acknowledge`).
- Four user-facing strings name Vega and need generalising: `features/locking.py`, `features/rounds/release_round.py`, `features/imports/import_round.py`, and the API summary in `app.py`. Everything else is docstrings.
- `src/seebach/trf/dialect.py` — drop TRF06 if Vega does not need it, add TRF26 if M0 check 7 shows column drift.

### Verification

**The port extraction** is a refactor, so the bar is that nothing moves:

1. `uv run pytest -q` — all 125 backend tests pass **unmodified**. If a test needs changing, the refactor changed behaviour and that is a bug, not a test to update. The one expected exception is wherever a test names the format explicitly.
2. `uv run ruff check src tests`, `uv run mypy`, `pnpm -r run typecheck`.
3. The API surface diff is reviewed deliberately: `uv run python scripts/dump_openapi.py && pnpm run api:types`, then `git diff packages/api-client/src/schema.d.ts`. `ExportRound.dialect` widening is a real contract change and should show up here.
4. `python scripts/smoke.py` still closes the loop against the compose stack.
5. A new test that a second adapter can be registered and selected — otherwise the port is a protocol with one implementation and nothing proves it is a seam at all. A trivial fake adapter in the test suite is enough.

**M0** is manual and its bar is different — it is a written answer, not a green test:

1. Run the spike kit against `tests/fixtures/round1_pairings.trf` and `round3_messy.trf` **first**. The fixtures have known answers, so this proves the tooling rather than the manager.
2. Then by hand against Swiss-Manager, filling in the checklist, check 1 before anything else.
3. Record real Swiss-Manager exports as golden fixtures in `tests/fixtures/` — messy ones especially. They are worth more than anything we generate ourselves.

**Prerequisite:** Swiss-Manager (installed). Vega remains a separate, later gate.

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

**One folder per REST resource.** The API surface and the source tree have the
same shape, so a route and the file that serves it are found the same way.

```
src/seebach/
  shared/
    models.py               ALL SQLAlchemy models — Tournament, Section, Round,
                            Game, GameEvent, Device, TournamentMember.
                            Anemic: columns and relationships, no behaviour.
    enums.py                GameResult, ResultState, ResultKind, RoundState,
                            Colour, Role
  features/
    audit.py                append a game_event row
    locking.py              load a round FOR UPDATE, refuse a frozen one
    scoping.py              game/round/device → tournament, for authorization

    tournaments/            /api/tournaments
      create_tournament.py
      list_tournaments.py
      get_tournament.py     sections, rounds, board counts by state
      add_member.py         per-tournament role
    imports/                /api/tournaments/{id}/imports
      preview_import.py     dry-run diff, nothing written
      import_round.py       commit an import; owns build_plan
    boards/                 /api/tournaments/{id}/boards
      get_board_list.py     hall app, across all sections
    queue/                  /api/tournaments/{id}/queue
      get_arbiter_queue.py  disputed / empty / claimed
    devices/                /api/tournaments/{id}/devices, /api/devices/{id}
      issue_device_token.py returns the QR payload
      list_devices.py
      revoke_device.py
    rounds/                 /api/rounds/{id}
      get_round.py
      release_round.py      arbiter confirms the round
      export_round.py       emit TRF with results, freeze the round
    games/                  /api/games/{id}
      claim_result.py       kiosk, idempotent
      set_result.py         arbiter override, forfeits and byes
      resolve_dispute.py

  platform/
    mediator.py             dispatch + pipeline behaviours
    pipeline/               authorize, validate, idempotency, transaction, log
    db.py, auth/, errors.py, migrations/
  registry.py               every route module, in REST order
  trf/                      LIBRARY — parser, serializer, passthrough model
```

**Models are anemic and shared.** One `models.py` for the whole schema, one `enums.py` beside it — columns, relationships and nothing else. The entities are heavily cross-referenced (an import writes tournament → section → round → game in one transaction), so per-slice models would only create import gymnastics. **No value objects** — plain columns, ints, strings and enums.

**All behaviour lives in the commands.** A command owns its own state mutation and validates its own preconditions. There is deliberately no shared transitions/rules module: most of these mutations are a single enum assignment, and a module that collects them would accrete every rule in the system until nothing could change safely. Where the same conditional genuinely appears twice, one file importing the other is fine.

**Shared code is allowed, extracted when a second caller actually appears.** Small modules named for what they do — `audit.py`, `locking.py`, `scoping.py` — at the root of `features/`, beside the features that use them. Explicitly *not* a single `_common.py`: a file named after being shared rather than after doing something is a junk drawer, and accretes exactly the way a rules module would. The constraint is the same either way — share mechanics (appending a `game_event` row, loading a round `FOR UPDATE`), keep policy in the command that owns it.

**Invariants are enforced where they cannot be bypassed** — DB check constraints, plus a test that enumerates the legal `(from_state, action, to_state)` triples. Both beat a helper function that a command can simply forget to call.

**One file per use case**, holding its command or query, its handler and its route. Files may reference each other where it genuinely helps — the only mechanical rule is no import cycles. `trf/` stays a pure library (no DB, no FastAPI import), consumed like a third-party package.

**The command/query split is carried by types, not by folders.** `Command` and `Query` are what decide whether a message opens a transaction, whether it dedupes on an idempotency key, and what it defaults to being allowed to touch. Grouping the *files* by that distinction as well was a mistake: it separated `preview_import` from `import_round`, which are one workflow for the arbiter and share a plan builder. Grouping by resource puts them next to each other and costs the split nothing, because the split never depended on the layout.

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

| Milestone | Deliverable | Status |
|---|---|---|
| **M0** | **Manager round-trip spike.** Go/no-go for the whole design. Throwaway code only. Swiss-Manager first, Vega second — both must work. | **running** — seed imported into Swiss-Manager, check 2 passed; check 1 (the gate) and check 3 pending |
| **M1** | Repo skeleton, `docker compose`, Alembic baseline, mediator + pipeline, CI (ruff, mypy, pytest), and `trf/` parse + serialize with passthrough fidelity. | done |
| **M2** | Import: `preview_import` diff → `import_round` populating tournament / section / round / game. Arbiter can load a Vega file and see the boards. | done |
| **M3** | Device tokens + QR issue/revoke, hall PWA with the 3 screens and the offline queue. **Players can enter results.** | done |
| **M4** | Arbiter queue, dispute resolution, `release_round`, `export_round` with freeze. **Loop closes — full round-trip working.** | done, against our own files |
| **M5** | Pilot at a real club event, on a section that does not matter, running in parallel with paper scoresheets. | blocked on M0 |

Zitadel is still deferred. Staff auth runs in a bootstrap mode where the bearer token *is* the subject, gated behind `SEEBACH_DEV_AUTH_ENABLED`, which is off by default — an insecure auth mode has to be asked for. The OIDC path is written and wired; it activates on `SEEBACH_OIDC_ISSUER`. The API only ever sees a standard OIDC JWT either way, so nothing but configuration changes when Zitadel lands.

### What "done" means here, and what it does not

M1–M4 are done in the sense that the loop closes: 125 backend tests, 14 frontend tests, and a smoke test that runs the whole cycle against the `docker compose` stack — create, preview, import, issue a QR token, claim from a device, retry, release, export, confirm the round is frozen.

It is **not** done in the sense that matters most. Every TRF the system has ever read or written was produced by us. M0 is the only thing that can tell us whether a real manager will take a file we generated, and it remains the go/no-go for the whole design. Until it runs, the honest description of this codebase is: a complete implementation of a round trip with one unverified end.

Three things M0 should also settle now that the code exists and raises the questions concretely:

1. **Board numbers are ours, not the manager's.** TRF does not carry them, so we derive them by ordering white players by starting rank. The manager prints its own numbers on the pairing slips and they will not match. The hall app is search-by-name so this is cosmetic, but it needs checking against a real pairing slip before a pilot.
2. ~~**Points are recomputed on export.**~~ **Fixed.** The spike kit's check 4 caught it on its first run: recomputing the whole points column asserted our reading of every code in the file, including the pairing-allocated bye -- and what a PAB is worth is a tournament regulation, not a property of the letter `U`. Some events award 1 point, some 0.5. Points now move by the *delta* of results we actually wrote, so a number we were never told cannot be corrupted. M0 should still confirm a manager accepts the adjusted column.
3. **`XXR` and rounds present can disagree.** We treat the highest round with pairings as the round being imported, and the declared count as the tournament length. Real Vega files should confirm that is the right reading.


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

- **Our own implementation** — pairing engines (bbpPairings, JaVaFo, Berger round-robin) plus owning the player list and tournament setup. This is a third adapter behind the manager port, not a new architecture: it reads a round from the database and writes results back to it, satisfying the same interface with no file anywhere. Needs the scoring work below before it is useful, since a manager that cannot compute standings is not a manager.
- **Scoring / FIDE C.07 tiebreaks.** The hardest piece by a wide margin: ~20 systems, Article 16's asymmetric handling of unplayed games, and regulations that are versioned law (the pre-2023 "virtual opponent" was removed in Sep 2023, with further revisions in Apr and Aug 2024). Needs per-tournament pinned regulation editions when it does land.
- **Public results frontend** with live SSE — only worth building once we compute standings ourselves.
- **chess-results.com export**, additional interchange adapters (Swiss-Manager), and owning the player list / tournament setup.
