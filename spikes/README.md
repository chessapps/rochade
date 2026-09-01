# M0 — the manager round-trip spike

Everything in this folder is **throwaway**. It is not product code, it is not
in CI, and none of it graduates as-is. Its job is to turn documentation into
observed fact.

## Why this exists

M1–M4 are built and the loop closes. But every file the system has ever read or
written was produced by us, so the one thing we do not know is the only thing
that matters: **will a real tournament manager take a file we generated?**

Until that is answered, the honest description of this codebase is *a complete
implementation of a round trip with one unverified end*. Both `Vega` and
`SwissManager` adapters ship with their capability flags set to `UNVERIFIED`,
and the admin app tells arbiters so on screen. This spike is what changes them.

## The two legs

They may not use the same format, and that is the interesting part.

| Leg | Question |
|---|---|
| **Outbound** | Does the manager export the round that is **paired but not played**? |
| **Inbound** | Will it take our results back, **merge** them, and pair round N+1? |

For Swiss-Manager specifically, its published version history lists TRF only as
an *export* (`Extras / FIDE Data Export TRF16`, now `TRF26`). The documented
ways to get results *in* are `File / Import PGN-File (results)` (2021-07-20),
`File / Import Player-Results (XML)` (2021-04-21), and pairing text files. So
expect the two legs to differ, and try the inbound candidates in that order.

## Set up the tournament

Nine players, so there is always a bye. Declare five rounds, play two, pair the
third. Any names will do; keep them ASCII for the first run so an encoding
problem cannot masquerade as a parsing one.

1. **Round 1** — enter normal results, plus:
   - one **forfeit** (one player does not appear) → should export as `+` / `-`
   - the odd player out takes the **pairing-allocated bye** → `U`
2. **Round 2** — one player requests a **half-point bye** → `H`.
   Afterwards, **withdraw** a different player.
3. **Round 3** — pair it, and **do not enter any results**. Export here.
   The withdrawn player should show `Z`.
4. Then **add a tenth player**, re-pair round 3, and export again. Two files to
   compare.

Note the **printed board numbers** from the manager's pairing slip for round 3.
TRF does not carry board numbers, so ours are derived and will not match; check
7 is partly about how confusing that is in practice.

## Run the checks

```sh
# 1, 2, 4, 7 -- read whatever the manager gave us
python spikes/inspect_export.py round3.trf

# 3 outbound -- the file we would hand back
python spikes/fill_results.py round3.trf --results "1:1,2:=,3:0,4:+"

# 3 inbound, Swiss-Manager's likely path if TRF import does not exist
python spikes/to_pgn_results.py round3.trf --all =

# 5 -- what a re-pair changed
python spikes/compare_exports.py round3.trf round3-repaired.trf
```

Run them against `tests/fixtures/round3_messy.trf` **first**. That file has
known answers, so a clean run there proves the tooling rather than the manager.

## The checklist

Fill this in. A written answer, not a green test.

| # | Check | Swiss-Manager | Vega |
|---|---|---|---|
| 1 | Exports a paired-but-unplayed round *(do this one first)* | | |
| 2 | We parse players, boards, colours, prior results | | |
| 3 | Takes our results back and **merges** — which format? | | |
| 4 | Round trip lossless for everything we did not touch | | |
| 5 | A re-pair is detectable, changed boards identifiable | | |
| 6 | `+ - H U Z` survive with the right codes | | |
| 7 | Columns match the TRF16 ruler (or: which version?) | | |

Also record:

- **Menu paths actually used**, verbatim. The documentation and the installed
  build disagree often enough that this is worth writing down.
- **Version and build number** of each program.
- **What happened on import** — merged, duplicated, rejected, silently partial.
- Whether the manager **objected to the points column**. We now move points by
  the delta of results we wrote rather than recomputing the whole column,
  precisely because what a pairing-allocated bye is worth is a tournament
  regulation and not a property of the letter `U`.

## If check 1 fails

It redirects everything, so stop and reconsider before running the rest. In
order: look for a round selector on the export dialog (Swiss-Manager gained
"when exporting TRF files, rounds can be selected manually" on 2025-12-11);
then the manager's own pairing-list export; then blank PGN headers, which is
how Swiss-Manager users already feed pairings to online platforms.

## When it passes

1. Check the real exports into `tests/fixtures/` as golden files — messy ones
   above all. They are worth more than anything we generate ourselves.
2. Update the adapter's `Capabilities` from `UNVERIFIED` to what you saw.
3. Write `interchange/swiss_manager.py` against the format that actually worked,
   and promote whatever this folder proved into `interchange/formats/`.
4. Delete this folder.
