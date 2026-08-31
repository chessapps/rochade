"""Serialize a TrfFile back to text.

The player line is *patched*, never rebuilt: we overwrite exactly the character
cells we own (opponent, colour, result, and points when asked) and leave every
other byte of the original line untouched. That is what makes round-trip
identity achievable for input we did not modify.
"""

from __future__ import annotations

from seebach.trf import columns
from seebach.trf.dialect import Dialect
from seebach.trf.model import Player, TrfFile
from seebach.trf.results import points_for


def serialize(trf: TrfFile, dialect: Dialect, *, recompute_points: bool = False) -> str:
    """Render the document. `dialect` is required -- never serialize "TRF" generically."""
    rendered = [
        _render_player(trf.players[_rank_of(line.raw)], recompute_points=recompute_points)
        if line.code == "001"
        else line.raw
        for line in trf.lines
    ]
    if dialect is Dialect.TRF06:
        rendered = [_to_trf06(line) for line in rendered]
    text = trf.newline.join(rendered)
    if trf.trailing_newline:
        text += trf.newline
    return text


def to_bytes(trf: TrfFile, dialect: Dialect, *, recompute_points: bool = False) -> bytes:
    text = serialize(trf, dialect, recompute_points=recompute_points)
    return text.encode(dialect.encoding, errors="replace")


def _to_trf06(line: str) -> str:
    """Replace characters cp1252 cannot carry, one for one.

    Substitution is deliberately width-preserving: TRF is a fixed-column format,
    so a transliteration that changed the length would shift every field after
    the name.
    """
    encoding = Dialect.TRF06.encoding
    return "".join(c if _encodable(c, encoding) else "?" for c in line)


def _encodable(char: str, encoding: str) -> bool:
    try:
        char.encode(encoding)
    except UnicodeEncodeError:
        return False
    return True


def _rank_of(raw: str) -> int:
    return int(raw[columns.START_RANK])


def _render_player(player: Player, *, recompute_points: bool) -> str:
    cells = list(player.raw)

    for round_no, entry in sorted(player.rounds.items()):
        opponent = f"{entry.opponent:4d}" if entry.opponent is not None else "0000"
        _patch(cells, columns.opponent_slice(round_no), opponent)
        _patch_char(cells, columns.colour_index(round_no), entry.colour.value)
        _patch_char(cells, columns.result_index(round_no), entry.result)

    if recompute_points:
        total = sum(points_for(e.result) for e in player.rounds.values())
        _patch(cells, columns.POINTS, f"{total:4.1f}")

    rendered = "".join(cells)
    # Real files trim trailing blanks, so a pending result can sit past the end
    # of the line. Padding it back out with spaces would be a byte difference
    # for a line we did not actually change, so give the padding back.
    if len(rendered) > len(player.raw) and not rendered[len(player.raw) :].strip():
        rendered = rendered[: len(player.raw)]
    return rendered


def _patch(cells: list[str], span: slice, value: str) -> None:
    _grow(cells, span.stop)
    width = span.stop - span.start
    text = value.rjust(width)[:width]
    cells[span] = list(text)


def _patch_char(cells: list[str], index: int, value: str) -> None:
    _grow(cells, index + 1)
    cells[index] = value


def _grow(cells: list[str], length: int) -> None:
    if len(cells) < length:
        cells.extend(" " * (length - len(cells)))
