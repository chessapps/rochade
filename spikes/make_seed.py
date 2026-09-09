"""Generate the M0 seed tournament as a TRF16 file.

Swiss-Manager has `Datei -> FIDE-Datenformat importieren TRF16`, so the whole
test tournament can be imported rather than keyed in by hand. That is worth
doing for its own sake: it exercises the direction we most need to work, before
any results are involved.

The seed holds **rounds 1 and 2 only**. Round 3 is deliberately absent so that
Swiss-Manager pairs it itself -- which is what check 1 is about. It carries the
awkward cases on purpose:

    round 1   a forfeit (+/-) and a pairing-allocated bye (U)
    round 2   a half-point bye (H)

Two files are written. The plain one is ASCII throughout, so a failed import is
unambiguous. The `-accents` one differs only in two names, and is a deliberate
probe: TRF is a fixed-*column* format, and in UTF-8 an umlaut is two bytes, so
a reader that indexes bytes rather than characters shifts every field after the
name -- but only on those two rows. Import the plain file first.

Columns come from `rochade.trf.columns`, the same definitions the parser uses,
so this file and the reader cannot drift apart.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from rochade.trf import columns, parse
from rochade.trf.results import points_for

CRLF = chr(13) + chr(10)

HEADER = [
    "012 Rochade M0 Spike",
    "022 Rochade",
    "032 SUI",
    "042 2026/09/05",
    "052 2026/09/07",
    "062 9",
    "072 9",
    "092 Individual: Swiss-System",
    "102 Muster, Anna",
    "122 90 min + 30 sec increment",
    "XXR 5",
    "XXC white1",
]

# rank, sex, title, name, rating, federation, born
PLAYERS = [
    (1, "m", "FM", "Baumann, Lukas", 2201, "SUI", "1990/04/02"),
    (2, "m", "", "Chen, Wei", 2150, "SUI", "1995/11/23"),
    (3, "w", "WFM", "Dubois, Elise", 2098, "FRA", "2001/07/09"),
    (4, "m", "", "Mueller, Tobias", 2044, "SUI", "1988/01/30"),
    (5, "m", "", "Fischer, Jonas", 1987, "GER", "2003/05/17"),
    (6, "w", "", "Gruber, Sarah", 1922, "AUT", "1999/09/12"),
    (7, "m", "", "Huber, Marco", 1870, "SUI", "1975/12/01"),
    (8, "w", "", "Iten, Nadia", 1804, "SUI", "2007/02/28"),
    (9, "m", "", "Jenni, Rafael", 1755, "SUI", "2010/06/05"),
]

# round -> list of (white, black, white_result). black None means a bye, and
# the result is then the bye code itself.
ROUNDS: dict[int, list[tuple[int, int | None, str]]] = {
    1: [
        (1, 5, "1"),
        (6, 2, "0"),
        (3, 7, "="),
        (4, 8, "+"),  # Iten did not appear -- forfeit
        (9, None, "U"),  # pairing-allocated bye
    ],
    2: [
        (2, 1, "="),
        (9, 4, "0"),
        (3, 6, "1"),
        (7, 8, "="),
        (5, None, "H"),  # requested half-point bye
    ],
}

MIRROR = {"1": "0", "0": "1", "=": "=", "+": "-", "-": "+"}


#: Applied only to the second file. Same lengths in characters, different in bytes.
ACCENTED = {3: "Dubois, Élise", 4: "Müller, Tobias"}


def build(accents: bool = False) -> str:
    entries: dict[int, dict[int, tuple[int | None, str, str]]] = {rank: {} for rank, *_ in PLAYERS}
    for round_no, games in ROUNDS.items():
        for white, black, result in games:
            if black is None:
                entries[white][round_no] = (None, "-", result)
                continue
            entries[white][round_no] = (black, "w", result)
            entries[black][round_no] = (white, "b", MIRROR[result])

    points = {
        rank: sum(points_for(code) for _, _, code in entries[rank].values()) for rank, *_ in PLAYERS
    }
    order = sorted(points, key=lambda r: (-points[r], r))
    ranks = {rank: i for i, rank in enumerate(order, start=1)}

    lines = list(HEADER)
    for rank, sex, title, name, rating, federation, born in PLAYERS:
        shown = ACCENTED.get(rank, name) if accents else name
        lines.append(
            _player_line(
                rank,
                sex,
                title,
                shown,
                rating,
                federation,
                born,
                points[rank],
                ranks[rank],
                entries[rank],
            )
        )
    return CRLF.join(lines) + CRLF


def _player_line(
    rank: int,
    sex: str,
    title: str,
    name: str,
    rating: int,
    federation: str,
    born: str,
    points: float,
    final_rank: int,
    entries: dict[int, tuple[int | None, str, str]],
) -> str:
    cells = list(" " * (columns.HEADER_WIDTH + 1))
    _put(cells, columns.CODE, "001")
    _put(cells, columns.START_RANK, f"{rank:4d}")
    _put(cells, columns.SEX, sex.ljust(1))
    _put(cells, columns.TITLE, title.ljust(3))
    _put(cells, columns.NAME, name.ljust(33)[:33])
    _put(cells, columns.RATING, f"{rating:4d}")
    _put(cells, columns.FEDERATION, federation.ljust(3))
    # FIDE id left blank on purpose: these are invented players, and a made-up
    # id invites the manager to try matching them against a real rating list.
    _put(cells, columns.FIDE_ID, " " * 11)
    _put(cells, columns.BIRTH_DATE, born.ljust(10))
    _put(cells, columns.POINTS, f"{points:4.1f}")
    _put(cells, columns.RANK, f"{final_rank:4d}")
    line = "".join(cells).rstrip()

    for round_no in sorted(entries):
        opponent, colour, result = entries[round_no]
        base = columns.round_base(round_no)
        line = line.ljust(base)
        block = list(" " * columns.ROUND_WIDTH)
        block[0:4] = list(f"{opponent:4d}" if opponent is not None else "0000")
        block[columns.COLOUR_OFFSET] = colour
        block[columns.RESULT_OFFSET] = result
        line += "".join(block).rstrip()
    return line


def _put(cells: list[str], span: slice, value: str) -> None:
    width = span.stop - span.start
    cells[span] = list(value.ljust(width)[:width])


def verify(text: str) -> None:
    """Read it back with our own parser and assert it says what we meant."""
    trf = parse(text)
    assert len(trf.players) == 9, len(trf.players)
    assert trf.declared_rounds == 5, trf.declared_rounds
    assert trf.rounds_present == 2, trf.rounds_present
    assert trf.unknown_result_codes == [], trf.unknown_result_codes

    codes = {code for p in trf.players.values() for e in p.rounds.values() for code in [e.result]}
    for required in ("+", "-", "U", "H"):
        assert required in codes, f"{required!r} missing from the seed"

    assert trf.player(4).points == 2.0, trf.player(4).points

    for round_no in (1, 2):
        seen = [
            r
            for pairing in trf.pairings(round_no)
            for r in (pairing.white, pairing.black)
            if r is not None
        ]
        assert sorted(seen) == list(range(1, 10)), (round_no, sorted(seen))

    print("  verified: 9 players, 2 rounds, codes + - U H present, names intact")


def main() -> int:
    out = pathlib.Path(__file__).parent / "out"
    out.mkdir(exist_ok=True)

    for accents, filename in ((False, "m0-seed.trf"), (True, "m0-seed-accents.trf")):
        text = build(accents=accents)
        verify(text)
        path = out / filename
        # UTF-8 without a BOM, CRLF: that is what TRF16 is. Written in binary so
        # nothing re-translates the line endings on the way out.
        path.write_bytes(text.encode("utf-8"))
        widened = max(len(line.encode("utf-8")) - len(line) for line in text.split(CRLF))
        note = "ASCII only" if not accents else f"+{widened} bytes on the widened rows"
        print(f"  wrote {path.resolve()}  ({path.stat().st_size} bytes, {note})")

    print()
    print("Standings after round 2 (what Swiss-Manager should show):")
    trf = parse(build())
    for rank in sorted(trf.players, key=lambda r: (-(trf.players[r].points or 0), r)):
        p = trf.players[rank]
        print(f"  {p.points:4.1f}  #{rank}  {p.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
