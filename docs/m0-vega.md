# M0 findings — Vega

Observed facts only. Anything not written down here is still an assumption.

**Vega 12.1.8 (8 September 2026), English UI, unregistered copy, Windows 11.**
Run on 2026-09-11 against the synthetic nine-player tournament in
`spikes/make_seed.py`, driven by `spikes/vega_gui.py` (screenshots under
`spikes/out/shots/`). The files Vega produced are checked in under
`tests/fixtures/vega/`.

---

## The verdict

**The loop closes, with two files in and one file out per round, and the
arbiter stays in the tournament they already have open — under a new name.**

(Amended the same evening: `crosstable.txt` turned out to exist only once a
result has been entered, so a fresh tournament's round 1 had no players file.
`engine26.trf`, which Vega writes at every engine pairing, took its place —
see *The tournament folder*.)

| Leg | Menu | Format | Verdict |
|---|---|---|---|
| manager → us | none: `engine26.trf` (or `crosstable.txt`) + `SortedPairs.txt` from the tournament folder | a TRF and a plain text file, UTF-8 | **the way in**; the pairing list is rewritten at every pairing and every manual change to one, the TRF at every engine pairing |
| manager → us (documented) | `Rating Report → FIDE → Rating Report to FIDE` | TRF16 / TRF26 | **refuses**: "In round 3 table 1 there is an unfinished game. Please insert the result or no report will be saved" |
| us → manager | `File → Import tournament in FIDE format - TRF2026` | TRF16 with two Vega adjustments (below) | **the way back**: results, forfeits and byes land on the boards; the next round pairs |

There is no file import of results in Vega 12: the manual offers keying
them, its own VegaResults online service, or importing a whole tournament as
a TRF. The last is what works, and it is not a merge. Vega **replaces** the
open tournament with the file — same folder, same play system, but renamed
after the file's stem (`A.trf` becomes the tournament `A`, saved as `A.vegz`
next to the old one), with the arbiter and tie-break settings that the TRF
does not carry reset. Rochade therefore names the file after the section and
keeps the same name every round, so the arbiter sees one tournament, not one
per round.

| # | Check | Result |
|---|---|---|
| 1 | Exports a paired-but-unplayed round | **NO via the rating report**, which refuses outright. **YES via the folder**: `SortedPairs.txt` lists the boards the moment they are paired |
| 2 | We identify players, boards, colours, prior results | **YES** — `crosstable.txt` has start numbers, names, ratings, titles, federations and one cell per round; `SortedPairs.txt` has the boards with colours, by name |
| 3 | Results merge back and the next round pairs | **YES** via `Import TRF2026`, as a replace-in-place; round 4 paired on the results we sent |
| 4 | Round trip lossless for untouched fields | not applicable — Vega gives us no TRF to hand back, so the file is ours, built from the two folder files |
| 5 | A re-pair is detectable | **YES** — the folder files change; a late-comer arrives as a new start number with `--` for the rounds missed |
| 6 | `+ - H U Z` survive | `+ -` (shown as `1F-0F`), `U` (`PAB`), `H` (`HPB`) both ways; Vega itself writes `Z` for a late-comer's missed rounds. Unrated `W D L` not tried |
| 7 | Column drift | **Vega counts bytes.** A UTF-8 name padded by character hangs the import (CPU at 100 %, memory past 1 GB, killed after minutes). Padded to 33 *bytes* it imports and displays correctly. Windows-1252 imports but shows mojibake |

---

## The tournament folder

Vega keeps everything for a tournament in one folder and rewrites a handful
of plain files there whenever the tournament changes. After `Round Manager →
Automatic` for round 3 the folder held, all with the same timestamp:

