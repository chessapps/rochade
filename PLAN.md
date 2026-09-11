# Rochade — Digital Result Entry for Managed Tournaments

## Context

The original plan was a full tournament platform: own the player list, drive pairing engines as plugins, compute FIDE tiebreaks, publish public standings. That put the two longest-tail, highest-risk pieces — the pairing-engine plugin layer and FIDE C.07 tiebreak arithmetic — directly in front of the one genuinely novel thing: **players entering their own results on their phones instead of an arbiter retyping scoresheets.**

**v1 inverts that.** An existing manager — Vega, Swiss-Manager — stays the tournament manager. We become the digital result-entry layer that plugs into it:

```
  manager                       Rochade                       manager
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
| Standings / tiebreaks | **The manager owns it.** No scoring module in v1. Its table is *shown*: Swiss-Manager's player list carries points, tiebreaks and rank, and the import keeps them (2026-09-08). |
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
  manager                              Rochade
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
whole cost of using Rochade. Anything a round needs beyond those two — a
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

**Context.** M1–M4 are built and the loop closes, but until M0 ran every TRF the system had ever read or written was produced by us. M0 is the only thing that can tell us whether a real tournament manager will take our file back, and it gates the pilot.

**Swiss-Manager: run on 2026-09-02, and the loop closes** — `docs/m0-swiss-manager.md` is the record, `tests/fixtures/swiss_manager/` the files. Two things it settled that the plan had wrong:

- The version history lists TRF only as an export, so the earlier draft expected the inbound leg to need PGN or XML. The running build has `Datei → FIDE-Datenformat importieren TRF16` — but it **creates a new tournament every time** (rank 3 in the friction ranking above). The path that merges into the open tournament is `Extras → Daten Import/Export → Spielerauslosung`, a program-specific pairing file two menus away. That is the adapter's `writes_format`.
- **Both Swiss-Manager and Vega must work** — different clubs run different programs — and they do not use the same inbound format, so the interchange is a seam, not an assumption. Vega remains unrun.

M0 therefore has two legs that may need different formats:

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
| `fill_results.py` | Take an export, fill round N with results, emit TRF16. Uses `rochade.trf` deliberately — that library is what is under test. |
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
        vega.py                swiss_manager.py         rochade.py  (v2)
     TRF16 in / TRF16 out   TRF16 in / M0 decides out   no files at all —
     merges (unverified)    (PGN? XML? TRF?)            pairs in process
```

Two abstractions, kept apart on purpose:

- **Formats** are libraries — `trf/` today, perhaps `pgn/` tomorrow. Pure, no database, no framework. They know byte layouts and nothing about any program.
- **Adapters** are the port's implementations. They compose formats and encode one program's actual behaviour: which round it exports, whether it merges on import, what it silently drops, which encoding it writes.

That split is what lets "our own implementation" be an adapter rather than a special case. It reads a round from the database and writes results back to it; it satisfies the same interface with no file anywhere. This is the `PairingEngine` port the plan already deferred to v2 — it turns out to be the same port, not a second one.

### Shape

```
src/rochade/
  interchange/
    document.py     RoundDocument, PairingRow, ManagerFile — format-neutral
    port.py         the Manager protocol + Capabilities + a registry
    vega.py         adapter
    swiss_manager.py adapter
    formats/
      trf.py        thin wrapper over the existing rochade.trf
      pgn.py        headers-only PGN results, only if M0 asks for it
  trf/              unchanged, still pure
```

`Capabilities` is part of the interface, not a footnote: **an adapter must declare what it cannot do** — whether it exports an unplayed round, whether it merges on import, which result codes survive the trip. The admin app reads those to decide what to warn about, so a lossy path (PGN cannot express `+ - H U Z`) is visible before an arbiter commits to it rather than discovered at a real event.

### What Swiss-Manager taught the port

The adapter that came out of M0 is not the one the plan sketched. It writes **Swiss-Manager's own pairing file** (`Extras → Daten Import/Export → Spielerauslosung`), because that is the path that merges into the open tournament; the TRF16 import creates a new one. Since 2026-09-07 it also *reads* Swiss-Manager's own text exports — `Spielerdaten` plus `Spielerauslosung`, joined on the start number — because the TRF16 export crashes on 15.0.0.3 for a tournament whose rounds it paired itself (`docs/m0-swiss-manager.md`). TRF16 is still read for Vega and for rounds imported earlier. Three consequences landed in the shared code rather than the adapter:

