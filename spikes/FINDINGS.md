# M0 findings

Observed facts only. Anything not written down here is still an assumption.

**Swiss-Manager 15.0.0.3 (06.05.2026), German UI, Windows 11.**

---

## Confirmed

### Swiss-Manager reads our TRF16 — every code intact

`Datei → FIDE-Datenformat importieren TRF16` with `spikes/out/m0-seed.trf`
created the tournament and read all nine players and both rounds.

Round 1 came back as:

| Br | Weiß | Erg. | Schwarz |
|---|---|---|---|
| 1 | Baumann Lukas (FM) | 1 - 0 | Fischer Jonas |
| 2 | Gruber Sarah | 0 - 1 | Chen Wei |
| 3 | Dubois Elise (WFM) | ½ - ½ | Huber Marco |
| 4 | Mueller Tobias | **+ - -** | Iten Nadia |
| — | Jenni Rafael | **1 - -** | **spielfrei** |

Standings after round 2 matched our own computation on all nine rows, in the
same order. So the following survive the trip into Swiss-Manager:

- forfeit win / loss (`+` / `-`) — shown as a forfeit, not as a played 1:0
- pairing-allocated bye (`U`) and half-point bye (`H`)
- colours, titles (FM, WFM), ratings, federations (SUI, FRA, GER, AUT)
- `012` tournament name, `XXR` round count

### A pairing-allocated bye is worth 1 point

Jenni Rafael: `U` in round 1, loss in round 2, total **1**. Fischer Jonas:
loss in round 1, `H` in round 2, total **½**.

That matches `points_for("U") == 1.0` in `src/seebach/trf/results.py`. It is
still a *tournament regulation* rather than a property of the letter — which is
why `set_result` moves points by delta and never recomputes the column — but
the default we assume agrees with what Swiss-Manager does.

### `Listen → Ergebnisse` (F9) shows one round at a time

The `Rd` menu is the round selector, and it only lists rounds that exist. This
is a view thing, not an import thing: `Rd → 0` before an import is what "no
rounds" looks like.

---

## Still open

| # | Check | Status |
|---|---|---|
| 1 | Exports a **paired-but-unplayed** round | **not yet run — this is the gate** |
| 3 | Takes results back and **merges** into the same tournament | not yet run |
| 4 | Round trip lossless for untouched fields | not yet run |
| 5 | A re-pair is detectable | not yet run |
| 7 | Columns match the TRF16 ruler; byte vs character indexing | not yet run |

The import above created a *new* tournament from a file. That is not the same
question as check 3, which is whether importing a file for a tournament it
already holds **merges** rather than duplicating.

---

## Consequences for the code

Nothing to change yet. `interchange/vega.py` and any future
`swiss_manager.py` keep `exports_unplayed_round` and `merges_on_import` at
`Support.UNVERIFIED` until checks 1 and 3 are run — those are the two flags
`Capabilities` exists to carry, and neither has been observed.

What *is* now evidence-backed is that a Swiss-Manager adapter can use TRF16 for
the **read** direction, and that the result-code vocabulary crosses intact.
