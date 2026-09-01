# M0 findings — Swiss-Manager

Observed facts only. Anything not written down here is still an assumption.

**Swiss-Manager 15.0.0.3 (06.05.2026), German UI, Windows 11.** Run on
2026-09-02 against the synthetic nine-player tournament in `make_seed.py`.
The files it produced are checked in under `tests/fixtures/swiss_manager/`.

---

## The verdict

**The loop closes, with two file operations per round, and the arbiter stays
in the tournament they already have open.**

| Leg | Menu | Format | Verdict |
|---|---|---|---|
| manager → us | `Extras → FIDE-Daten-Export TRF16` | TRF16 | exports the paired-but-unplayed round; every code intact |
| us → manager | `Extras → Daten Import/Export → Import Spielerauslosung` | Swiss-Manager pairing file (`;`-separated text) | **merges into the open tournament**; forfeits and double forfeits intact; the next round pairs |

The obvious candidate for the inbound leg — `Datei → FIDE-Datenformat
importieren TRF16` — is the wrong tool. It **creates a new tournament** from
the file every time (named after the file, `Bemerkung: Automatischer Import aus
der FIDE-Text-Datei für die Elowertung`), re-derives the round count from the
rounds present, infers the bye value from the points column, and drops whatever
the arbiter configured that TRF does not carry. It is a rating-office feature
for rebuilding a tournament, not a way to continue one.

| # | Check | Result |
|---|---|---|
| 1 | Exports a paired-but-unplayed round | **YES** — `Rundenauswahl` defaults to `1 bis N` including the paired round; a `Es fehlen noch Ergebnisse. Liste trotzdem ausgeben?` prompt wants `Ja` |
| 2 | We identify players, boards, colours, prior results | **YES** — and board numbers match Swiss-Manager's pairing list when derived by the FIDE rule (below) |
| 3 | Results merge back and the next round pairs | **YES via the pairing file**; **NO via TRF16 import** |
| 4 | Round trip lossless for untouched fields | **PASS** on all three real exports (`inspect_export.py`) |
| 5 | A re-pair is detectable | not run against the GUI; `compare_exports.py` is format-neutral and exercised on fixtures |
| 6 | `+ - H U Z` survive | `+ -` both ways, `U` and `H` inbound. Outbound byes are not ours to write (below) |
| 7 | Column drift | **none** — the export lines up with the TRF16 ruler exactly; UTF-8, padded by character |

---

## The pairing file

`Extras → Daten Import/Export`, `Spielerauslosung (Text-File)`, round range,
`Starten`, save dialog. Import is the mirror: `Spielerauslosung`, `Starten`,
open dialog. Both are silent on success.

```
Runde;Brett;IdentW;IdentS;NrW;NrS;ErgW;ErgS;Kontumaz;Erg;Mnr;ErgEloW;ErgEloS
3;1;0;0;4;2;1;0;;1:0;0;;
3;2;0;0;1;3;0,5;0,5;;0,5:0,5;0;;
3;3;0;0;7;9;0;1;;0:1;0;;
3;4;0;0;5;8;1;0;K;1:0K;0;;
3;5;0;0;6;-1;1;1;;1:1;0;;
```

- `Brett` is **Swiss-Manager's own board number**. `NrW`/`NrS` are start
  numbers — the same numbers as TRF's start rank, so the two files join on them.
- `ErgW;ErgS` are the points with a **German decimal comma**; `Erg` repeats
  them as `W:S`. `Kontumaz` = `K` marks a forfeit and is appended to `Erg` too:
  `1:0K`, `0:1K`, and `0:0K` for a double forfeit. All three imported correctly
  and display as `+ - -`, `- - +`, `- - -`.
- An unplayed board is `0;0;;0:0`.
- A pairing-allocated bye is a row with `NrS = -1`. Before the round is
  complete it reads `0;0;;0:0`; afterwards Swiss-Manager rewrites it as
  `1;1;;1:1`. **Leaving the bye row out of the import left the bye unscored;
  sending it back unchanged (`0:0`) scored it correctly** — Swiss-Manager
  applies its own bye value regardless of what the row says. So: write back
  every row of the round, change only the played results.
