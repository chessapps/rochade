"""The manager's standings, shown and never computed."""

from __future__ import annotations

import pathlib
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from rochade.features.imports.import_round import ImportRound
from rochade.features.rounds.export_round import ExportRound
from rochade.features.rounds.release_round import ReleaseRound
from rochade.features.standings.get_standings import GetStandings
from rochade.features.standings.import_standings import ImportStandings
from rochade.features.standings.name_tiebreaks import NameTiebreaks
from rochade.platform.errors import NotFound, ValidationFailed
from rochade.platform.mediator import Principal
from rochade.shared.enums import PrincipalKind
from rochade.shared.models import Round, Section, Tournament
from tests.conftest import Send

pytestmark = [
    pytest.mark.db,
    # Every tournament here runs on Swiss-Manager.
    pytest.mark.manager("swiss_manager"),
]

SM = pathlib.Path(__file__).resolve().parents[1] / "fixtures" / "swiss_manager"


def read(name: str) -> str:
    return (SM / name).read_bytes().decode("utf-8")


def players_after_round_one() -> str:
    """The real player list, with the standings Swiss-Manager wrote after round 1."""
    return read("players_round1.txt")


def import_round_one(send: Send, tournament: Tournament) -> None:
    send(
        ImportRound(
            tournament_id=tournament.id,
            section_name="A",
            content=read("players_round1.txt") + "\n" + read("pairings_round1_played.txt"),
        )
    )


def test_the_round_import_brings_the_standings_along(
    send: Send, session: Session, tournament: Tournament
) -> None:
    """The player list carries Pkt, Wtg1.. and Rang; the import keeps them."""
    import_round_one(send, tournament)

    standings = send(GetStandings(tournament_id=tournament.id))

    assert len(standings.sections) == 1
    table = standings.sections[0]
    assert table.section_name == "A"
    assert table.manager_label == "Swiss-Manager"
    # The list was exported after round 1 was played and before round 2 was
    # paired: "after round 0" is what the import can know from a round-1 file.
    assert table.after_round == 0
    assert table.rows[0].rank == 1
    assert table.rows[0].name == "Brunner,Livia"
    assert table.rows[0].points == 1.0
    assert table.rows[0].tiebreaks == [1.0]
    assert table.tiebreak_columns == 1
    assert [r.rank for r in table.rows] == sorted(r.rank for r in table.rows)


def test_a_device_may_read_the_standings_of_its_own_tournament(
    send: Send, tournament: Tournament
) -> None:
    import_round_one(send, tournament)
    phone = Principal(
        kind=PrincipalKind.DEVICE,
        subject="device:phone",
        device_id=uuid.uuid4(),
        tournament_id=tournament.id,
    )

    assert send(GetStandings(tournament_id=tournament.id), principal=phone).sections


def test_standings_import_refreshes_the_table_after_an_export(
    send: Send, session: Session, tournament: Tournament
) -> None:
    """After the last round there is no pairing to import; the list alone will do."""
    import_round_one(send, tournament)
    round_ = session.scalars(select(Round).where(Round.number == 1)).one()
    send(ReleaseRound(round_id=round_.id, force=True))
    send(ExportRound(round_id=round_.id, force=True))

    before = send(GetStandings(tournament_id=tournament.id)).sections[0]
    assert before.stale, "round 1 went back to the manager since the standings arrived"

    # The same list, with the manager's numbers moved on: player 2 now leads.
    moved = (
        players_after_round_one()
        .replace(
            "1;Brunner Livia;WGM;;0;2447;01.06.1992;SUI;W;;;0;;0;;1;1;;;;;;1;",
            "1;Brunner Livia;WGM;;0;2447;01.06.1992;SUI;W;;;0;;0;;1;1,5;;;;;;2;",
        )
        .replace(
            "2;Dubois Martin;IM;;0;2359;10.11.1960;SUI;;;;0;;0;;0;2;;;;;;61;",
            "2;Dubois Martin;IM;;0;2359;10.11.1960;SUI;;;;0;;0;;2;3;;;;;;1;",
        )
    )
    outcome = send(ImportStandings(tournament_id=tournament.id, section_name="A", content=moved))

    assert outcome.after_round == 1
    assert outcome.players_updated == 14
    assert outcome.unknown_start_numbers == []
    after = send(GetStandings(tournament_id=tournament.id)).sections[0]
    assert not after.stale
    assert after.rows[0].name == "Dubois,Martin"
    assert after.rows[0].points == 2.0
    assert after.rows[1].tiebreaks == [1.5]
    section = session.scalars(select(Section)).one()
    assert section.standings_after_round == 1


def test_standings_need_a_section_and_a_player_list(send: Send, tournament: Tournament) -> None:
    with pytest.raises(NotFound):
        send(
            ImportStandings(
                tournament_id=tournament.id, section_name="A", content=players_after_round_one()
            )
        )

    import_round_one(send, tournament)
    with pytest.raises(ValidationFailed, match="Spielerdaten"):
        send(
            ImportStandings(
                tournament_id=tournament.id,
                section_name="A",
                content=read("pairings_round1_played.txt"),
            )
        )


def test_the_arbiter_names_the_tiebreak_columns(send: Send, tournament: Tournament) -> None:
    import_round_one(send, tournament)

    named = send(
        NameTiebreaks(
            tournament_id=tournament.id,
            section_name="A",
            names=["Buchholz", " Buchholz cut 1 ", "", ""],
        )
    )

    assert named.tiebreak_names == ["Buchholz", "Buchholz cut 1"]
    table = send(GetStandings(tournament_id=tournament.id)).sections[0]
    assert table.tiebreak_names == ["Buchholz", "Buchholz cut 1"]


def test_a_section_without_standings_is_not_listed(send: Send, tournament: Tournament) -> None:
    """A TRF names players but says nothing about ranks, whoever wrote it."""
    send(
        ImportRound(
            tournament_id=tournament.id,
            section_name="V",
            content=read("round3_paired.trf"),
        )
    )

    assert send(GetStandings(tournament_id=tournament.id)).sections == []
