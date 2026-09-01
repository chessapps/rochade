# Running a round with Swiss-Manager

Two file operations per round. Everything else is what you do already.

Verified against Swiss-Manager 15.0.0.3 (German UI). Menu names are given as
they appear there.

## Once, before the tournament

- Set the round dates: `Eingabe → Termine für die einzelnen Runden…` →
  `Übernehmen` → `OK`. Swiss-Manager's TRF export refuses without them
  (`Fehler (Message:42)`), and a rated tournament needs them anyway.
- In Seebach, create the tournament and issue the hall QR codes as usual.

## Every round

### 1. Pair the round in Swiss-Manager — as always

`Auslosen → Auslosungsmenü…` (F6), `Starten`, `OK`.

### 2. Export it for Seebach

`Extras → FIDE-Daten-Export TRF16`

- If it says players without a FIDE ID make the tournament unratable, `ok` — it
  is a hint, and Seebach does not need FIDE IDs.
- `Rundenauswahl`: the defaults already include the round you just paired. `OK`.
- `Es fehlen noch Ergebnisse. Liste trotzdem ausgeben?` → **`Ja`**. Those
  missing results are the round about to be played; that is the point.

There is no save dialog. The file is written to

```
Documents\SwissManagerUniCode\Listen\FIDE_Export_<tournament>.TXT
```

In Seebach: **Import the paired round** → pick `Swiss-Manager`, choose that file,
`Preview`, read the diff, `Import`. The boards appear in the hall app with the
same board numbers Swiss-Manager printed on the pairing list.

### 3. Play

Players enter results on their phones. Forfeits and byes are yours: set them in
Seebach's queue (`+`/`-` for a no-show, `-`/`-` if nobody came).

### 4. Release and export

When the queue is clear, `Release`, then `Export for Swiss-Manager`. A file
`<section>-round<N>.txt` downloads and the round is frozen — from now on
Swiss-Manager owns it.

### 5. Import the results into Swiss-Manager

`Extras → Daten Import/Export…` → under **Importart** choose `Spielerauslosung`
→ `Starten` → pick the downloaded file → `OK`.

Nothing is shown on success. Check `Listen → Ergebnisse` (F9): the results are
there, forfeits as `+ - -`, the bye scored by your tournament's setting. Then
pair the next round — back to step 1.

## Things to know

- **Do not use `Datei → FIDE-Datenformat importieren TRF16` to bring results
  back.** It creates a *new* tournament from the file every time, sets the round
  count from what the file holds and guesses the bye value from the points
  column. It is for rebuilding a tournament for the rating office, not for
  continuing yours.
- Names in Seebach appear as Swiss-Manager exports them: `Surname,Given`, and
  transliterated for the tournament's own federation (`Müller` → `Mueller`).
  Players find their board by typing part of their name, so this rarely matters.
- Titles (FM, WFM…) are not in the export. Cosmetic.
- If you re-pair a round after exporting it (a late entrant), export again and
  re-import in Seebach. The preview shows exactly which boards moved and which
  entered results would be dropped; nothing is applied until you accept it.
- A half-point bye or a withdrawal is set in Swiss-Manager before pairing, as
  always. Seebach shows it and never writes it back.
