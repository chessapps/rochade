# Running a tournament in Rochade itself

The desk pairs the rounds and keeps the table; no files go in or out. What
follows is one round from the arbiter's chair, with the odd cases after it.

## Before round 1

1. **New tournament**, program *Rochade (Gacrux engine)*.
2. **New section…**: a name, the number of rounds, the tie-breaks in order
   (Points first, then by default Buchholz Cut 1, Buchholz, Sonneborn-Berger),
   and who has white on board one in round 1 (or draw lots).
3. **Players**: add them in any order. The first pairing seeds the list by
   rating, then title, then name, and the numbers are final from then on.
   Names must be unique within the section; they are what the boards, the
   phones and the log call the player.

## Every round

1. **Pair round N** on the section card. The preview shows the boards, the
   bye and who is left out; *Pair* writes them. The round is open for entry,
   the phones see it, and the round before is closed for good.
2. Results arrive from the hall. *Attention* lists what needs you; forfeits
   and corrections are set here.
3. **Release round N**. Every entered result is confirmed and the standings
   are computed. A board you correct after the release moves the table again.
4. Back to 1.

After the last declared round the section card says so and points at the
standings.

## The odd cases

- **A pairing to take back.** *Unpair…* in the dock of the round board, as
  long as nobody has entered anything. The round before reopens for
  corrections; pairing again gives the same boards unless the players or
  their absences changed.
- **Someone is not there tonight.** Before pairing, mark them absent for the
  round (half a point or none). They are left out and the bye goes elsewhere.
- **A late entry.** *Players* → *Add player…* after round 1: they take the
  next number, the rounds they missed count as absences, and they are paired
  from the next round.
- **A withdrawal.** *Players* → *Withdraw…*: from the next unpaired round on.
  A board already paired is settled with a result (a forfeit if need be), not
  by removing the player. *Reinstate* brings them back for a round that is not
  paired yet.
- **A forced release.** Boards released empty stay open for you to set here.
  The standings wait, and the next round cannot be paired, until every board
  of the round has a result.
- **A result to correct in a closed round.** Not from the desk once the next
  round has entries on it: unpair the newer round if it is untouched, correct,
  pair again. Otherwise the correction waits for a later version.

## What the engine is

Pairings are the FIDE Dutch system and the table is FIDE C.07 tie-breaks,
both computed by TieBreakServer, the "Gacrux" reference implementation by
IA Otto Milvang (© FIDE, MIT). A copy ships inside Rochade; `docs/gacrux.md`
records how it behaves. Rochade itself is not FIDE-endorsed.