| File | Written when | What it carries | Read by Rochade |
|---|---|---|---|
| `SortedPairs.txt` | every pairing, every manual change | the boards of the round just paired, by name, both sides listed | **yes** |
| `crosstable.txt` | every import, pairing and result — **but only once a result exists**: a fresh tournament with round 1 paired has none (seen 2026-09-11 evening, `VegaTournaments`) | every player with start number and one cell per round played | yes, in the TRF's place |
| `engine.man` | every *engine* pairing | the engine's raw pairs, `white black` per line, bye as `0` | no — **stale after a manual change** |
| `engine26.trf` | every engine pairing, from round 1 on | the TRF Vega hands the Gacrux plugin, the state *before* the pairing: every player, every result with colour, byes as `U`/`H`, forfeits as `+`/`-`, rounds as `142 N`, birth dates; names squashed (`BaumannLukas`) | **yes** — the players and the history; the boards come from `SortedPairs.txt` |
| `pairingsN.qtf`, `standings.qtf` | every pairing / result | the same in U++ rich text, for printing | no |
| `www<name>/<name>N.pgn` | every pairing | a PGN skeleton per board, `[Round "3.1"]` | no |
| `standings.txt` | every result | Vega's own standings with its tie-breaks, a legend naming the columns, shared positions on ties (`standings_round3.txt`) | **yes**, on the Standings page (`rochade.vega.standings`) |
| `<name>.vegz`, `<name>-VEGZ-NN.bakz` | save / before a pairing | the tournament, binary | no |

### `SortedPairs.txt`

```
Rochade M0 Spike: Pairing of round 3 sorted by name

==========================================================================================
BYE                   plays with black VS         Gruber, Sarah          in board    5
Baumann, Lukas        plays with white VS         Dubois, Elise          in board    2
Chen, Wei             plays with black VS         Mueller, Tobias        in board    1
...
Mueller, Tobias       plays with white VS         Chen, Wei              in board    1

 Generated by Vega - www.vegachess.com
```

- Every board twice, once per side; the pairing-allocated bye is a game
  against the literal `BYE`. A half-point bye is a player status and the
  player is simply absent, as in Swiss-Manager.
- Names are bare — no title — and match `crosstable.txt` exactly, umlauts
  included (UTF-8).
- The header carries the round number. An unregistered copy prefixes the
  tournament name with `(copy licensed to: unregistered)`.
- **Board numbers are Vega's own.** They matched the FIDE order in every
  observed round, but they are read, not derived: after a manual swap of two
  boards (`Modify Pairing`) this file shows the swap; `engine.man` beside it
  still shows the engine's original pairs (`engine_round3_stale_after_manual.man`).

### `crosstable.txt`

```
Rochade M0 Spike
Rochade - 05/09/2026, 07/09/2026

 Cross Table at round 2

  N NAME                 Rtg   T  Fed  Pts |   1     2
--------------------------------------------------------
  1 Baumann, Lukas       2201  FM SUI  1.5 | +W5   =B2
  4 Mueller, Tobias      2044     SUI  2.0 | +F8   +B9
  5 Fischer, Jonas       1987     GER  0.5 | -B1   =HPB
  9 Jenni, Rafael        1755     SUI  1.0 | +PAB  -W4
 10 Keller, Simon           0     SUI  0.0 |  --    --
```

- "at round N" is the last round with results; the round just paired is not
  in it. Columns are found from the header row.
- A cell is the result from the player's side (`+ = -`), then colour and
  opponent (`W5`), or `F` and opponent for a forfeit — **the colour is
  dropped for forfeits**, so Rochade writes the lower start number as white
  when it has no better source; unplayed games do not count for colour in
  the Dutch rules — or a bye (`PAB` pairing-allocated, `HPB` half point).
  `--` is a round the player was not in. Rating `0` is unrated.
- Mixed line endings: the table is CRLF, the last line LF.

---

## The import

`File → Import tournament in FIDE format - TRF2026`, a U++ file dialog that
takes a typed path. Silent on success.

- **A tournament must be open first** (`File → New Tournament`, with a
  folder). The import then replaces it: players, rounds, results, points.
  The window title and the saved `.vegz` take the file's stem; the `012`
  name is kept inside. The arbiter's name, move rate and tie-breaks come from
  the TRF or reset (tie-breaks reset to Buchholz alone).
- **`XXR` is ignored.** The round count comes from `142 N`; without it the
  tournament has as many rounds as the file and `Automatic` says "The
  Tournament is finished". `to_vega()` writes the line; the count itself is
  the arbiter's answer at the first import, remembered on the section.
- **Bytes, not characters.** `accents_charpad_hangs_vega.trf` (two names with
  `ü` and `É`, the name field 33 characters wide) never returned; the same
  file with the field 33 *bytes* wide (`accents_bytepad_imported.trf`)
  imported and showed `Müller, Tobias` and `Dubois, Élise` correctly, and
  Vega wrote them back UTF-8 in `crosstable.txt` and `SortedPairs.txt`.
  Reproduced twice each way.
