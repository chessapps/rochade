"""Write results into a parsed TRF.

Each game appears twice in the file, once on each player's row. Setting a
result therefore always sets both sides -- an export that patched only one row
is the classic way to hand a manager a file it half-believes.
"""

from __future__ import annotations

from seebach.trf.model import TrfFile
from seebach.trf.results import UNPLAYED_CODES, is_known, mirror


def set_result(trf: TrfFile, round_no: int, start_rank: int, code: str) -> None:
    """Set `start_rank`'s result in `round_no`, mirroring onto the opponent."""
    if not is_known(code):
        raise ValueError(f"unknown TRF result code {code!r}")

    player = trf.player(start_rank)
    entry = player.rounds.get(round_no)
    if entry is None:
        raise ValueError(f"player {start_rank} has no round {round_no}")

    entry.result = code

    if entry.opponent is None:
        if code not in UNPLAYED_CODES:
            raise ValueError(f"player {start_rank} has a bye in round {round_no}, not a game")
        return

    opponent_entry = trf.player(entry.opponent).rounds.get(round_no)
    if opponent_entry is None:
        raise ValueError(
            f"player {entry.opponent} is listed as opponent but has no round {round_no}"
        )
    opponent_entry.result = mirror(code)


def set_game(trf: TrfFile, round_no: int, white_rank: int, white_code: str) -> None:
    """Set a game by its white player -- the form the export command uses."""
    set_result(trf, round_no, white_rank, white_code)
