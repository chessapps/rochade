# M0 — the manager round-trip spike

Everything in this folder is **throwaway**: not product code, not in CI. Its job
is to turn documentation into observed fact, one manager at a time.

## Status

| Manager | Result | Record |
|---|---|---|
| **Swiss-Manager 15.0.0.3** | **done — the loop closes.** TRF16 out, its own pairing file back in, merged into the open tournament. | `docs/m0-swiss-manager.md`; real files under `tests/fixtures/swiss_manager/` |
| **Vega 12.1.8** | **done — the loop closes.** Two files from its tournament folder in, a TRF back that replaces the open tournament; the next round pairs. Its rating report refuses to export a paired round; its own `engine.man` goes stale after a manual change. | `docs/m0-vega.md`; real files under `tests/fixtures/vega/` |

The Swiss-Manager run also settled two design questions for every adapter:
board numbers follow the FIDE order (they now match the manager's pairing list),
and results cross the port as a pair of codes so a double forfeit exists.

## How it was run against Vega

The lesson from Swiss-Manager, in one line: **the obvious inbound path may be
the wrong one.** Its TRF16 import created a fresh tournament every time; the
path that merged was a program-specific pairing file two menus away. Vega's
surprise was the mirror image: the documented *export* refuses while a round is
unplayed, and the files it writes into its tournament folder are the way in.
The steps below are what the plan said; `docs/m0-vega.md` is what happened.
`vega_gui.py` drove the clicks and `vega_pairing_trf.py` built the first TRF we
handed back, before the product did it from the folder files.

1. `uv run python spikes/make_seed.py` — nine players, rounds 1–2 played with a
   forfeit, a pairing-allocated bye and a half-point bye, round 3 absent.
   Import `spikes/out/m0-seed.trf` into Vega **or** key the same tournament in
   by hand if Vega will not create one from a TRF.
2. Pair round 3 in Vega and export TRF16 → `spikes/out/vega-round3.trf`.
3. `uv run python spikes/inspect_export.py spikes/out/vega-round3.trf` —
   **check 1 is the gate**: does the export contain the paired-but-unplayed round?
4. `uv run python spikes/fill_results.py spikes/out/vega-round3.trf --manager vega --results "1:1,2:=,3:0,4:+"`
   → `vega-round3-filled.trf`. Board numbers now match what Vega prints if it
   uses the FIDE order too; write down whether they do.
5. Import the filled file into Vega. **Record precisely** whether it merged into
   the open tournament, created a second one, or refused — and whether round 4
   can then be paired. This decides the adapter's `writes_format`.
6. Add a tenth player, re-pair, export again, and run
   `uv run python spikes/compare_exports.py before.trf after.trf` for the
   re-pair diff.
7. Repeat step 1 with `m0-seed-accents.trf` for the byte-vs-character probe.

Then: set the flags in `interchange/vega.py` from what was observed, write down
the two menu paths as `export_howto` / `import_howto`, and check the real Vega
files in as fixtures. Messy ones are worth the most.

## Driving Swiss-Manager from a script

`swiss_manager_gui.py` is the pywinauto driver that produced the fixtures --
`menus`, `trf-export`, `pairings-export`, `pairings-import`, `shot`. It needs
its own venv (see its docstring) and Swiss-Manager already running with the
tournament open. Use it to re-run a probe against a new build, or to check a
question the record does not answer, without clicking through the dialogs.

## The checks, for reference

| # | Check |
|---|---|
| 1 | The export contains a round with pairings and **no results** — the gate |
| 2 | We identify players, boards, colours and prior results |
| 3 | The manager takes results back, **merges** into the same tournament, pairs the next round |
| 4 | Round trip lossless for untouched fields (`inspect_export.py` does this) |
| 5 | A mid-tournament re-pair is detectable (`compare_exports.py`) |
| 6 | `+ - H U Z` survive in both directions |
| 7 | Column drift against the TRF16 ruler; byte vs character indexing |
