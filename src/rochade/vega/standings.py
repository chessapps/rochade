"""``standings.txt`` as Vega writes it into the tournament folder.

Rewritten at every result. The table is fixed-column text with two ``|``
separators, a tie-break column per configured tie-break, and a legend at the
bottom that spells the column codes out::

    TestOpen
     - ,

    Standings at round 3

    Pos   N     NAME                      g | FRtg  NRtg  Fed |  Pts      BH
    ------------------------------------------------------------------------
      1   6     Gruber, Sarah             m | 1922     0  AUT |  2.5     5.0
      4   1  FM Baumann, Lukas            m | 2201     0  SUI |  2.0     4.0

    Tie Break legend:
    BH : Buchholz

Players on equal points and tie-breaks share a position, as above. The
title sits between the start number and the name; the name column is found
from the header. Rating ``0`` is unrated.

Observed on Vega 12.1.8, 2026-09-11.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_HEADER = re.compile(r"^\s*Standings at round (\d+)\s*$")
_ROW = re.compile(r"^\s*(\d+)\s+(\d+)\s*")
_LEGEND = re.compile(r"^\s*([A-Za-z0-9_]+)\s*:\s*(.+?)\s*$")


class StandingsError(ValueError):
    def __init__(self, message: str, *, line_no: int | None = None) -> None:
        super().__init__(message)
        self.line_no = line_no


@dataclass(frozen=True, slots=True)
class StandingsRow:
    position: int
    number: int
    name: str
    title: str = ""
    gender: str = ""
    fide_rating: int | None = None
    national_rating: int | None = None
    federation: str = ""
    points: float = 0.0
    #: One per tie-break column, in the header's order; None where blank.
    tiebreaks: tuple[float | None, ...] = ()


@dataclass(frozen=True, slots=True)
class Standings:
    tournament_name: str
    round_no: int
    #: The column codes as the header shows them (``BH``, ``BH_C1``, ...).
    tiebreak_codes: tuple[str, ...]
    #: The same, spelled out by the legend; the code again where it is silent.
    tiebreak_names: tuple[str, ...]
    rows: tuple[StandingsRow, ...]


def looks_like_standings(line: str) -> bool:
    return _HEADER.match(line) is not None


def parse_standings(text: str) -> Standings:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    lines = [line.lstrip("﻿") for line in lines]

    round_no: int | None = None
    header_at: int | None = None
    for i, line in enumerate(lines):
        match = _HEADER.match(line)
        if match:
            round_no = int(match.group(1))
            header_at = i
            break
    if round_no is None or header_at is None:
        raise StandingsError("no 'Standings at round N' line: this is not standings.txt")
    tournament_name = next((line.strip() for line in lines[:header_at] if line.strip()), "")

    columns_at = next(
        (
            i
            for i in range(header_at + 1, len(lines))
            if lines[i].lstrip().startswith("Pos") and "NAME" in lines[i]
        ),
        None,
    )
    if columns_at is None:
        raise StandingsError("no column header (Pos N NAME ...)", line_no=header_at + 1)
    header = lines[columns_at]
    parts = header.split("|")
    if len(parts) != 3:
        raise StandingsError("the column header is not in three parts", line_no=columns_at + 1)
    name_col = header.index("NAME")
    first_bar = header.index("|")
    codes = tuple(parts[2].split()[1:])  # after Pts

    rows: list[StandingsRow] = []
    i = columns_at + 1
    if i < len(lines) and set(lines[i].strip()) <= {"-"}:
        i += 1
    while i < len(lines) and lines[i].strip():
        rows.append(_row(lines[i], i + 1, name_col=name_col, first_bar=first_bar, width=len(codes)))
        i += 1

    legend: dict[str, str] = {}
    in_legend = False
    for line in lines[i:]:
        if line.strip().lower().startswith("tie break legend"):
            in_legend = True
            continue
        if not in_legend:
            continue
        if not line.strip():
            if legend:
                break
            continue
        match = _LEGEND.match(line)
        if match:
            legend[match.group(1)] = match.group(2)

    return Standings(
        tournament_name=tournament_name,
        round_no=round_no,
        tiebreak_codes=codes,
        tiebreak_names=tuple(legend.get(code, code) for code in codes),
        rows=tuple(rows),
    )


def _row(line: str, line_no: int, *, name_col: int, first_bar: int, width: int) -> StandingsRow:
    parts = line.split("|")
    if len(parts) != 3:
        raise StandingsError("a row is not in three parts", line_no=line_no)
    match = _ROW.match(line)
    if not match:
        raise StandingsError("a row does not start with position and start number", line_no=line_no)
    position, number = int(match.group(1)), int(match.group(2))
    title = line[match.end() : name_col].strip()
    who = line[name_col:first_bar].split()
    gender = ""
    if who and len(who[-1]) == 1 and who[-1].isalpha():
        gender = who.pop()
    name = " ".join(who)
    if not name:
        raise StandingsError("a row has no name", line_no=line_no)

    ratings = parts[1].split()
    if len(ratings) < 3:
        raise StandingsError("a row lacks ratings and federation", line_no=line_no)
    fide = _int(ratings[0])
    national = _int(ratings[1])
    federation = ratings[2]

    scores = parts[2].split()
    if not scores:
        raise StandingsError("a row has no points", line_no=line_no)
    points = _float(scores[0])
    if points is None:
        raise StandingsError(f"points {scores[0]!r} are not a number", line_no=line_no)
    tiebreaks = tuple(_float(cell) for cell in scores[1:])
    if len(tiebreaks) < width:
        tiebreaks = tiebreaks + (None,) * (width - len(tiebreaks))

    return StandingsRow(
        position=position,
        number=number,
        name=name,
        title=title,
        gender=gender,
        fide_rating=fide or None,
        national_rating=national or None,
        federation=federation,
        points=points,
        tiebreaks=tiebreaks[:width] if width else tiebreaks,
    )


def _int(text: str) -> int | None:
    try:
        return int(text)
    except ValueError:
        return None


def _float(text: str) -> float | None:
    try:
        return float(text.replace(",", "."))
    except ValueError:
        return None
