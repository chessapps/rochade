# M0 runbook — Swiss-Manager

Menu paths below were read off the running build, not from documentation:
**Swiss-Manager 15.0.0.3 (06.05.2026), German UI**. A newer build renames the
export to `TRF26`; if you update first, use that instead and note it.

Everything you need is in `spikes/out/`. Commands are run from `C:\dev\seebach`.

> **Before you start:** Swiss-Manager currently has `ETH.TUNx` open with 0
> players. Nothing below touches it — step 1 imports into a *new* tournament —
> but save or close it first if it matters to you.

---

## Step 0 — generate the files

```sh
uv run python spikes/make_seed.py
```

Writes two files:

| File | What it is |
|---|---|
| `spikes/out/m0-seed.trf` | 9 players, rounds 1–2 played. **ASCII only.** Use this one. |
| `spikes/out/m0-seed-accents.trf` | Identical but for two names (`Élise`, `Müller`). A separate probe — see step 7. |

The seed carries the awkward cases on purpose: a **forfeit** (`+`/`-`) and a
**pairing-allocated bye** (`U`) in round 1, a **half-point bye** (`H`) in round 2.
Round 3 is deliberately *absent* so Swiss-Manager pairs it itself.

---

## Step 1 — import the seed → **check 2, and the inbound leg for free**

`Datei` → `FIDE-Datenformat importieren TRF16`

Pick `C:\dev\seebach\spikes\out\m0-seed.trf`.

**Record:** did it create a tournament, or refuse? Any warnings?

Then check `Listen` → `Rang` (F5). It should read:

| Pts | # | Player |
|---|---|---|
| 2.0 | 4 | Mueller, Tobias |
| 1.5 | 1 | Baumann, Lukas |
| 1.5 | 2 | Chen, Wei |
| 1.5 | 3 | Dubois, Elise |
| 1.0 | 7 | Huber, Marco |
| 1.0 | 9 | Jenni, Rafael |
| 0.5 | 5 | Fischer, Jonas |
| 0.5 | 8 | Iten, Nadia |
| 0.0 | 6 | Gruber, Sarah |

⚠️ **The two that matter most.** `Listen` → `Ergebnisse` (F9) shows **one round
at a time**, and the `Rd` menu is the round selector — pick `Rd` → `1` first,
or you will be looking at round 2 and wondering where round 1 went. The `Rd`
menu only lists rounds that exist, so it is also the quickest way to see
whether an import brought the rounds in at all.

With round 1 selected, confirm:

- **Round 1, Mueller vs Iten** shows as a **forfeit**, not a normal 1:0.
- **Round 2, Fischer** shows a **half-point bye**, and **round 1, Jenni** a
  **pairing-allocated bye** — and that Jenni's bye is worth **1 point**, not ½.

If the points differ from the table, Swiss-Manager scores a PAB differently
than we assume. That is worth knowing and is not a bug on either side — it is a
tournament regulation. Just write down what it did.

> ✅ **Step 1 is done and passed** — see `spikes/FINDINGS.md`. The forfeit came
> through as a forfeit, the bye as `spielfrei` worth 1 point, and the standings
> matched on all nine rows. Start from step 2.

---

## Step 2 — raise the round count *(you will be stuck without this)*

`Eingabe` → `Turnier...` → **`Runden`: change `2` to `5`** → `OK`.

Swiss-Manager's TRF import ignores our `XXR 5` and sets the round count from
the rounds actually in the file. With 2 of 2 played the tournament reads as
finished, so `Auslosen → Auslosungsmenü` is greyed out along with every other
pairing action. Raising the count re-enables them.

Nothing we can put in the file avoids this — see `FINDINGS.md`. It is a step in
the loop, not a workaround.

While you are in that dialog, note **`Pkt. für spielfreien Spieler`**. It
should read `1`; that is the bye value, and it is a per-tournament setting.

---

## Step 3 — let Swiss-Manager pair round 3

