"""The Swiss-Manager pairing file ("Spielerauslosung (Text-File)").

This is the file that closes the loop with Swiss-Manager. Its TRF16 export tells
us the pairings; this file, imported through `Extras -> Daten Import/Export ->
Spielerauslosung`, hands the results back **into the tournament the arbiter
already has open** -- which the TRF16 import does not do (it creates a new one).

One row per board, semicolon-separated, CRLF, German decimal comma::

    Runde;Brett;IdentW;IdentS;NrW;NrS;ErgW;ErgS;Kontumaz;Erg;Mnr;ErgEloW;ErgEloS
    3;1;0;0;4;2;1;0;;1:0;0;;
    3;2;0;0;1;3;0,5;0,5;;0,5:0,5;0;;
    3;4;0;0;5;8;1;0;K;1:0K;0;;
    3;5;0;0;6;-1;0;0;;0:0;0;;

`NrW`/`NrS` are the start numbers -- the same numbers TRF calls the starting
rank, which is how the two files join. `Brett` is Swiss-Manager's own board
number. `Kontumaz` = `K` marks a forfeit and is repeated at the end of `Erg`.
A bye is a row with `NrS = -1`; Swiss-Manager scores it by its own tournament
setting whatever the row says, so the row is written back unchanged. An
unplayed board is `0;0;;0:0`.

Results cross this module as TRF codes, one per side, because that is the one
vocabulary every adapter shares. The mapping is total in the direction that
matters -- every code Swiss-Manager can take has exactly one spelling -- and
partial in the other: byes other than the pairing-allocated one do not appear in
this file at all, and unrated results have no spelling, so they are refused
rather than guessed.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

HEADER = "Runde;Brett;IdentW;IdentS;NrW;NrS;ErgW;ErgS;Kontumaz;Erg;Mnr;ErgEloW;ErgEloS"
CRLF = "\r\n"
BYE = -1

#: (white, black) TRF codes -> (ErgW, ErgS, Kontumaz). `Erg` is derived.
_ENCODE: dict[tuple[str, str], tuple[str, str, str]] = {
    (" ", " "): ("0", "0", ""),
    ("1", "0"): ("1", "0", ""),
    ("0", "1"): ("0", "1", ""),
    ("=", "="): ("0,5", "0,5", ""),
    ("+", "-"): ("1", "0", "K"),
    ("-", "+"): ("0", "1", "K"),
    ("-", "-"): ("0", "0", "K"),
}
_DECODE: dict[tuple[str, str, str], tuple[str, str]] = {v: k for k, v in _ENCODE.items()}

#: White-side codes this file can carry for a played board. The adapter reports
#: these as its `result_codes_out`.
WRITABLE_CODES: frozenset[str] = frozenset(w for (w, _b) in _ENCODE if w.strip())


class PairingFileError(ValueError):
    def __init__(self, message: str, *, line_no: int | None = None) -> None:
        super().__init__(message)
        self.line_no = line_no


@dataclass(frozen=True, slots=True)
class PairingLine:
    round_no: int
    board: int
    white: int
    #: None for a bye. Swiss-Manager writes -1.
    black: int | None
    white_result: str = " "
    black_result: str = " "
    #: FIDE ids as Swiss-Manager writes them; "0" when the player has none.
    white_id: str = "0"
    black_id: str = "0"

    @property
    def is_bye(self) -> bool:
        return self.black is None


def render_pairing_file(lines: Sequence[PairingLine]) -> str:
    out = [HEADER]
    for line in lines:
        out.append(_render(line))
    return CRLF.join(out) + CRLF


def _render(line: PairingLine) -> str:
    if line.is_bye:
        # Whatever we hold for the bye, Swiss-Manager decides what it is worth.
        # Writing the row back as it exported it is what keeps that true.
        erg_w, erg_s, kontumaz = "0", "0", ""
    else:
        try:
            erg_w, erg_s, kontumaz = _ENCODE[(line.white_result, line.black_result)]
        except KeyError:
            raise PairingFileError(
                f"board {line.board}: Swiss-Manager's pairing file cannot express "
                f"the result {line.white_result!r}/{line.black_result!r}"
            ) from None
    return ";".join(
        [
            str(line.round_no),
            str(line.board),
            line.white_id or "0",
            (line.black_id or "0") if not line.is_bye else "0",
            str(line.white),
            str(BYE if line.black is None else line.black),
            erg_w,
            erg_s,
            kontumaz,
            f"{erg_w}:{erg_s}{kontumaz}",
            "0",
            "",
            "",
        ]
    )


def parse_pairing_file(text: str) -> list[PairingLine]:
    """Read a pairing file Swiss-Manager wrote.

    Not needed to close the loop -- TRF16 is the inbound leg -- but it is how
    the tests prove `render` against real files, and it is the cheap way to read
    Swiss-Manager's own board numbers should anyone ever need them.
    """
    rows = text.replace("\r\n", "\n").split("\n")
    if not rows or rows[0].strip() != HEADER:
        raise PairingFileError("not a Swiss-Manager pairing file: header does not match", line_no=1)

    lines: list[PairingLine] = []
    for line_no, raw in enumerate(rows[1:], start=2):
        if not raw.strip():
            continue
        cells = raw.split(";")
        if len(cells) < 10:
            raise PairingFileError(
                f"expected at least 10 fields, got {len(cells)}", line_no=line_no
            )
        try:
            round_no, board = int(cells[0]), int(cells[1])
            white, black = int(cells[4]), int(cells[5])
        except ValueError as exc:
            raise PairingFileError(f"unreadable number: {exc}", line_no=line_no) from None

        if black == BYE:
            white_result, black_result = " ", " "
        else:
            key = (cells[6], cells[7], cells[8].strip().upper())
            try:
                white_result, black_result = _DECODE[key]
            except KeyError:
                # Swiss-Manager rewrites a scored bye as 1;1 -- byes are caught
                # above -- so anything left here is a result we do not know.
                raise PairingFileError(
                    f"unknown result {cells[9]!r} on board {board}", line_no=line_no
                ) from None

        lines.append(
            PairingLine(
                round_no=round_no,
                board=board,
                white=white,
                black=None if black == BYE else black,
                white_result=white_result,
                black_result=black_result,
                white_id=cells[2] or "0",
                black_id=cells[3] or "0",
            )
        )
    return lines
