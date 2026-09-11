# The Gacrux engine, as observed

What the vendored TieBreakServer actually does when Rochade drives it, the way
`docs/m0-swiss-manager.md` records Swiss-Manager. Everything here was run on
2026-09-10 against version 1.9.57 (commit `14a34a2c`) with Python 3.12 on
Windows, and again in CI on Linux through `tests/gacrux/`. Re-run
`uv run python spikes/gacrux_probe.py` after a refresh and update this file
with anything that moved.

## Driving it

- Two scripts matter: `pairingchecker.py` and `tiebreakchecker.py`. Both take
  `-i <file> -o <file> -f TRF -b utf-8`. Both **exit 0 whatever happened** and
  put the verdict in `status.code` of the JSON they write; the error text is
  in `status.error`, a list. Nothing goes to stderr. `rochade.gacrux.engine`
  therefore reads the file and trusts only the status.
- Imports inside upstream are by bare module name, so the scripts run with the
  vendored directory as the working directory. In process would need
  `sys.path` games; a child process needs nothing.
- Runtime is flat: about half a second per call for 9, 100 and 201 players
  alike, seven rounds deep, tie-breaks included. The 15-second timeout in
  `Settings.gacrux_timeout` only exists to catch a hang; at most two engine
  processes run at once, server-wide, so a burst of previews cannot crowd
  out the hall's claims.
- The child gets a minimal environment and Python's `-E -s -B -X utf8`
  flags: nothing on the server's `PYTHONPATH` or in a user site directory
  can shadow the vendored modules, and no `.pyc` lands in the package. The
  engine's own error lines are returned to the arbiter with our scratch-file
  paths blanked; a timeout, crash or missing install is a 503, never a 422.
- Everything the arbiter types is validated to the TRF column grammar before
  it reaches a line (`features/players/add_player.py`), and the builder
  strips line breaks and control characters from every value regardless: a
  name with a newline in it would otherwise start a record of its own.

## Pairing

`pairingchecker.py -n <round> -p -m dutch [-t w|b] [-u <rank> <rank> ...]`

- Output: `pairingResult` is an object (the docstring in upstream says array;
  it is not): `{"rules": "2026-02-01", "round": N, "pairs": [[white, black], ...]}`.
  Ids are TRF starting ranks. **The bye is `[white, 0]`**, listed last.
- `-n` names the round to pair. Without it the engine pairs `currentRound + 1`,
  where `currentRound` is the last round with a *played* game, so an unplayed
  round already in the file is ignored and paired afresh. Rochade always
  passes `-n` and checks the round number that comes back.
- Pairing past `XXR` is refused with status 504 (`Number of rounds = 2,
  can't pair round 3`). A damaged `001` line is status 502 with the line
  number. A missing input file is 502 too.
- Top colour: `-t w` and `-t b` decide round 1 and flip every board. From
  round 2 on the engine reads the colour off round 1's first board and `-t`
  is ignored, so it must be given for round 1 and is harmless afterwards.
  Without `-t` in round 1 the engine draws lots.
- Absence: a player whose block for the round being paired is `0000 - Z` is
  left out; so is anyone named in `-u`. `-u` takes starting ranks separated by
  spaces. A player with `H` for the round is likewise left out, and the
  half point is theirs in the tie-breaks.
- Round 1 of `tests/fixtures/round1_pairings.trf` (eight players, blocks
  present but unplayed) comes back as the fixture's own boards, (1,5) (6,2)
  (3,7) (8,4), and so does the same roster with the blocks stripped.
- A field of one player pairs as `[[1, 0]]`, a bye, without complaint. The
  application refuses that before the engine sees it.
- What the TRF needs: `001` lines and `XXR`. `XXC` is read as a no-op
  (upstream: "not really important"); `152 W|B` would set a fixed top colour
  for every round, which is not what `-t` means, so Rochade does not write it.
  The points column is read but the score is recomputed from the round
  blocks; `062` is ignored.

## Tie-breaks

`tiebreakchecker.py -s -n <after round> -t PTS BH/C1 BH SB`

- Output: `tiebreakResult.competitors[]` of `{"cid", "rank", "tiebreakScore":
  ["2.0", "1.0", ...]}`. **Scores are strings**, one per spec in the order
  given; `rank` ties are shared (two players on rank 4, none on 5). The
  `tiebreaks[]` list beside it echoes the parsed specs with their modifiers,
  and `round` is the declared round count, not `-n`.
- `-n 2` limits the arithmetic to rounds 1..2. Round 3's unplayed blocks do
  not leak in.
- `-s` selects Swiss rules for unplayed games (Article 16). Rochade always
  passes it; there is no round-robin mode yet.
- A blank round block and a `0000 - Z` block score identically, so a late
  entry's missing rounds can stay blank in the TRF Rochade builds.
- Every code in `rochade.gacrux.tiebreaks.KNOWN_TIEBREAKS` is accepted and
  produces a column; `tests/gacrux/test_tiebreak_codes.py` proves it on
  every run.
- The golden values for the messy seed after two rounds are in
  `tests/fixtures/gacrux/round3_standings_after_2.json`.

## Checked since

- Round 3 of the nine-player seed (`spikes/make_seed.py`), board by board,
  2026-09-11: the vendored engine, Vega 12.1.8 with its bundled Gacrux, and
  Swiss-Manager 15.0.0.3 all pair `4-2 1-3 7-9 5-8`, bye 6
  (`docs/m0-vega.md`). One round of one seed, not a proof; but the three
  agree where they were compared.
