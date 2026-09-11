"""The rules around a pairing, one at a time."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from rochade.features.games.set_result import SetResult
from rochade.features.imports.import_round import ImportRound
from rochade.features.pairing import pair_round as pair_module
from rochade.features.pairing.compute_standings import ComputeStandings
from rochade.features.pairing.pair_round import Absence, PairRound
from rochade.features.pairing.preview_pairing import PreviewPairing
from rochade.features.pairing.unpair_round import UnpairRound
from rochade.features.players.add_player import AddPlayer
from rochade.features.players.withdraw_player import WithdrawPlayer
from rochade.features.rounds.release_round import ReleaseRound
from rochade.features.sections.create_section import CreateSection
from rochade.gacrux import EngineError
from rochade.platform.errors import Conflict, ValidationFailed
from rochade.shared.enums import RoundState
from rochade.shared.models import Round, Section, Tournament
from tests.conftest import Send
from tests.handlers.test_players import ROSTER, enter

pytestmark = [pytest.mark.db, pytest.mark.manager("gacrux")]


@pytest.fixture
def section(send: Send, session: Session, tournament: Tournament) -> Section:
    created = send(CreateSection(tournament_id=tournament.id, name="A", declared_rounds=5))
    return session.get(Section, created.section_id)  # type: ignore[return-value]


def _finish(send: Send, round_: Round) -> None:
    for game in round_.games:
        if game.black_rank is not None:
            send(SetResult(game_id=game.id, white_result="1", black_result="0"))
    send(ReleaseRound(round_id=round_.id))


def test_fewer_than_two_players_cannot_be_paired(send: Send, section: Section) -> None:
    plan = send(PreviewPairing(section_id=section.id))
    assert "at least two players" in plan.blocked_by[0]
    send(AddPlayer(section_id=section.id, name="Only, One"))
    with pytest.raises(Conflict) as excinfo:
        send(PairRound(section_id=section.id))
    assert "at least two players" in excinfo.value.details["reasons"][0]


def test_two_players_make_one_board(send: Send, session: Session, section: Section) -> None:
    enter(send, section, ROSTER[:2])
    paired = send(PairRound(section_id=section.id))
    assert (paired.boards, paired.byes) == (1, 0)


def test_an_open_round_blocks_the_next_pairing(send: Send, section: Section) -> None:
    enter(send, section, ROSTER[:4])
    send(PairRound(section_id=section.id))
    plan = send(PreviewPairing(section_id=section.id))
    assert plan.round_number == 2
    assert "still open for entry" in plan.blocked_by[0]


def test_absences_are_checked(send: Send, session: Session, section: Section) -> None:
    enter(send, section, ROSTER[:4])
    plan = send(PreviewPairing(section_id=section.id, absent=[Absence(start_rank=99)]))
    assert "no player has start number 99" in plan.blocked_by

    send(PairRound(section_id=section.id, absent=[Absence(start_rank=4, result="Z")]))
    round1 = session.scalars(select(Round)).one()
    byes = [g for g in round1.games if g.black_rank is None]
    # Three left: one board, a pairing-allocated bye, and the absence itself.
    assert [(g.white_rank, g.white_result) for g in byes] == [(3, "U"), (4, "Z")]
    assert len(round1.games) == 3


def test_a_withdrawn_player_is_out_and_a_returning_one_is_in(
    send: Send, session: Session, section: Section
) -> None:
    enter(send, section, ROSTER[:4])
    send(PairRound(section_id=section.id))
    round1 = session.scalars(select(Round)).one()
    _finish(send, round1)
    players = {p.name: p for p in section.players}
    send(WithdrawPlayer(player_id=players["Egger, Tobias"].id))

    plan = send(PreviewPairing(section_id=section.id))
    assert [p.name for p in plan.withdrawn] == ["Egger, Tobias"]
    assert plan.players_in == 3
    assert len(plan.byes) == 1 and plan.byes[0].result == "U"
    assert "even field" in plan.warnings[0]


def test_an_engine_failure_writes_nothing(
    send: Send, session: Session, section: Section, monkeypatch: pytest.MonkeyPatch
) -> None:
    enter(send, section, ROSTER[:4])

    def broken(*args: object, **kwargs: object) -> object:
        raise EngineError("simulated", code=599, errors=["the engine is on fire"])

    monkeypatch.setattr(pair_module, "pair", broken)
    with pytest.raises(ValidationFailed, match="could not pair round 1") as excinfo:
        send(PairRound(section_id=section.id))
    assert excinfo.value.details["engine_errors"] == ["the engine is on fire"]
    session.expire_all()
    assert session.scalars(select(Round)).all() == []
    # And the provisional start ranks were not touched.
    assert [p.name for p in sorted(section.players, key=lambda p: p.start_rank)] == [
        n for n, _, _ in ROSTER[:4]
    ]


def test_only_the_newest_open_round_can_be_unpaired(
    send: Send, session: Session, section: Section
) -> None:
    enter(send, section, ROSTER[:4])
    send(PairRound(section_id=section.id))
    round1 = session.scalars(select(Round)).one()
    _finish(send, round1)
    with pytest.raises(Conflict, match="has been released"):
        send(UnpairRound(round_id=round1.id))
    send(PairRound(section_id=section.id))
    with pytest.raises(Conflict, match="not the newest"):
        send(UnpairRound(round_id=round1.id))


@pytest.mark.manager("vega")
def test_an_imported_round_is_not_unpaired_here(
    send: Send, session: Session, tournament: Tournament, round1_text: str
) -> None:
    send(ImportRound(tournament_id=tournament.id, section_name="A", content=round1_text))
    round_ = session.scalars(select(Round)).one()
    with pytest.raises(Conflict, match="re-pair it there"):
        send(UnpairRound(round_id=round_.id))
    section = session.scalars(select(Section)).one()
    with pytest.raises(Conflict, match="come from its pairing program"):
        send(ComputeStandings(section_id=section.id))


def test_standings_can_be_recomputed_on_demand(
    send: Send, session: Session, section: Section
) -> None:
    enter(send, section, ROSTER[:4])
    before = send(ComputeStandings(section_id=section.id))
    assert before.computed is False
    assert "no round" in before.reason

    send(PairRound(section_id=section.id))
    round1 = session.scalars(select(Round)).one()
    _finish(send, round1)
    again = send(ComputeStandings(section_id=section.id))
    assert again.computed is True
    assert again.after_round == 1
    assert [r.rank for r in again.standings.rows] == [1, 1, 3, 3]


def test_a_pairing_stores_the_engines_input_and_output(
    send: Send, session: Session, section: Section
) -> None:
    from rochade.shared.enums import EventAction
    from rochade.shared.models import GameEvent

    enter(send, section, ROSTER[:4])
    send(PairRound(section_id=section.id))
    event = session.scalars(
        select(GameEvent).where(GameEvent.action == EventAction.ROUND_PAIRED)
    ).one()
    # The top colour was drawn by lot at creation, so compare colour-blind.
    assert sorted(sorted(p) for p in event.payload["engine_pairs"]) == [[1, 3], [2, 4]]
    assert event.payload["seeded"] is True
    assert event.payload["reordered"] is False  # entered in rating order already
    assert event.payload["top_board_colour"] in ("white", "black")
    round_ = session.scalars(select(Round)).one()
    assert round_.state is RoundState.OPEN
    assert "001    1" in round_.source_trf
