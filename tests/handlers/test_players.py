"""Sections and players of a tournament Rochade pairs itself."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from rochade.features.imports.import_round import ImportRound
from rochade.features.pairing.pair_round import PairRound
from rochade.features.players.add_player import AddPlayer
from rochade.features.players.list_players import ListPlayers
from rochade.features.players.update_player import UpdatePlayer
from rochade.features.players.withdraw_player import ReinstatePlayer, WithdrawPlayer
from rochade.features.sections.create_section import CreateSection
from rochade.platform.errors import Conflict, ValidationFailed
from rochade.shared.enums import EventAction
from rochade.shared.models import GameEvent, Section, Tournament
from tests.conftest import Send

pytestmark = [pytest.mark.db, pytest.mark.manager("gacrux")]

ROSTER = [
    ("Baumann, Lukas", 2201, "FM"),
    ("Chen, Wei", 2150, ""),
    ("Dubois, Elise", 2098, "WFM"),
    ("Egger, Tobias", 2044, ""),
    ("Fischer, Jonas", 1987, ""),
    ("Gruber, Sarah", 1922, ""),
    ("Huber, Marco", 1870, ""),
    ("Iten, Nadia", 1804, ""),
    ("Jenni, Rafael", 1755, ""),
]


@pytest.fixture
def section(send: Send, session: Session, tournament: Tournament) -> Section:
    created = send(CreateSection(tournament_id=tournament.id, name="A", declared_rounds=5))
    return session.get(Section, created.section_id)  # type: ignore[return-value]


def enter(send: Send, section: Section, roster: list[tuple[str, int, str]] = ROSTER) -> None:
    for name, rating, title in roster:
        send(AddPlayer(section_id=section.id, name=name, rating=rating, title=title))


# --- sections ---------------------------------------------------------------


def test_a_section_is_created_with_its_settings(
    send: Send, session: Session, tournament: Tournament
) -> None:
    created = send(
        CreateSection(
            tournament_id=tournament.id,
            name="Open",
            declared_rounds=7,
            tiebreaks=["pts", "bh", "sb"],
            top_board_colour="black",
        )
    )
    assert created.tiebreaks == ["PTS", "BH", "SB"]
    assert created.top_board_colour == "black"
    assert created.drawn_by_lot is False
    section = session.get(Section, created.section_id)
    assert section is not None
    assert section.manager == "gacrux"
    assert section.declared_rounds == 7
    assert section.tiebreak_names == ["PTS", "BH", "SB"]
    assert section.top_board_colour == "black"


def test_the_top_colour_is_drawn_when_left_open(send: Send, tournament: Tournament) -> None:
    created = send(CreateSection(tournament_id=tournament.id, name="A", declared_rounds=5))
    assert created.drawn_by_lot is True
    assert created.top_board_colour in ("white", "black")
    assert created.tiebreaks == ["PTS", "BH/C1", "BH", "SB"]


def test_section_settings_are_validated(send: Send, tournament: Tournament) -> None:
    with pytest.raises(ValidationFailed, match="must be PTS"):
        send(
            CreateSection(
                tournament_id=tournament.id, name="A", declared_rounds=5, tiebreaks=["BH"]
            )
        )
    with pytest.raises(ValidationFailed, match="unknown tie-break"):
        send(
            CreateSection(
                tournament_id=tournament.id, name="A", declared_rounds=5, tiebreaks=["PTS", "XX"]
            )
        )
    send(CreateSection(tournament_id=tournament.id, name="A", declared_rounds=5))
    with pytest.raises(Conflict, match="already exists"):
        send(CreateSection(tournament_id=tournament.id, name="A", declared_rounds=5))


@pytest.mark.manager("vega")
def test_a_managers_tournament_gets_its_sections_from_imports(
    send: Send, tournament: Tournament
) -> None:
    with pytest.raises(Conflict, match="arrive with its first export"):
        send(CreateSection(tournament_id=tournament.id, name="A", declared_rounds=5))


# --- players ----------------------------------------------------------------


def test_players_are_listed_in_entry_order_until_seeded(send: Send, section: Section) -> None:
    enter(send, section, [("Zed, Zoe", 1500, ""), ("Abt, Ann", 2100, "")])
    listed = send(ListPlayers(section_id=section.id))
    assert listed.editable is True
    assert listed.seeded is False
    assert [(p.start_rank, p.name) for p in listed.players] == [(1, "Zed, Zoe"), (2, "Abt, Ann")]


def test_a_name_is_unique_within_the_section(send: Send, section: Section) -> None:
    send(AddPlayer(section_id=section.id, name="Müller, Anna"))
    with pytest.raises(Conflict, match="already in the section"):
        send(AddPlayer(section_id=section.id, name="  müller,  ANNA "))


def test_fields_are_normalised(send: Send, session: Session, section: Section) -> None:
    added = send(
        AddPlayer(
            section_id=section.id,
            name=" Müller,  Anna ",
            title="wfm",
            rating=0,
            federation="sui",
            sex="W",
            birth_date="2001/07/09",
            fide_id="1300003",
        )
    )
    assert added.name == "Müller, Anna"
    assert added.title == "WFM"
    assert added.rating is None
    assert added.federation == "SUI"
    assert added.sex == "w"
    event = session.scalars(
        select(GameEvent).where(GameEvent.action == EventAction.PLAYER_ADDED)
    ).one()
    assert event.payload["late_entry"] is False


@pytest.mark.manager("vega")
def test_a_managers_list_is_read_only(
    send: Send, session: Session, tournament: Tournament, round1_text: str
) -> None:
    send(ImportRound(tournament_id=tournament.id, section_name="A", content=round1_text))
    section = session.scalars(select(Section)).one()
    listed = send(ListPlayers(section_id=section.id))
    assert listed.editable is False
    assert len(listed.players) == 8
    with pytest.raises(Conflict, match="come from its pairing program"):
        send(AddPlayer(section_id=section.id, name="Late, Larry"))


def test_a_player_can_be_corrected(send: Send, section: Section) -> None:
    added = send(AddPlayer(section_id=section.id, name="Muller, Anna", rating=1900))
    updated = send(
        UpdatePlayer(player_id=added.id, name="Müller, Anna", rating=1950, federation="SUI")
    )
    assert (updated.name, updated.rating, updated.federation) == ("Müller, Anna", 1950, "SUI")


def test_a_rename_is_refused_once_the_player_has_sat_at_a_board(
    send: Send, section: Section
) -> None:
    enter(send, section)
    send(PairRound(section_id=section.id))
    listed = send(ListPlayers(section_id=section.id))
    assert listed.seeded is True
    first = listed.players[0]
    # Everything but the name still moves.
    send(UpdatePlayer(player_id=first.id, name=first.name, rating=2222))
    with pytest.raises(Conflict, match="already been on a board"):
        send(UpdatePlayer(player_id=first.id, name="Someone, Else"))


def test_seeding_orders_by_rating_title_then_name(send: Send, section: Section) -> None:
    enter(
        send,
        section,
        [
            ("Weak, Will", 1500, ""),
            ("Untitled, Ulla", 2000, ""),
            ("Master, Mia", 2000, "IM"),
            ("Fide, Finn", 2000, "FM"),
            ("Nobody, Nils", 0, ""),
            ("Strong, Sam", 2300, ""),
        ],
    )
    send(PairRound(section_id=section.id))
    listed = send(ListPlayers(section_id=section.id))
    assert [p.name for p in listed.players] == [
        "Strong, Sam",
        "Master, Mia",
        "Fide, Finn",
        "Untitled, Ulla",
        "Weak, Will",
        "Nobody, Nils",
    ]
    assert [p.start_rank for p in listed.players] == [1, 2, 3, 4, 5, 6]


def test_a_late_entry_takes_the_next_number(send: Send, session: Session, section: Section) -> None:
    enter(send, section)
    send(PairRound(section_id=section.id))
    late = send(AddPlayer(section_id=section.id, name="Late, Larry", rating=2400))
    assert late.start_rank == 10
    event = session.scalars(
        select(GameEvent).where(
            GameEvent.action == EventAction.PLAYER_ADDED, GameEvent.round_number == 1
        )
    ).one()
    assert event.payload["late_entry"] is True


def test_withdrawal_and_return(send: Send, section: Section) -> None:
    enter(send, section)
    send(PairRound(section_id=section.id))
    listed = send(ListPlayers(section_id=section.id))
    nine = listed.players[-1]

    with pytest.raises(Conflict, match="already paired"):
        send(WithdrawPlayer(player_id=nine.id, from_round=1))
    gone = send(WithdrawPlayer(player_id=nine.id))
    assert gone.withdrawn_from_round == 2
    with pytest.raises(Conflict, match="already withdrawn"):
        send(WithdrawPlayer(player_id=nine.id, from_round=3))

    back = send(ReinstatePlayer(player_id=nine.id))
    assert back.withdrawn_from_round is None
    with pytest.raises(Conflict, match="has not been withdrawn"):
        send(ReinstatePlayer(player_id=nine.id))
