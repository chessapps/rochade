"""The parsed TRF document.

Design rule: every line of the source file survives in `TrfFile.lines`
verbatim. The typed fields on `Player` are a *view* over the raw line, never a
replacement for it -- serialization patches the raw text rather than rebuilding
it, so a field we never modelled cannot be lost.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from seebach.trf import columns
from seebach.trf.results import mirror


class Colour(StrEnum):
    WHITE = "w"
    BLACK = "b"
    NONE = "-"

    @property
    def opposite(self) -> Colour:
        if self is Colour.WHITE:
            return Colour.BLACK
        if self is Colour.BLACK:
            return Colour.WHITE
        return Colour.NONE


@dataclass(slots=True)
class TrfLine:
    """One physical line, kept verbatim."""

    line_no: int
    raw: str

    @property
    def code(self) -> str:
        return self.raw[columns.CODE].strip()


@dataclass(slots=True)
class RoundEntry:
    round_no: int
    opponent: int | None
    colour: Colour
    result: str

    @property
    def is_bye(self) -> bool:
        return self.opponent is None


@dataclass(slots=True)
class Player:
    start_rank: int
    name: str
    sex: str
    title: str
    rating: int | None
    federation: str
    fide_id: str
    birth_date: str
    points: float | None
    rank: int | None
    rounds: dict[int, RoundEntry]
    line_no: int
    raw: str

    def round(self, round_no: int) -> RoundEntry | None:
        return self.rounds.get(round_no)


@dataclass(slots=True, frozen=True)
class Pairing:
    """A game in one round, seen from both sides.

    `black` is None for a bye. Board numbers are not in the TRF at all -- they
    are assigned by ordering, which is why we derive rather than read them.
    """

    round_no: int
    board: int
    white: int
    black: int | None
    white_result: str
    black_result: str

    @property
    def is_bye(self) -> bool:
        return self.black is None


@dataclass(slots=True)
class TrfFile:
    lines: list[TrfLine]
    players: dict[int, Player]
    name: str = ""
    city: str = ""
    federation: str = ""
    start_date: str = ""
    end_date: str = ""
    chief_arbiter: str = ""
    declared_rounds: int | None = None
    newline: str = "\n"
    trailing_newline: bool = True
    unknown_result_codes: list[str] = field(default_factory=list)

    @property
    def rounds_present(self) -> int:
        """Highest round number for which any player has a round block."""
        return max((max(p.rounds, default=0) for p in self.players.values()), default=0)

    @property
    def round_count(self) -> int:
        """Rounds the tournament runs, preferring the declared XXR value."""
        return self.declared_rounds if self.declared_rounds is not None else self.rounds_present

    def player(self, start_rank: int) -> Player:
        try:
            return self.players[start_rank]
        except KeyError:
            raise KeyError(f"no player with starting rank {start_rank}") from None

    def pairings(self, round_no: int) -> list[Pairing]:
        """Games in `round_no`, deduplicated across the two player rows.

        Board numbers follow the conventional ordering: real games first in
        white-player rank order, then byes. Vega renumbers boards on re-pairing,
        which is exactly why nothing downstream may treat a board as an identity.
        """
        games: list[tuple[int, int | None, str, str]] = []
        seen: set[int] = set()
        for rank in sorted(self.players):
            if rank in seen:
                continue
            entry = self.players[rank].rounds.get(round_no)
            if entry is None:
                continue
            seen.add(rank)
            if entry.opponent is None:
                games.append((rank, None, entry.result, " "))
                continue
            seen.add(entry.opponent)
            opponent = self.players.get(entry.opponent)
            other = opponent.rounds.get(round_no) if opponent else None
            other_result = other.result if other else _mirror_or_blank(entry.result)
            if entry.colour is Colour.BLACK:
                games.append((entry.opponent, rank, other_result, entry.result))
            else:
                games.append((rank, entry.opponent, entry.result, other_result))

        real = sorted((g for g in games if g[1] is not None), key=lambda g: g[0])
        byes = sorted((g for g in games if g[1] is None), key=lambda g: g[0])
        return [
            Pairing(
                round_no=round_no,
                board=i,
                white=w,
                black=b,
                white_result=wr,
                black_result=br,
            )
            for i, (w, b, wr, br) in enumerate([*real, *byes], start=1)
        ]


def _mirror_or_blank(code: str) -> str:
    """The opponent's code, or blank when the file is inconsistent.

    Reached only when a player points at an opponent whose row does not list the
    game back. That is a damaged file, but the import preview is a better place
    to say so than a crash inside a read model.
    """
    try:
        return mirror(code)
    except ValueError:
        return " "
