# Running a round with Vega

Two files in, one file out, per round. Everything else is what you do already.

Verified against Vega 12.1.8 (English UI). Menu names are given as they
appear there. What was watched, and what was not, is in `docs/m0-vega.md`.

## Once, before the tournament

- Create the tournament in Vega as always (`File → New Tournament`), with a
  **tournament folder** — Vega writes the files Rochade reads into it, so
  know where it is. Register the players and close the registration.
- In Rochade: **New tournament**, choose **Vega** as the program that pairs it
  (fixed for the tournament: every import and export from then on is Vega's),
  then **Devices → Issue a QR code**. Open it as a poster and print it, or show
  it on the arbiter's screen. One code admits any number of phones for as long
  as the tournament runs; revoke it at any time.

### If a phone cannot scan

Under **Devices**, **Open joining with a code** shows six characters you can
read out. It grants what the QR grants, so read it out in the hall, not in a
group chat.

## Every round

### 1. Pair the round in Vega — as always

`Round Manager → Automatic` (or `Manual`, or `Modify Pairing` afterwards:
Rochade reads the boards as they stand, not as the engine first proposed
them).

### 2. Hand the round to Rochade — two files from the tournament folder

Vega has already written them; there is nothing to export:

1. **`engine26.trf`** — the players with their start numbers, every result
   so far and the number of rounds. Vega writes it each time its engine
   pairs, from round 1 on.
2. **`SortedPairs.txt`** — the boards of the round you just paired.

In Rochade the section card says **Import round N** — press it, drop **both**
files on the page, **Preview the changes**, read what they change, **Import**.

**From round 2 on, `SortedPairs.txt` alone is enough**: Rochade names the
boards from the players it already holds. Add `engine26.trf` again when a
player was added or removed; Rochade tells you if the list names somebody it
does not know.

`crosstable.txt` does the same job as `engine26.trf` and Rochade takes it
too — but Vega only starts writing it once a result has been entered, so it
cannot start a tournament. If you paired a round **by hand** (`Manual`) the
engine did not run and `engine26.trf` is still the previous round's; hand
over `crosstable.txt` then, or `SortedPairs.txt` alone if Rochade already
holds the players. Rochade refuses an engine file that is behind, and says
so. If you hand over a cross table or a pairing list without the engine
file, Rochade asks **how many rounds** the tournament has, once; the section
remembers it.

> **Not `Rating Report → FIDE`.** It refuses to write anything while a paired
> round has no results — which is exactly when you need it — with "In round N
> table 1 there is an unfinished game". The folder files are the way. Rochade
> still *reads* a TRF if you have one.

### 3. Play

Players enter results on their phones; the round board updates every few
seconds and opens on **Attention** — the boards with no result and the ones
two phones disagree about. A no-show is yours: `more…` on the board, then
`+:−`, `−:+` or `−:−`. With a board focused, `1` `=` `0` on the keyboard set
it too. **Entered → Confirm all N** confirms checked results without
releasing the round.

### 4. Release and export

When Attention is empty the bar at the bottom says **Release round N**; press
it. Then **Export for Vega**: a file `<section>.trf` downloads — the same name
every round, on purpose — and the round is frozen: from now on Vega owns it.
The green card at the top of the round tells you what to do in Vega and has
the file again should the download have gone astray.

### 5. Import the results into Vega

`File → Import tournament in FIDE format - TRF2026` → choose the downloaded
file. Nothing is shown on success: the boards of the round show the results,
forfeits as `1F-0F`, the bye as `1`.

Two things to know about this import:

- **Vega replaces the open tournament with the file** and names the
  tournament after the file. Since Rochade names the file after the section,
  the tournament is called `A` from the first import on and saved as
  `A.vegz` in the same folder, next to the one you created; the earlier
  `.vegz` and Vega's own `.bakz` backups stay where they are.
- **Tie-breaks other than Buchholz are reset.** If Vega's own standings are
  what you print, set them again under `File → Tournament manager → Modify
  Tournament → Tie Breaks` after the first import. The play system, the
  round count and the dates survive.

Then pair the next round — back to step 1.

### 6. Standings

Vega computes them; Rochade shows them. Vega rewrites `standings.txt` in the
tournament folder at every result, tie-breaks included. On Rochade's
**Standings** page, drop that file: points, tie-breaks and ranks are taken
as Vega printed them, matched on the start number, and the tie-break columns
carry Vega's names. The hall app shows the same table. Do it after the
results of a round went back to Vega, or after the last round.

## Things to know

- **Names must match.** Rochade joins the two files by name; both come from
  the same Vega tournament, so they do. Accented names are fine: Rochade
  writes the file back the way Vega reads it (Vega counts bytes, and a file
  padded any other way hangs it).
- **If you re-pair a round after handing it over** (a late-comer, a
  correction), hand `SortedPairs.txt` over again **before** sending results
  back; Rochade's preview shows which boards moved and which entered
  results would be dropped, and applies nothing until you accept it. A
  late-comer needs `engine26.trf` too.
- A half-point bye or a withdrawal is set in Vega before pairing, as always;
  the player is simply not on the list. Rochade shows the bye and writes it
  back as it came.
- Vega's forfeit cells in `crosstable.txt` (`+F8`) do not say who had
  white; `engine26.trf` does. For rounds Rochade ran itself that is known
  anyway; for history read from the cross table the lower start number is
  written as white, which the pairing rules never look at for an unplayed
  game.
- An unregistered Vega is limited to 20 players; the club's own licence
  applies as usual.
