# Running a round with Swiss-Manager

Two file operations per round. Everything else is what you do already.

Verified against Swiss-Manager 15.0.0.3 (German UI). Menu names are given as
they appear there.

## Once, before the tournament

- Set the round dates: `Eingabe → Termine für die einzelnen Runden…` →
  `Übernehmen` → `OK`. Swiss-Manager's TRF export refuses without them
  (`Fehler (Message:42)`), and a rated tournament needs them anyway.
- In Seebach: **New tournament**, then **Devices → Issue a QR code**. Open it
  as a poster and print it, or show it on the arbiter's screen. One code admits
  any number of phones to this tournament for the day; issue a second one for
  the other end of the hall if you like, and revoke either at any time.

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

In Seebach the section card says **Import round N** — press it, drop that file
on the page, **Preview the changes**, read what the file changes, **Import**.
You land on the round board; the phones show the same board numbers
Swiss-Manager printed on the pairing list.

### 3. Play

Players enter results on their phones; the round board updates every few
seconds. It opens on **Attention** — the boards with no result and the ones two
phones disagree about — so an empty list means the round is done. A disputed
board shows both claims and which phone made each; pick the right one or set it
from the scoresheet. A no-show is yours: `forfeit…` on the board, then `+:−`,
`−:+` or `−:−`. With a board focused, `1` `=` `0` on the keyboard set it too.

### 4. Release and export

When Attention is empty the bar at the bottom says **Release round N**; press
it. Then **Export for Swiss-Manager**: a file `<section>-round<N>.txt` downloads
and the round is frozen — from now on Swiss-Manager owns it. The green card at
the top of the round tells you what to do in Swiss-Manager and has the file
again should the download have gone astray; **Import round N+1** is on it too.

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
- **If you re-pair a round after exporting it** (a late entrant, a correction),
  export again and re-import in Seebach **before** sending results back. The
  results file carries the pairings too, and Swiss-Manager takes them: a file
  built from the old pairings would quietly undo your re-pairing. Seebach's
  preview shows exactly which boards moved and which entered results would be
  dropped; nothing is applied until you accept it.
- A half-point bye or a withdrawal is set in Swiss-Manager before pairing, as
  always. Seebach shows it and never writes it back.