`Auslosen` → `Auslosungsmenü...` (F6), pair round 3.

Optionally first, to get a `Z` into the file:
`Auslosen` → `Spieler ausschließen...` and withdraw **Gruber, Sarah** (#6).

---

## Step 4 — export → **checks 1, 2, 4, 7**

`Extras` → `FIDE-Daten-Export TRF16`

If it offers a round selector (`Rundenauswahl`), **include round 3**. Save as:

```
C:\dev\seebach\spikes\out\sm-round3.trf
```

Then:

```sh
uv run python spikes/inspect_export.py spikes/out/sm-round3.trf
```

**This is the gate.** Read `CHECK 1` in the output:

- **YES** → Swiss-Manager exports the paired-but-unplayed round. The loop can
  start. Continue.
- **NO** → stop and tell me. It means the export only describes completed
  games, and the outbound leg needs a different route before anything else
  matters. Look for a round selector on the export dialog first.

Also read `CHECK 4` (should say byte-identical) and `CHECK 7` (do the fields
line up with the ruler, or has TRF26 moved a column?).

---

## Step 5 — fill in results → **the file we would hand back**

```sh
uv run python spikes/fill_results.py spikes/out/sm-round3.trf --results "1:1,2:=,3:0,4:+"
```

It prints which board is which before writing, so check the names look right —
**our board numbers are derived and will not match your pairing slip**, which
is itself part of check 7. Adjust the `--results` string to match reality.

Writes `spikes/out/sm-round3-filled.trf`.

---

## Step 6 — import it back → **check 3, the one that decides everything**

`Datei` → `FIDE-Datenformat importieren TRF16`, pick `sm-round3-filled.trf`.

**Record precisely:**

- Did it **merge into the existing tournament**, or create a **second** one?
- Are rounds 1–2 still intact afterwards?
- Does `Listen` → `Ergebnisse` show the round-3 results you set?
- Did the **forfeit on board 4** survive as a forfeit?
- Can it now pair **round 4** (`Auslosen` → F6)?

If it duplicates rather than merges, try `Datei` → `Turnier Verschmelzen`
(merge tournaments) and note whether that is the intended path instead.

---

## Step 7 — the re-pair → **check 5**

Back in the tournament: add a 10th player (`Eingabe` → `Spieler Eingeben...`),
delete round 3's pairing and re-pair it, then export again as
`spikes/out/sm-round3-repaired.trf`.

```sh
uv run python spikes/compare_exports.py spikes/out/sm-round3.trf spikes/out/sm-round3-repaired.trf
```

It should name the added player and every board that moved.

---

## Step 8 — the encoding probe

Only once the above works. Import `m0-seed-accents.trf` as a **new** tournament
and look at players **#3 and #4**.

- Names correct, ratings and results still in the right columns → Swiss-Manager
  indexes TRF by character. Good.
- Names mangled, **or** the rating/federation/results wrong *on those two rows
  only* → it indexes by byte, and we must pad by bytes rather than characters.

That is a real difference in how we would have to write files, which is why it
is isolated to its own run.

---

## If TRF import turns out not to merge

The fallback, in order:

1. `Datei` → `Import PGN-File (Ergebnisse)` — results as PGN.
   Generate with `uv run python spikes/to_pgn_results.py spikes/out/sm-round3.trf --all =`.
   **Note it cannot carry forfeits or byes** — the script prints what it drops.
2. `Datei` → `XML-Import` / `XML-Export`.
3. `Extras` → `Daten Import/Export...` — the pairing/player text files.

---

## What to send back

The filled-in checklist in `spikes/README.md`, plus:

- the exported `.trf` files (they become golden fixtures — messy ones are worth
  the most)
- anything Swiss-Manager said in a dialog, verbatim
- whether it merged, duplicated or refused

That is what turns `Support.UNVERIFIED` into a fact in
`src/seebach/interchange/`, and unblocks writing the Swiss-Manager adapter.
