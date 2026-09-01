"""A round as any manager describes it, with no format in the shape.

This is what the port passes across. It is deliberately not a TRF model: a
manager that hands us PGN, XML or nothing at all must be able to produce one of
these, or the seam is a TRF seam wearing a different name.

The one concession to format is `source`, which holds the original bytes
verbatim. Passthrough fidelity depends on writing results back into the file we
were given rather than rebuilding it, so the adapter needs the original to
patch. Nothing outside an adapter should look at it.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class PlayerRow:
    start_rank: int
    name: str
    title: str = ""
    rating: int | None = None
    federation: str = ""
    fide_id: str = ""


@dataclass(frozen=True, slots=True)
class PairingRow:
    """One board. `black_*` is None for a bye -- there is no opponent at all.

    Results are TRF codes even here, one per side. They are the only vocabulary
    that can express a forfeit, a half-point bye and a double forfeit, so they
    are the lingua franca between adapters even when neither end is TRF. An
    adapter whose format cannot carry a code says so in its `Capabilities`.
    """

    board: int
    white_rank: int
    white_name: str
    black_rank: int | None = None
    black_name: str | None = None
    white_result: str = " "
    black_result: str = " "

    @property
    def is_bye(self) -> bool:
        return self.black_rank is None


@dataclass(frozen=True, slots=True)
class RoundDocument:
    """Everything one manager export told us.

    Carries every round the file describes, not just the newest one: the import
    diff compares prior-round results against what we hold, and a rebuild
    recreates the whole section.
    """

    round_number: int
    players: dict[int, PlayerRow]
    pairings: dict[int, list[PairingRow]]
    source: str
    tournament_name: str = ""
    declared_rounds: int | None = None
    unknown_result_codes: list[str] = field(default_factory=list)

    @property
    def rounds_present(self) -> int:
        return max(self.pairings, default=0)

    def board_rows(self, round_no: int) -> list[PairingRow]:
        return self.pairings.get(round_no, [])

    @property
    def open_rounds(self) -> list[int]:
        """Rounds that are paired but carry no result -- what players would enter.

        If this is empty the manager gave us history only, and the loop cannot
        start however good the import side turns out to be.
        """
        return [
            round_no
            for round_no, rows in sorted(self.pairings.items())
            if rows and all(row.white_result == " " for row in rows if not row.is_bye)
        ]


@dataclass(frozen=True, slots=True)
class ResultEntry:
    """One confirmed board, addressed the way every format can address it.

    Both sides, because a double forfeit is ("-", "-") and no single white-side
    code can say so. A blank black side means "the mirror of white".
    """

    white_rank: int
    white_result: str
    black_result: str = " "


@dataclass(frozen=True, slots=True)
class ManagerFile:
    """What the arbiter downloads and feeds back into the manager."""

    filename: str
    content: str
    media_type: str = "text/plain"