- A half-point bye (`H`) does not appear in the file at all. It is a player
  status, not a pairing.
- `IdentW`/`IdentS` were `0` throughout because the seed has no FIDE ids.
  Whether the importer checks them against the player is **unverified**.
- Import was run twice on round 4 with the same file; the second run changed
  nothing. Re-import is idempotent.

---

## The TRF16 export

- Written **silently** to `Documents\SwissManagerUniCode\Listen\FIDE_Export_<tournament>.TXT`
  — no save dialog. `FIDE_Export_Logfile.TXT` beside it was empty on every run.
- **Refuses without round dates**: `Fehler (Message:42) Für elogewertete
  Turniere müssen die Termine der einzelnen Runden eingegeben werden.` Fix is
  `Eingabe → Termine für die einzelnen Runden... → Übernehmen → OK`. A real
  tournament has these set; the seed did not.
- `Hinweis (Message:189)`: players without FIDE id make the tournament
  unratable. Informational; the export proceeds. **TRF16 does not need FIDE
  identities** — the seed had none and the whole loop ran.
- Header is Swiss-Manager's dialect: no `XXR`; the round count is **`142 N`**
  (5 → `142 5`, 2 → `142 2`). `132` carries round dates in `YY/MM/DD`. `062 9 (9)`.
  It also writes a column ruler into the file (a blank line, two digit rows, a
  `DDD SSSS sTTT NNN…` row). Our parser keeps all of it verbatim and check 4
  proves it goes back byte-identical.
- Sex is `m`/`f` (we wrote `w`; it came back `f`). Names come back as
  `Surname,Given` — no space after the comma.
- **Titles were blank in every export** even though FM/WFM show in the GUI.
  Presumably `Spielernamen und Titeln aus FIDE-Liste nehmen` (checked by
  default) and no FIDE list entry. Cosmetic for us.
- **Names are transliterated for the tournament's own federation.** The
  `Rundenauswahl` dialog has `Spezielle Sonderzeichenkonvertierung für Land SUI`;
  `Müller` (SUI) came out `Mueller`, `Élise` (FRA) stayed `Élise`. Hall app
  shows what the file says. Consistent between exports, so matching by name
  across imports still works. Clearing that field should switch it off — unverified.
- The points column **excludes the open round entirely**: a player holding a
  pairing-allocated bye in the unplayed round shows their pre-round total. Swiss-
  Manager credits the bye when the round completes. Irrelevant now that we do
  not write TRF back to Swiss-Manager; it would have mattered a great deal if we did.
- A pairing-allocated bye in the unplayed round is already written as `0000 - U`.

### Board numbers

TRF has no board numbers. Swiss-Manager's, read off its pairing list and its
pairing file across rounds 1, 3 and 4, are the FIDE order:

1. higher score of the two players, descending
2. sum of the two scores, descending
3. start rank of the higher-ranked player, ascending
4. byes last, unnumbered

Scores are the points column, i.e. before the round. Deriving boards this way
reproduced Swiss-Manager's numbers on every board of every round we looked at.

---

## Earlier, still true

- The TRF import ignores `XXR` (and `142`) and derives the round count from
  content. Only matters when a tournament is *created* from a TRF, which no
  arbiter does in the real workflow — they set it up natively.
- A pairing-allocated bye is worth `Pkt. für spielfreien Spieler`, a
  per-tournament setting; 1 by default. The import inferred 0 for the
  snapshot re-import because the points column said so.
- `Listen → Ergebnisse` (F9) shows one round at a time; `Rd` selects.

---

## Consequences for the code

- New adapter `interchange/swiss_manager.py`: reads TRF16 through the shared
  library, writes the pairing file. `exports_unplayed_round = YES`,
  `merges_on_import = YES`, `result_codes_out = {1, =, 0, +, -}`.
- New format module for the pairing file, pure, beside `trf/`.
- Board numbering in `RoundDocument.board_rows()` becomes the FIDE order for
  every adapter; the current "white players by start rank" was wrong.
- `declared_rounds` should read `142` when `XXR` is absent.
- The Vega adapter stays as it is and stays `UNVERIFIED`. Nothing here was
  observed against Vega.
