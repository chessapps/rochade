"""The parsed TRF document.

Design rule: every line of the source file survives in `TrfFile.lines`
verbatim. The typed fields on `Player` are a *view* over the raw line, never a
replacement for it -- serialization patches the raw text rather than rebuilding
it, so a field we never modelled cannot be lost.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from rochade.trf import columns
from rochade.trf.results import is_known, mirror, points_for


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
    #: Starting ranks whose points we adjusted. Serialization writes the points
    #: column for these and no others, so a player we never touched keeps the
    #: manager's own number byte for byte -- comma decimal separators included.
    points_changed: set[int] = field(default_factory=set)

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

        TRF carries no board numbers, so they are derived -- and derived the way
        the managers print them, which is the FIDE order: the higher score of
        the two players first, then the sum of their scores, then the start rank
        of the player *with* that higher score (the lower rank when they are
        level); byes after every real game. Scores are the players' points
        *before* the round. Swiss-Manager's pairing lists matched this on every
        board of every round M0 looked at, including a round built so that the
        third key alone decided two boards.

        Still not an identity: a re-pair renumbers boards, which is why nothing
        downstream may treat a board as more than a label.
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

        before = self.points_before(round_no)

        def board_key(game: tuple[int, int | None, str, str]) -> tuple[float, float, int]:
            white, black = game[0], game[1]
            if black is None:
                return (-before.get(white, 0.0), -before.get(white, 0.0), white)
            ws, bs = before.get(white, 0.0), before.get(black, 0.0)
            # Level scores: the lower rank. Otherwise whoever holds the higher score.
            leader = min(white, black) if ws == bs else (white if ws > bs else black)
            return (-max(ws, bs), -(ws + bs), leader)

        real = sorted((g for g in games if g[1] is not None), key=board_key)
        byes = sorted((g for g in games if g[1] is None), key=board_key)
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

    def points_before(self, round_no: int) -> dict[int, float]:
        """Each player's score going into `round_no`, from the points column.

        The column is whatever the manager last computed. For a round that is
        complete it includes that round, so everything from `round_no` onwards is
        subtracted at face value. A round with any game still unplayed is left
        alone: Swiss-Manager does not credit even the byes of an open round until
        it is complete, and subtracting them would move the bye player for no
        reason. Players without a points column score 0 -- ordering is all this
        is used for.
        """
        open_rounds = {
            r
            for r in range(round_no, self.rounds_present + 1)
            if any(
                e.result == " "
                for p in self.players.values()
                if (e := p.rounds.get(r)) is not None and not e.is_bye
            )
        }
        before: dict[int, float] = {}
        for rank, player in self.players.items():
            total = player.points if player.points is not None else 0.0
            for r, entry in player.rounds.items():
                if r >= round_no and r not in open_rounds and is_known(entry.result):
                    total -= points_for(entry.result)
            before[rank] = total
        return before


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
