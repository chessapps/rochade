"""The manager port is a seam, not a protocol with one implementation.

A port that only Vega satisfies proves nothing. These tests register a second,
deliberately different adapter -- a different wire format, a smaller result
vocabulary -- and drive the whole import/export loop through it. If the seam
leaks TRF, this is where it shows.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from typing import ClassVar

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from seebach.features.games.set_result import SetResult
from seebach.features.imports.import_round import ImportRound
from seebach.features.imports.preview_import import PreviewImport
from seebach.features.managers.list_managers import ListManagers
from seebach.features.rounds.export_round import ExportRound
from seebach.features.rounds.release_round import ReleaseRound
from seebach.interchange import (
    Capabilities,
    ManagerFile,
    PairingRow,
    PlayerRow,
    ResultEntry,
    RoundDocument,
    Support,
    manager_for,
)
from seebach.interchange import port as port_module
from seebach.platform.errors import Conflict, ValidationFailed
from seebach.shared.models import Round, Section, Tournament
from tests.conftest import Send

pytestmark = pytest.mark.db


# --- a second adapter, as unlike Vega as we can cheaply make it -------------

#: Deliberately not TRF: two header lines, then "board|white|black|result".
SIMPLE_FILE = """ROUND 1
PLAYERS 4
1|Alpha, Ann|3|Gamma, Gus|
2|Beta, Bob|4|Delta, Dee|
"""


class SimpleManager:
    """A toy manager that speaks a line format and cannot express forfeits."""

    key: ClassVar[str] = "simple"
    label: ClassVar[str] = "Simple (test only)"
    capabilities: ClassVar[Capabilities] = Capabilities(
        exports_unplayed_round=Support.YES,
        merges_on_import=Support.YES,
        # Played results only. A forfeit or a bye has nowhere to go.
        result_codes_out=frozenset({"1", "=", "0"}),
        reads_format="simple-lines",
        writes_format="simple-lines",
        notes=("Cannot carry forfeits or byes.",),
    )

    def read_round(
        self, content: str, known_players: Mapping[int, PlayerRow] | None = None
    ) -> RoundDocument:
        lines = [line for line in content.splitlines() if line.strip()]
        round_number = int(lines[0].split()[1])
        players: dict[int, PlayerRow] = {}
        rows: list[PairingRow] = []
        for board, line in enumerate(lines[2:], start=1):
            white_rank, white_name, black_rank, black_name, result = line.split("|")
            players[int(white_rank)] = PlayerRow(start_rank=int(white_rank), name=white_name)
            players[int(black_rank)] = PlayerRow(start_rank=int(black_rank), name=black_name)
            rows.append(
                PairingRow(
                    board=board,
                    white_rank=int(white_rank),
                    white_name=white_name,
                    black_rank=int(black_rank),
                    black_name=black_name,
                    white_result=result or " ",
                    black_result=" ",
                )
            )
        return RoundDocument(
            round_number=round_number,
            players=players,
            pairings={round_number: rows},
            source=content,
            tournament_name="Simple Open",
            declared_rounds=round_number,
        )

    def write_results(
        self,
        document: RoundDocument,
        round_number: int,
        results: Sequence[ResultEntry],
        *,
        stem: str,
    ) -> ManagerFile:
        by_rank = {entry.white_rank: entry.white_result for entry in results}
        lines = [f"ROUND {round_number}", f"PLAYERS {len(document.players)}"]
        for row in document.board_rows(round_number):
            lines.append(
                f"{row.white_rank}|{row.white_name}|{row.black_rank}|{row.black_name}"
                f"|{by_rank.get(row.white_rank, '')}"
            )
        return ManagerFile(filename=f"{stem}.simple", content="\n".join(lines) + "\n")


@pytest.fixture
def simple_manager() -> Iterator[SimpleManager]:
    manager = SimpleManager()
    port_module.register(manager)
    try:
        yield manager
    finally:
        port_module._REGISTRY.pop(manager.key, None)


# --- the tests --------------------------------------------------------------


def test_an_adapter_can_be_registered_and_listed(send: Send, simple_manager: SimpleManager) -> None:
    listed = {m.key: m for m in send(ListManagers())}
    assert set(listed) == {"vega", "swiss_manager", "simple"}
    assert listed["simple"].writes_format == "simple-lines"
    assert listed["simple"].verified is True
    # Vega's flags are honest about never having been checked against the real
    # program -- that is what M0 is for. Swiss-Manager's were.
    assert listed["vega"].verified is False
    assert listed["vega"].exports_unplayed_round is Support.UNVERIFIED
    assert listed["swiss_manager"].verified is True
    assert listed["swiss_manager"].merges_on_import is Support.YES


def test_the_whole_loop_runs_through_a_non_trf_adapter(
    send: Send, session: Session, tournament: Tournament, simple_manager: SimpleManager
) -> None:
    plan = send(
        PreviewImport(
            tournament_id=tournament.id,
            section_name="S",
            content=SIMPLE_FILE,
            manager="simple",
        )
    )
    assert plan.tournament_name == "Simple Open"
    assert plan.boards == 2
    assert [p.name for p in plan.players_added] == [
        "Alpha, Ann",
        "Beta, Bob",
        "Gamma, Gus",
        "Delta, Dee",
    ]

    send(
        ImportRound(
            tournament_id=tournament.id,
            section_name="S",
            content=SIMPLE_FILE,
            manager="simple",
        )
    )
    section = session.scalars(select(Section)).one()
    assert section.manager == "simple"

    round_ = session.scalars(select(Round)).one()
    boards = sorted(round_.games, key=lambda g: g.board)
    assert [(g.white_name, g.black_name) for g in boards] == [
        ("Alpha, Ann", "Gamma, Gus"),
        ("Beta, Bob", "Delta, Dee"),
    ]

    for game in boards:
        send(SetResult(game_id=game.id, white_result="1", black_result="0"))
    send(ReleaseRound(round_id=round_.id))

    exported = send(ExportRound(round_id=round_.id))
    assert exported.manager == "simple"
    assert exported.file_format == "simple-lines"
    assert exported.filename == "S-round1.simple"
    assert exported.content.splitlines()[2] == "1|Alpha, Ann|3|Gamma, Gus|1"


def test_export_refuses_a_code_the_adapter_would_silently_drop(
    send: Send, session: Session, tournament: Tournament, simple_manager: SimpleManager
) -> None:
    """The failure this design is most exposed to, caught before it happens."""
    send(
        ImportRound(
            tournament_id=tournament.id,
            section_name="S",
            content=SIMPLE_FILE,
            manager="simple",
        )
    )
    round_ = session.scalars(select(Round)).one()
    boards = sorted(round_.games, key=lambda g: g.board)

    send(SetResult(game_id=boards[0].id, white_result="+", black_result="-"))
    send(SetResult(game_id=boards[1].id, white_result="=", black_result="="))
    send(ReleaseRound(round_id=round_.id))

    with pytest.raises(Conflict) as excinfo:
        send(ExportRound(round_id=round_.id))
    assert excinfo.value.details["codes"] == ["+", "-"]

    # The arbiter can still force it, having been told what it costs.
    forced = send(ExportRound(round_id=round_.id, force=True))
    assert forced.boards_written == 2


def test_vega_carries_every_code_so_nothing_is_refused(
    send: Send, session: Session, tournament: Tournament, round1_text: str
) -> None:
    send(ImportRound(tournament_id=tournament.id, section_name="A", content=round1_text))
    round_ = session.scalars(select(Round)).one()
    for game in round_.games:
        send(SetResult(game_id=game.id, white_result="+", black_result="-"))
    send(ReleaseRound(round_id=round_.id))

    exported = send(ExportRound(round_id=round_.id))
    assert exported.manager == "vega"
    assert exported.file_format == "trf16"
    assert manager_for("vega").capabilities.drops(["+", "-", "H", "U", "Z"]) == []


def test_an_unknown_manager_is_rejected_by_name(send: Send, tournament: Tournament) -> None:
    with pytest.raises(ValidationFailed, match="no manager adapter named"):
        send(
            PreviewImport(
                tournament_id=tournament.id,
                section_name="S",
                content=SIMPLE_FILE,
                manager="nonesuch",
            )
        )


def test_sections_in_one_tournament_can_use_different_managers(
    send: Send,
    session: Session,
    tournament: Tournament,
    round1_text: str,
    simple_manager: SimpleManager,
) -> None:
    """The reason `manager` is on the section, not the tournament."""
    send(ImportRound(tournament_id=tournament.id, section_name="A", content=round1_text))
    send(
        ImportRound(
            tournament_id=tournament.id,
            section_name="S",
            content=SIMPLE_FILE,
            manager="simple",
        )
    )
    sections = {s.name: s.manager for s in session.scalars(select(Section)).all()}
    assert sections == {"A": "vega", "S": "simple"}
