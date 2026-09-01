"""Write results into a parsed TRF.

Each game appears twice in the file, once on each player's row. Setting a
result therefore always sets both sides -- an export that patched only one row
is the classic way to hand a manager a file it half-believes.
"""

from __future__ import annotations

from seebach.trf.model import Player, TrfFile
from seebach.trf.results import UNPLAYED_CODES, is_known, mirror, points_for


def set_result(trf: TrfFile, round_no: int, start_rank: int, code: str) -> None:
    """Set `start_rank`'s result in `round_no`, mirroring onto the opponent.

    Points move by the *delta* of what we wrote, never by recomputing the whole
    column. Recomputing would assert our reading of every code in the file,
    including the pairing-allocated bye -- and what a PAB is worth is a
    tournament regulation, not a property of the letter `U`. Some events award
    1 point for one, some 0.5. Adding only what we actually scored cannot
    corrupt a number we were never told.
    """
    if not is_known(code):
        raise ValueError(f"unknown TRF result code {code!r}")

    player = trf.player(start_rank)
    entry = player.rounds.get(round_no)
    if entry is None:
        raise ValueError(f"player {start_rank} has no round {round_no}")

    previous = entry.result
    entry.result = code
    _move_points(trf, player, points_for(code) - points_for(previous))

    if entry.opponent is None:
        if code not in UNPLAYED_CODES:
            raise ValueError(f"player {start_rank} has a bye in round {round_no}, not a game")
        return

    opponent = trf.player(entry.opponent)
    opponent_entry = opponent.rounds.get(round_no)
    if opponent_entry is None:
        raise ValueError(
            f"player {entry.opponent} is listed as opponent but has no round {round_no}"
        )
    mirrored = mirror(code)
    was = opponent_entry.result
    opponent_entry.result = mirrored
    _move_points(trf, opponent, points_for(mirrored) - points_for(was))


def _move_points(trf: TrfFile, player: Player, delta: float) -> None:
    """Adjust a player's running score, if the file gave us one to adjust.

    A file with no points column is left alone: we would be inventing a total
    rather than correcting one, and the manager recomputes on import anyway.
    """
    if delta == 0 or player.points is None:
        return
    player.points += delta
    trf.points_changed.add(player.start_rank)


def set_game(trf: TrfFile, round_no: int, white_rank: int, white_code: str) -> None:
    """Set a game by its white player -- the form the export command uses."""
    set_result(trf, round_no, white_rank, white_code)