- `ResultEntry` carries both sides. A double forfeit is `("-", "-")`; mirroring white's code cannot say so, and neither format should be handed a `+` nobody earned.
- `export_round` writes only what changed since import. A bye the manager allocated, or any result it exported with the round, goes back as it came — neither counted nor checked against the adapter's vocabulary. Without this, every Swiss-Manager export was refused over the `U` on the bye row.
- Byes are the manager's. The Swiss-Manager adapter writes a row for the pairing-allocated bye exactly as exported and none for a half-point or zero-point bye, because in Swiss-Manager those are player statuses, not pairings, and a row would turn one into a pairing.

### Sequencing — and the one risk worth naming

Building the port now means designing it against a single implementation, which is the classic way to get a port wrong. Two things make it acceptable here: extracting the Vega adapter is a **pure refactor already covered by 125 tests**, and I know enough about the second implementation's shape (different format in than out, PGN lossiness, merge behaviour unknown) to design for two genuinely different cases rather than one.

So: build the port and the Vega adapter now, and let M0 fill in the Swiss-Manager adapter's inbound leg. Expect the port to need one revision once that adapter is real — that is normal and cheap, not a failure.

1. **Extract the port** with `vega.py` as its only adapter. Refactor only, no behaviour change; the existing tests must pass untouched.
2. **Run M0** (below). It decides the Swiss-Manager adapter's inbound format and fills in its `Capabilities`.
3. **Write `swiss_manager.py`** against what M0 found.
4. **`rochade.py`** stays v2, but the port is shaped so it fits without redesign.

### Files this touches

- New: `src/rochade/interchange/` as above.
- `src/rochade/features/imports/import_round.py` — `build_plan` calls `manager.read_round()` instead of `parse()`. The `_Existing`/`ImportPlan` diffing is format-neutral already and does not move.
- `src/rochade/features/rounds/export_round.py` — calls `manager.write_results()`; `ExportRound.dialect` widens into the adapter's choice.
- `src/rochade/shared/models.py` + a migration — `Section.manager` records which adapter owns it, since a tournament may hold sections from different programs.
- `apps/admin` — a manager picker on import, and surface `Capabilities` warnings in the existing import-diff panel (`src/plan.ts` already splits notes into blocking / acknowledge / informational; a lossy export is an `acknowledge`).
- Four user-facing strings name Vega and need generalising: `features/locking.py`, `features/rounds/release_round.py`, `features/imports/import_round.py`, and the API summary in `app.py`. Everything else is docstrings.
- `src/rochade/trf/dialect.py` — drop TRF06 if Vega does not need it, add TRF26 if M0 check 7 shows column drift.

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
src/rochade/
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
- **Device tokens are app-issued and never touch the IdP.** `issue_device_token` mints a tournament-scoped random token (stored hashed), rendered as a QR; the phone scans it and stores it in localStorage. Individually revocable and never expiring (a poster must keep working on day three), every use logged; a revoked device can be removed from the list. A leaked token is one click to kill and the damage is bounded to reversible claims.

---

## Frontends — `apps/` (pnpm workspace, Vite + React + TypeScript + Tailwind)

Shared `packages/api-client` generated from the FastAPI OpenAPI schema (`openapi-typescript` + `openapi-fetch`), so a contract change breaks the build rather than production.

**`apps/admin`** — five screens under one shell, built so that "where am I in this round and what do I do next" is answered before the arbiter reads anything else:

- **Tournaments** — list and create; with one tournament it goes straight there.
- **Tournament home** — one card per section with a four-step stepper (imported → entry open → released → exported), a progress bar, and **one computed primary action**: *Fix 3 disputed · 1 empty*, *Release round 4*, *Export for Swiss-Manager*, *Import round 5*. Never a choice of buttons.
- **Round board** — every board with its state; the *Attention* filter (empty + disputed) replaces the old queue and is the default while the round is open, so an empty list means done. Inline result entry, forfeits one tap further away, keyboard `1` `=` `0` on the focused row. Polls every 5 s while open, rows that changed pulse, the log is fetched the moment a board moves so a dispute arrives with the phones named. Release and freeze are native `<dialog>`s that say what they do; the hand-off card carries the manager's own menu path, the file again, and the link to the next import.
- **Import wizard** — drop the file, preview, read the diff grouped by severity (blocking on top, must-read in the middle, the roster diff folded away), import; a blocked import asks once more.
- **Devices** — real QR codes, a printable poster, revoke behind a confirm.

