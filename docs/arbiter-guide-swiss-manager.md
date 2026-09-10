# Running a round with Swiss-Manager

Two file operations per round. Everything else is what you do already.

Verified against Swiss-Manager 15.0.0.3 (German UI). Menu names are given as
they appear there.

## Once, before the tournament

- Set the round dates: `Eingabe → Termine für die einzelnen Runden…` →
  `Übernehmen` → `OK`. Swiss-Manager's TRF export refuses without them
  (`Fehler (Message:42)`), and a rated tournament needs them anyway.
- In Rochade: **New tournament**, choose **Swiss-Manager** as the program that
  pairs it (this is fixed for the tournament: every import and export from then
  on is Swiss-Manager's, and nothing asks again), then **Devices → Issue a QR
  code**. Open it
  as a poster and print it, or show it on the arbiter's screen. One code admits
  any number of phones to this tournament for as long as it runs; issue a second one for
  the other end of the hall if you like. Revoke either at any time, and remove it from
  the list once revoked.

### If a phone cannot scan

Under **Devices**, **Open joining with a code** shows six characters you can read
out. A player types them on the hall app's opening screen and is admitted the
same way the QR admits them. Each phone that uses the code gets its own entry in
the device list, so one can be revoked without disturbing the rest, and **Turn
off** closes it once everybody is in.

It grants what the QR grants, so treat it the same way: read it out in the hall,
not in a group chat.

## Every round

### 1. Pair the round in Swiss-Manager — as always

`Auslosen → Auslosungsmenü…` (F6), `Starten`, `OK`.

### 2. Export it for Rochade — two files

`Extras → Daten Import/Export…`, on the **export** side (the left column):

1. **Spielerdaten (Text-File)** → `Starten` → save it, say as `players.txt`.
2. **Spielerauslosung (Text-File)** → set `Runde` to the round you just paired,
   both boxes the same number → `Starten` → save it, say as `round4.txt`.
3. `OK` closes the dialog. Neither export asks anything else and neither says
   anything when it works.

The first file is the entry list, the second is the boards; they mean nothing
apart, so the first round needs both. **From round 2 on, the pairings file alone
is enough**: Rochade names the boards from the players it already holds. Export
Spielerdaten again only when a player was added or removed, and Rochade tells
you if the pairings mention a start number it does not know.

In Rochade the section card says **Import round N** — press it, drop **both**
files on the page, **Preview the changes**, read what the file changes,
**Import**. You land on the round board; the phones show the same board numbers
Swiss-Manager printed on the pairing list.

> **Not `Extras → FIDE-Daten-Export TRF16`.** That was the original route and it
> is out of use: on 15.0.0.3 it crashes with an access violation
> (`Zugriffsverletzung bei Adresse 010ABD84`) for a tournament whose rounds
> Swiss-Manager paired itself, leaving a file with a header and no players.
> Seen 2026-09-07 on a 100-player test tournament, however the tournament was
> created and whether or not the round had results. Rochade still *reads* a TRF
> if you have one.

### 3. Play

Players enter results on their phones; the round board updates every few
seconds. It opens on **Attention** — the boards with no result and the ones two
phones disagree about — so an empty list means the round is done. A disputed
board shows both claims and which phone made each; pick the right one or set it
from the scoresheet. A no-show is yours: `more…` on the board, then `+:−`,
`−:+` or `−:−`. The same menu has the unrated results `W:L` `D:D` `L:W` and,
under **Any pair**, every TRF code for either side. A bye takes `change` and
then its own codes: 1 (allocated or full-point), ½ or 0. With a board
focused, `1` `=` `0` on the keyboard set it too.

As you check entered results against the scoresheets, **Entered → Confirm all
N** confirms them in one go without releasing the round. A confirmed board is
closed to the phones, so a late correction from a player comes to you instead
of overwriting what you checked; `change` on the board still works for you.

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

### 6. Standings

Swiss-Manager's player list carries its Rangliste: points, the tiebreaks in
the order of your tournament settings, and the rank. Whenever you import a
round with both files, the standings after the previous round come along, and
**Standings** in the admin app shows them; players see the same table behind
the **Standings** tab in the hall app. Nothing is computed in Rochade.

After the last round there is no pairing to import: export Spielerdaten once
more and drop it on the Standings page under **Import standings on their own**.
The file numbers the tiebreak columns without naming them; **Name them** once
from your tournament settings and the names stay.

## Things to know

- **Do not use `Datei → FIDE-Datenformat importieren TRF16` to bring results
  back.** It creates a *new* tournament from the file every time, sets the round
  count from what the file holds and guesses the bye value from the points
  column. It is for rebuilding a tournament for the rating office, not for
  continuing yours.
- Names in Rochade appear as Swiss-Manager exports them: `Surname,Given`, and
  transliterated for the tournament's own federation (`Müller` → `Mueller`).
  Players find their board by typing part of their name, so this rarely matters.
- Titles (FM, WFM…) are not in the export. Cosmetic.
- **If you re-pair a round after exporting it** (a late entrant, a correction),
  export again and re-import in Rochade **before** sending results back. The
  results file carries the pairings too, and Swiss-Manager takes them: a file
  built from the old pairings would quietly undo your re-pairing. Rochade's
  preview shows exactly which boards moved and which entered results would be
  dropped; nothing is applied until you accept it.
- A half-point bye or a withdrawal is set in Swiss-Manager before pairing, as
  always. Rochade shows it and never writes it back.
