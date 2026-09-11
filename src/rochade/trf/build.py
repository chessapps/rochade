"""Build a TRF16 document from scratch.

The rest of this library patches files a manager wrote. This is the one place
that writes one with no original to patch: a tournament Rochade runs itself
has no file until we make one, and the pairing engine reads nothing else.

The input is deliberately not a database model. `BuildPlayer` carries what a
`001` line carries and nothing more, so the builder can be tested without a
database and the pairing feature can be tested without a builder.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from rochade.trf import columns
from rochade.trf.model import RoundEntry
from rochade.trf.results import is_known, points_for

CRLF = "\r\n"

#: The starting rank and the opponent share a four-digit column.
MAX_RANK = 9999


def _clean(value: str) -> str:
    """One line, single spaces, printable characters only.

    A line break in a name would end the `001` record and start another;
    whatever followed would be read as a record of its own. The builder
    refuses to write one, whoever forgot to validate upstream.
    """
    return " ".join("".join(c for c in value if c.isprintable()).split())


@dataclass(frozen=True, slots=True)
class BuildPlayer:
    start_rank: int
    name: str
    sex: str = ""
    title: str = ""
    rating: int | None = None
    federation: str = ""
    fide_id: str = ""
    birth_date: str = ""
    #: By round number. A round the player was not in -- a late entry's
    #: earlier rounds, a withdrawn player's later ones -- is simply absent
    #: and renders as a blank block, which the engine scores as an absence.
    rounds: Mapping[int, RoundEntry] = field(default_factory=dict)

    @property
    def points(self) -> float:
        return sum(points_for(e.result) for e in self.rounds.values() if is_known(e.result))


@dataclass(frozen=True, slots=True)
class BuildDocument:
    name: str
    players: Sequence[BuildPlayer]
    city: str = ""
    federation: str = ""
    start_date: str = ""
    end_date: str = ""
    declared_rounds: int | None = None
    #: "white" | "black" | None. Written as `XXC` for readers that honour it;
    #: the engine takes it as a command-line flag instead.
    top_colour: str | None = None

    @property
    def rounds_present(self) -> int:
        return max((max(p.rounds, default=0) for p in self.players), default=0)


def build(document: BuildDocument) -> str:
    """Render the document as TRF16 text, CRLF, trailing newline."""
    lines = [f"012 {_clean(document.name)}".rstrip()]
    if document.city:
        lines.append(f"022 {_clean(document.city)}")
    if document.federation:
        lines.append(f"032 {_clean(document.federation)}")
    if document.start_date:
        lines.append(f"042 {_clean(document.start_date)}")
    if document.end_date:
        lines.append(f"052 {_clean(document.end_date)}")
    lines.append(f"062 {len(document.players)}")
    lines.append("092 Individual: Swiss-System")
    if document.declared_rounds is not None:
        lines.append(f"XXR {document.declared_rounds}")
    if document.top_colour in ("white", "black"):
        lines.append(f"XXC {document.top_colour}1")

    ranks = _ranks(document.players)
    width = document.rounds_present
    for player in sorted(document.players, key=lambda p: p.start_rank):
        lines.append(_player_line(player, ranks[player.start_rank], width))

    return CRLF.join(lines) + CRLF


def _ranks(players: Sequence[BuildPlayer]) -> dict[int, int]:
    """Provisional rank by points then start rank -- the column is informative only."""
    ordered = sorted(players, key=lambda p: (-p.points, p.start_rank))
    return {p.start_rank: i for i, p in enumerate(ordered, start=1)}


def _player_line(player: BuildPlayer, rank: int, width: int) -> str:
    if not 1 <= player.start_rank <= MAX_RANK:
        raise ValueError(f"starting rank {player.start_rank} does not fit a TRF line")
    cells = list(" " * columns.HEADER_WIDTH)
    _put(cells, columns.CODE, "001")
    _put(cells, columns.START_RANK, f"{player.start_rank:4d}")
    _put(cells, columns.SEX, _clean(player.sex)[:1])
    _put(cells, columns.TITLE, _clean(player.title)[:3])
    _put(cells, columns.NAME, _clean(player.name)[:33])
    _put(cells, columns.RATING, f"{player.rating:4d}" if player.rating else "")
    _put(cells, columns.FEDERATION, _clean(player.federation)[:3])
    _put(cells, columns.FIDE_ID, _clean(player.fide_id)[:11].rjust(11))
    _put(cells, columns.BIRTH_DATE, _clean(player.birth_date)[:10])
    _put(cells, columns.POINTS, f"{player.points:4.1f}")
    _put(cells, columns.RANK, f"{rank:4d}")
    line = "".join(cells)

    for round_no in range(1, width + 1):
        entry = player.rounds.get(round_no)
        if entry is None:
            line += " " * columns.ROUND_WIDTH
            continue
        if entry.opponent is not None and not 1 <= entry.opponent <= MAX_RANK:
            raise ValueError(f"opponent {entry.opponent} does not fit a TRF line")
        opponent = f"{entry.opponent:4d}" if entry.opponent is not None else "0000"
        result = entry.result if len(entry.result) == 1 and entry.result.isprintable() else " "
        line += f"  {opponent} {entry.colour.value} {result}"
    return line.rstrip()


def _put(cells: list[str], span: slice, text: str) -> None:
    width = span.stop - span.start
    cells[span] = list(text.ljust(width)[:width])