TanStack Query owns reads, writes, invalidation and polling; react-router serves it under `/admin`. Every irreversible action runs behind a single-flight guard — `isPending` flips only after a re-render, and a fast double click on *Export and freeze* went out twice before the guard existed.

**`apps/hall`** — a PWA, the 3-screen flow from the sketch unchanged: compact scrollable board list with sticky search → result choice (1:0 / ½:½ / 0:1) → confirm. Dense rows, large tap targets, minimal white space, readable on a five-year-old Android in a badly lit hall. Shows the **current round across all sections**.

**Offline-first, and this is not optional**: the board list is cached in IndexedDB, claims are queued with idempotency keys and retried in the background, and anything not yet acknowledged by the server is visibly marked pending. Venue WiFi *will* fail mid-round; the app must not lose entries when it does.

---

## Build order

| Milestone | Deliverable | Status |
|---|---|---|
| **M0** | **Manager round-trip spike.** Go/no-go for the whole design. Throwaway code only. Swiss-Manager first, Vega second — both must work. | **Swiss-Manager: done, the loop closes** (`docs/m0-swiss-manager.md`). **Vega: done, the loop closes** (`docs/m0-vega.md`). |
| **M1** | Repo skeleton, `docker compose`, Alembic baseline, mediator + pipeline, CI (ruff, mypy, pytest), and `trf/` parse + serialize with passthrough fidelity. | done |
| **M2** | Import: `preview_import` diff → `import_round` populating tournament / section / round / game. Arbiter can load a Vega file and see the boards. | done |
| **M3** | Device tokens + QR issue/revoke, hall PWA with the 3 screens and the offline queue. **Players can enter results.** | done |
| **M4** | Arbiter queue, dispute resolution, `release_round`, `export_round` with freeze. **Loop closes — full round-trip working.** | done, against our own files |
| **M5** | Pilot at a real club event, on a section that does not matter, running in parallel with paper scoresheets. | **unblocked for Swiss-Manager and Vega clubs** |

Zitadel is in the stack (2026-09-08): two containers sharing the stack's Postgres, a setup step that registers the arbiter app and hands its client id to the API, and the admin app signing in with an authorization-code flow against it. Any account in the Zitadel organisation is an arbiter; per-tournament roles are unchanged. The bootstrap mode where the bearer token *is* the subject still exists behind `ROCHADE_DEV_AUTH_ENABLED`, off by default, and beside Zitadel it only takes bearers that are not JWTs — it is how the smoke and browser scripts sign in locally. `deploy/README.md` has the deployment side.

### What "done" means here, and what it does not

M1–M4 are done in the sense that the loop closes: 180 backend tests, 69 frontend tests, a smoke test that runs the whole cycle against the `docker compose` stack through the API, and `scripts/admin_flow.mjs`, which runs it again through the arbiter app in a real browser — create, import, claims arriving by polling, a dispute resolved, a result from the keyboard, release, export, the file downloaded twice, the next round imported, a QR issued and revoked, and no screen overflowing at 375 px.

With Swiss-Manager it is now done in the sense that matters too: a real manager exported a round it had paired, took our results back into the same tournament, and paired the next one — twice. With Vega likewise, on 2026-09-11 (`docs/m0-vega.md`): it never exports the paired round, but it writes the two files that describe it into its tournament folder, and it takes a TRF back — as a replacement of the open tournament rather than a merge — and pairs the next round on it. Vega's surprise was the mirror of Swiss-Manager's: the import is the documented path and works; the export is the documented path and refuses.

Three questions the code raised that the Swiss-Manager run has now settled:

1. **Board numbers.** TRF does not carry them. They are derived in the FIDE order — higher score of the two players, then the sum, then the higher-ranked player's start rank, byes last — and that reproduced Swiss-Manager's pairing list on every board of every round observed. The hall app shows the same numbers as the printed slip.
2. **Points on export.** Moved by the delta of what we wrote, never recomputed — and for Swiss-Manager not written at all, since its results go back in a pairing file. The recompute would have overwritten the arbiter's bye setting; Swiss-Manager's TRF import was watched inferring that setting from the points column.
3. **`XXR` and rounds present.** Swiss-Manager writes neither `XXR` nor honours it; its round count travels as `142 N`, which the parser now reads. The highest round with pairings is the round being imported. Vega ignores `XXR` too and reads `142`; its folder files carry no round count at all, so the arbiter gives it once at the first import and the section keeps it.

---

## Verification

