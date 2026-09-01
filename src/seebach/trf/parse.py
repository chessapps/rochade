"""Parse a TRF document.

Tolerant by design. Unknown record types, unknown result codes and short lines
are all survivable -- they are retained and reported, not rejected. Only
structural damage to a `001` line (an unreadable starting rank) is fatal,
because without it there is no way to talk about the player at all.
"""

from __future__ import annotations

from seebach.trf import columns
from seebach.trf.errors import TrfParseError
from seebach.trf.model import Colour, Player, RoundEntry, TrfFile, TrfLine
from seebach.trf.results import is_known

PLAYER_CODE = "001"

_HEADERS = {
    "012": "name",
    "022": "city",
    "032": "federation",
    "042": "start_date",
    "052": "end_date",
    "102": "chief_arbiter",
}


def parse(text: str | bytes, *, encoding: str = "utf-8") -> TrfFile:
    if isinstance(text, bytes):
        text = _decode(text, encoding)

    newline = "\r\n" if "\r\n" in text else "\n"
    trailing_newline = text.endswith(("\n", "\r"))
    body = text[: -len(newline)] if trailing_newline and text.endswith(newline) else text
    if trailing_newline and not text.endswith(newline):
        body = text.rstrip("\r\n")

    raw_lines = body.split(newline) if body else []

    trf = TrfFile(lines=[], players={}, newline=newline, trailing_newline=trailing_newline)
    unknown_codes: set[str] = set()

    for i, raw in enumerate(raw_lines, start=1):
        line = TrfLine(line_no=i, raw=raw)
        trf.lines.append(line)
        code = line.code

        if code == PLAYER_CODE:
            player = _parse_player(raw, line_no=i, unknown_codes=unknown_codes)
            if player.start_rank in trf.players:
                raise TrfParseError(
                    f"duplicate starting rank {player.start_rank}", line_no=i, line=raw
                )
            trf.players[player.start_rank] = player
        elif code in _HEADERS:
            setattr(trf, _HEADERS[code], raw[4:].strip())
        elif code == "XXR":
            trf.declared_rounds = _optional_int(raw[4:])
        elif code == "142" and trf.declared_rounds is None:
            # Swiss-Manager's dialect: no XXR, the round count travels as 142.
            # XXR wins if both are present, since that is what pairing engines read.
            trf.declared_rounds = _optional_int(raw[4:])

    trf.unknown_result_codes = sorted(unknown_codes)
    return trf


def _decode(data: bytes, encoding: str) -> str:
    try:
        return data.decode(encoding)
    except UnicodeDecodeError:
        # TRF06 files in the wild are latin-1 family; never fail the whole import
        # over one accented surname.
        return data.decode("cp1252", errors="replace")


def _parse_player(raw: str, *, line_no: int, unknown_codes: set[str]) -> Player:
    start_rank = _optional_int(_field(raw, columns.START_RANK))
    if start_rank is None:
        raise TrfParseError("player line has no starting rank", line_no=line_no, line=raw)

    return Player(
        start_rank=start_rank,
        name=_field(raw, columns.NAME).strip(),
        sex=_field(raw, columns.SEX).strip(),
        title=_field(raw, columns.TITLE).strip(),
        rating=_optional_int(_field(raw, columns.RATING)),
        federation=_field(raw, columns.FEDERATION).strip(),
        fide_id=_field(raw, columns.FIDE_ID).strip(),
        birth_date=_field(raw, columns.BIRTH_DATE).strip(),
        points=_optional_float(_field(raw, columns.POINTS)),
        rank=_optional_int(_field(raw, columns.RANK)),
        rounds=_parse_rounds(raw, unknown_codes=unknown_codes),
        line_no=line_no,
        raw=raw,
    )


def _parse_rounds(raw: str, *, unknown_codes: set[str]) -> dict[int, RoundEntry]:
    rounds: dict[int, RoundEntry] = {}
    round_no = 0
    while True:
        round_no += 1
        base = columns.round_base(round_no)
        if base >= len(raw):
            break
        block = raw[base : base + columns.ROUND_WIDTH]
        if not block.strip():
            continue
        if not _is_round_block(raw, round_no):
            # Not a round at all. Some producers append their own fields after
            # the last round block; reading them as rounds would make the
            # serializer overwrite them, so stop at the first thing that does
            # not have the shape of a round.
            break

        result = _char(raw, columns.result_index(round_no))
        if not is_known(result):
            unknown_codes.add(result)

        rounds[round_no] = RoundEntry(
            round_no=round_no,
            opponent=_opponent(_field(raw, columns.opponent_slice(round_no))),
            colour=_colour(_char(raw, columns.colour_index(round_no))),
            result=result,
        )
    return rounds


def _is_round_block(raw: str, round_no: int) -> bool:
    """Does this window have the shape of a round -- numeric opponent, legal colour?

    The result character is deliberately not part of the test: an unfamiliar
    result code is something to report, not a reason to stop reading rounds.
    """
    opponent = _field(raw, columns.opponent_slice(round_no)).strip()
    if opponent and not opponent.isdigit():
        return False
    return _char(raw, columns.colour_index(round_no)).strip().lower() in ("", "w", "b", "-")


def _opponent(text: str) -> int | None:
    value = _optional_int(text)
    return None if value in (None, 0) else value


def _colour(char: str) -> Colour:
    lowered = char.strip().lower()
    if lowered == "w":
        return Colour.WHITE
    if lowered == "b":
        return Colour.BLACK
    return Colour.NONE


def _field(raw: str, span: slice) -> str:
    return raw[span]


def _char(raw: str, index: int) -> str:
    return raw[index] if index < len(raw) else " "


def _optional_int(text: str) -> int | None:
    stripped = text.strip()
    if not stripped:
        return None
    try:
        return int(stripped)
    except ValueError:
        return None


def _optional_float(text: str) -> float | None:
    stripped = text.strip().replace(",", ".")
    if not stripped:
        return None
    try:
        return float(stripped)
    except ValueError:
        return None