- Codes: `+`/`-` arrive as `1F-0F`, `U` as `PAB` (bye value 1), `H` as `HPB`,
  and all of them appear as written in the `engine26.trf` Vega hands its
  engine afterwards (`engine26_after_import.trf`). Points are recomputed from
  the results.
- Importing the seed with `XXR 5` and rounds 1–2 played gave a two-round
  tournament (`Modify Tournament` showed `Rounds: 2`); the same file with
  `142 5` gave five.

---

## The next round

`Round Manager → Automatic` on the imported state paired round 4 as
`4-1 9-3 2-5 6-7`, bye 8, from the results we sent — the same the engine gives
on the same TRF. A late-comer added under `Players → Add Player` ("When you
have done with late-comer please regenerate the pairing number!") became
start number 10, rating 0, and was paired in the re-run; Vega writes his
missed rounds as `0000 - Z` in its own TRF.

### Three engines, one round

Round 3 of the seed, board by board:

| Program | Boards |
|---|---|
| Vega 12.1.8, "Swiss FIDE Dutch 2026 (Gacrux)" | 4-2, 1-3, 7-9, 5-8, bye 6 |
| Rochade's vendored TieBreakServer 1.9.57 (`rochade.gacrux.engine.pair`) | 4-2, 1-3, 7-9, 5-8, bye 6 |
| Swiss-Manager 15.0.0.3 (`tests/fixtures/swiss_manager/pairings_round3_unplayed.txt`) | 4-2, 1-3, 7-9, 5-8, bye 6 |

Identical. Two of the three are the same engine; the third agrees.

---

## Through the product

Once the adapter was written, the same round ran through Rochade itself
(2026-09-11, `spikes/out/api.log`): a Vega tournament created over the API,
`crosstable.txt` + `SortedPairs.txt` imported as round 3 with five declared
rounds, four results set, the round released and exported as `A.trf`
(`142 5` in it), that file imported into Vega 12.1.8 -- which showed the
results on the boards and saved `A.vegz` -- round 4 paired there with
`Automatic`, and the new `SortedPairs.txt` imported into Rochade as round 4:
`4-1 9-3 2-5 6-7`, bye 8, Vega's board numbers.

---

## Odds and ends

- Unregistered Vega is limited to 20 players ("This software CANNOT be used
  in any official chess competition with more than 20 players"); the seed is
  nine, so nothing here depended on the licence. A club needs its own.
- Reopening a saved tournament with a paired, unplayed round shows "Insert
  missing result" once on start-up and then works normally; imports work
  after a reopen.
- Ultimate++ exposes nothing to pywinauto: `vega_gui.py` drives it by
  coordinates and keyboard and reads screenshots. The main window is
  `UPP-CLASS-W`; dialogs are the same class with the title `Vega`.

---

## Consequences for the code

- `interchange/vega.py`: reads the folder files (`formats/vega_text.py`,
  built on `rochade.vega`) — `SortedPairs.txt` for the boards, `engine26.trf`
  or `crosstable.txt` for the players and the history — still reads a TRF
  alone, writes a TRF passed through `rochade.vega.to_vega` (byte-padded
  names, `142 N`). Names from the engine file are matched to the pairing
  list by letters alone and take the list's spelling; an engine file that
  ends more than one round before the list (a manual pairing) is refused
  with a pointer to the cross table. `exports_unplayed_round
  = YES`, `merges_on_import = YES` (a replace, said so in the notes),
  `result_codes_out = {1, =, 0, +, -, U, H, Z}`.
- The export file is named after the section alone (`A.trf`), so Vega keeps
  one tournament name across rounds. The port's `stem` is now the section;
  each adapter decides whether the round goes in the name.
- `ImportRound` / `PreviewImport` take `declared_rounds` for files that carry
  none (the cross table, the pairing list); `engine26.trf` carries it as
  `142 N`, so with that file nobody is asked. The section remembers it and
  the export writes it.
- Board numbers of the imported round come from `SortedPairs.txt`, not from
  the FIDE rule; earlier rounds (first import mid-tournament) are numbered
  by the rule, as for every adapter.