- **Unit** — `pytest` on `trf/`, pure and fixture-free. Hypothesis property tests for round-trip identity: parse → serialize is byte-stable for input we did not modify.
- **Corpus** — real TRF files from several completed tournaments checked into the repo as golden fixtures, including messy ones (byes, forfeits, withdrawals, late entries).
- **Handler tests** — each command and query exercised directly through the mediator against a testcontainers Postgres, bypassing HTTP. This is the main test tier; one file per use case makes it the natural unit.
- **Loop test** — the full cycle in one integration test: import round 1 → claim results → dispute → resolve → release → export → assert the exported TRF parses and carries exactly the confirmed results.
- **Differential against the real programs** — the manual leg, once per milestone: take our exported file into real Swiss-Manager and real Vega, confirm it lands and the next round pairs. Both legs done once (`docs/m0-swiss-manager.md`, `docs/m0-vega.md`); the three engines paired the nine-player seed identically.
- **End-to-end** — `scripts/admin_flow.mjs`: Playwright driving the arbiter app in the browser already on the machine against the compose stack, the whole round from create to the next import. Not in CI (it needs a browser and the stack); run before a pilot and after any change to the admin app.
- **Offline drill** — hall PWA throttled offline: submit three results, restore the network, assert exactly three claims arrive and no duplicates.

---

## Risks

1. **Vega replaces rather than merges.** Its TRF import swaps the open tournament for the file, renamed after it, with tie-breaks reset; anything the arbiter changed in Vega since the last export that the file does not carry is lost. The guide says so; the file is named after the section so at least the tournament keeps one name.
2. **Manual handoff under time pressure.** Two file operations per round, in a hall, between rounds. Mitigated by explicit round state in the UI ("round 3 ready to export", "round 4 pairings loaded"), the import diff, and freeze-on-export. Still the most likely place a real event goes wrong.
3. **Divergence between the two systems.** An arbiter editing results in Vega after we exported. Freeze-on-export plus the import diff surfacing prior-round mismatches is the guard; it detects rather than prevents.
4. **Anonymous claims.** Bounded by device revocation, the audit log, and the arbiter release gate. If abuse appears in practice, the escalation path is a per-board PIN printed on the pairing slip.
5. **Churn during an open round.** Between-round churn is free — Vega handles it and we absorb a fresh state. What is *not* free: a no-show forfeit (nobody is at the board to enter it, so the arbiter must, which makes `set_result` with forfeit kinds an M4 requirement, not a nice-to-have), and a mid-round re-pair that invalidates boards we already hold claims on.
6. **Vega counts bytes.** A UTF-8 name padded by character hangs its import outright; `rochade.vega.to_vega` pads by byte. Any other writer of a TRF for Vega has to do the same, which is why the serializer targets a named dialect, never "TRF" generically.
7. **A stale results file re-pairs Swiss-Manager.** Its pairing-file import takes the pairings in the file, so results exported from a round the arbiter has since re-paired in Swiss-Manager would undo that re-pairing silently. Nothing on our side can see the manager's state; the guard is the instruction, given at the hand-off and in the guide, to re-export and re-import before sending results back after any re-pairing. Worth a stronger guard if it bites in a pilot — e.g. refusing to export a round whose import is older than a configurable age.

---

## Explicitly deferred to v2+

Kept out of v1 on purpose, with the seams left in place so they can be added without a rewrite:

- ~~**Our own implementation**~~ — **landed (2026-09-11) as the `gacrux` adapter**: Rochade owns the player list, pairs with the FIDE Dutch system and computes C.07 tie-breaks by driving the vendored TieBreakServer (`src/rochade/gacrux/`, `features/{sections,players,pairing}/`). It is the third adapter behind the manager port, exactly as sketched: `Capabilities.native` says no file goes in or out, the import and export use cases refuse such a tournament, and the round states keep their meaning (a round is closed by the next pairing rather than by an export). `docs/gacrux.md` records what the engine does; `docs/arbiter-guide-gacrux.md` is the round from the arbiter's chair. Still open: corrections to a closed round once the next one has entries, round-robin (upstream has no Berger yet), self-registration.
- ~~**Scoring / FIDE C.07 tiebreaks.**~~ — not written here after all: TieBreakServer is FIDE's own reference implementation of every C.07 system, so embedding it (above) bought the arithmetic and its regulation versions in one go. A section stores the engine's tie-break spec; the edition it applies is the engine's current one (`"rules": "2026-03-01"`), pinned by the vendored commit.
- **Public results frontend** with live SSE — only worth building once we compute standings ourselves.
- **chess-results.com export**, further interchange adapters beyond Swiss-Manager and Vega, and owning the player list / tournament setup.
