"""The Swiss-Manager player file ("Spielerdaten (Text-File)").

The other half of what Swiss-Manager exports as plain text. The pairing file
says who plays whom by start number; this one says who those numbers are::

    Nr;Name;Titel;Identnr;EloNat;EloInt;Geburt;Fed;Sex;...;Nachname;Vorname;Atitel
    1;Brunner Livia;WGM;;0;2447;01.06.1992;SUI;W;...;Brunner;Livia;

Together they carry everything a round needs, which is what makes them an
inbound leg on their own: `Extras -> Daten Import/Export` writes both, and
neither goes near the TRF16 export.

Columns are looked up **by name from the header row**, never by position. The
number of tiebreak columns (`Wtg1`..`Wtg6`) follows the tournament's settings,
so counting fields from the left is how a reader breaks on somebody else's
tournament.

The same file carries the standings: `Pkt` (points), `Wtg1`.. (the tiebreaks
in the order the tournament's settings define, unnamed) and `Rang` (rank), as
Swiss-Manager's own Rangliste has them at export time. That is the whole
reason Seebach never computes a tiebreak of its own.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

#: The columns this reader needs. Everything else in the file is ignored.
REQUIRED = ("Nr", "Nachname", "Vorname")


class PlayerFileError(ValueError):
    def __init__(self, message: str, *, line_no: int | None = None) -> None:
        super().__init__(message)
        self.line_no = line_no


@dataclass(frozen=True, slots=True)
class PlayerLine:
    #: `Nr` -- the start number the pairing file joins on.
    start_number: int
    #: "Surname,Given", as TRF spells it and as the rest of the code expects.
    name: str
    title: str = ""
    rating: int | None = None
    federation: str = ""
    fide_id: str = ""
    #: `Pkt`; None when the column is absent or empty.
    points: float | None = None
    #: `Wtg1`.. in file order, trailing empties dropped. Unnamed: the file does
    #: not say which system each column is.
    tiebreaks: tuple[float | None, ...] = ()
    #: `Rang`; None when the column is absent or empty.
    rank: int | None = None


_TIEBREAK = re.compile(r"^Wtg(\d+)$")


def looks_like_player_file(text: str) -> bool:
    first = _first_line(text)
    return first.startswith("Nr;") and "Nachname" in first


def parse_player_file(text: str) -> list[PlayerLine]:
    rows = text.replace("\r\n", "\n").split("\n")
    if not rows:
        raise PlayerFileError("the file is empty", line_no=1)

    header = [cell.strip() for cell in rows[0].lstrip("﻿").split(";")]
    index = {name: i for i, name in enumerate(header)}
    tiebreak_columns = sorted(
        (int(m.group(1)), name) for name in header if (m := _TIEBREAK.match(name))
    )
    missing = [name for name in REQUIRED if name not in index]
    if missing:
        raise PlayerFileError(
            "not a Swiss-Manager player file: the header has no "
            + ", ".join(repr(name) for name in missing),
            line_no=1,
        )

    lines: list[PlayerLine] = []
    for line_no, raw in enumerate(rows[1:], start=2):
        if not raw.strip():
            continue
        cells = raw.split(";")

        def cell(name: str, cells: list[str] = cells) -> str:
            position = index.get(name)
            if position is None or position >= len(cells):
                return ""
            return cells[position].strip()

        try:
            start_number = int(cell("Nr"))
        except ValueError:
            raise PlayerFileError(
                f"unreadable start number {cell('Nr')!r}", line_no=line_no
            ) from None

        surname, given = cell("Nachname"), cell("Vorname")
        # `Name` holds the two joined by a space, which is not how anything else
        # here spells a name; the split columns are the ones to trust.
        name = ",".join(part for part in (surname, given) if part) or cell("Name")
        if not name:
            raise PlayerFileError(f"player {start_number} has no name", line_no=line_no)

        tiebreaks = [_number(cell(name)) for _, name in tiebreak_columns]
        while tiebreaks and tiebreaks[-1] is None:
            tiebreaks.pop()

        lines.append(
            PlayerLine(
                start_number=start_number,
                name=name,
                title=cell("Titel"),
                rating=_rating(cell("EloInt"), cell("EloNat")),
                federation=cell("Fed"),
                fide_id=_identity(cell("FideIdent")),
                points=_number(cell("Pkt")),
                tiebreaks=tuple(tiebreaks),
                rank=_integer(cell("Rang")),
            )
        )

    if not lines:
        raise PlayerFileError("the file has a header but no players", line_no=1)
    return lines


def _rating(international: str, national: str) -> int | None:
    """The international rating, or the national one when that is all there is."""
    for value in (international, national):
        try:
            number = int(value)
        except ValueError:
            continue
        if number > 0:
            return number
    return None


#: How Swiss-Manager spells a half: the glyph in `Pkt`, a decimal comma in
#: the tiebreak columns, and U+FFFD when a Windows-1252 file was read as UTF-8.
_HALVES = ("½", "�", "1/2")


def _number(value: str) -> float | None:
    """A score as Swiss-Manager writes it: `1`, `2½`, `0,5` or `0.5`; empty is None."""
    if not value:
        return None
    text = value.replace(" ", "")
    half = 0.0
    for glyph in _HALVES:
        if text.endswith(glyph):
            text = text[: -len(glyph)]
            half = 0.5
            break
    if not text:
        return half if half else None
    try:
        return float(text.replace(",", ".")) + half
    except ValueError:
        return None


def _integer(value: str) -> int | None:
    try:
        return int(value)
    except ValueError:
        return None


def _identity(value: str) -> str:
    """Swiss-Manager writes an empty cell or a `0` for "no FIDE id"."""
    return "" if value in ("", "0") else value


def _first_line(text: str) -> str:
    for line in text.replace("\r\n", "\n").split("\n"):
        if line.strip():
            return line.lstrip("﻿").strip()
    return ""


def by_start_number(lines: Iterable[PlayerLine]) -> dict[int, PlayerLine]:
    return {line.start_number: line for line in lines}
