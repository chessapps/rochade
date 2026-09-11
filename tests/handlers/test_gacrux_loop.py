"""The whole loop of a tournament Rochade pairs itself, in one test.

Enter players -> pair round 1 -> claims, a dispute, a forfeit -> release,
standings appear -> pair round 2 -> take it back, correct round 1 -> pair
again -> a late entry, an absence, a withdrawal -> the last round.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from rochade.features.games.claim_result import ClaimResult
from rochade.features.games.resolve_dispute import ResolveDispute
from rochade.features.games.set_result import SetResult
from rochade.features.pairing.pair_round import Absence, PairRound
from rochade.features.pairing.preview_pairing import PreviewPairing
from rochade.features.pairing.unpair_round import UnpairRound
from rochade.features.players.add_player import AddPlayer
from rochade.features.players.list_players import ListPlayers
from rochade.features.players.withdraw_player import WithdrawPlayer
from rochade.features.rounds.release_round import ReleaseRound
from rochade.features.sections.create_section import CreateSection
from rochade.features.standings.get_standings import GetStandings
from rochade.features.tournaments.get_tournament import GetTournament
from rochade.platform.errors import Conflict, RoundFrozen
from rochade.shared.enums import EventAction, GameResult, ResultState, RoundState
from rochade.shared.models import Game, GameEvent, Round, Section, Tournament
from rochade.trf import parse
from tests.conftest import Send
from tests.handlers.test_players import ROSTER, enter
from tests.handlers.test_result_flow import device_of

pytestmark = [pytest.mark.db, pytest.mark.manager("gacrux")]


def _round(session: Session, section: Section, number: int) -> Round:
    return session.scalars(
        select(Round).where(Round.section_id == section.id, Round.number == number)
    ).one()


def _boards(round_: Round) -> list[Game]:
    return sorted((g for g in round_.games if g.black_rank is not None), key=lambda g: g.board)


def test_the_native_loop_closes(send: Send, session: Session, tournament: Tournament) -> None:
    created = send(
        CreateSection(
            tournament_id=tournament.id, name="A", declared_rounds=3, top_board_colour="white"
        )
    )
    section = session.get(Section, created.section_id)
    assert section is not None
    enter(send, section)

    # --- preview, then pair round 1 ---------------------------------------
    plan = send(PreviewPairing(section_id=section.id))
    assert plan.can_pair
    assert plan.seeds is True
    assert plan.round_number == 1
    assert plan.players_in == 9
    assert len(plan.boards) == 4 and len(plan.byes) == 1
    # Seeded by rating: 1 v 5, 6 v 2, 3 v 7, 8 v 4 in FIDE order; 9 has the bye.
    assert [(b.white_rank, b.black_rank) for b in plan.boards] == [(1, 5), (6, 2), (3, 7), (8, 4)]
    assert plan.boards[0].white_name == "Baumann, Lukas"
    assert (plan.byes[0].start_rank, plan.byes[0].result, plan.byes[0].board) == (9, "U", 5)
    session.refresh(section)
    assert section.rounds == []  # the preview wrote nothing

    paired = send(PairRound(section_id=section.id))
    assert (paired.round_number, paired.boards, paired.byes, paired.seeded) == (1, 4, 1, True)
    assert paired.previous_round_closed is None
    round1 = _round(session, section, 1)
    assert round1.state is RoundState.OPEN
    assert round1.source_filename == "gacrux"
    assert parse(round1.source_trf).rounds_present == 0
    boards = _boards(round1)
    first = boards[0]
    assert (first.board, first.white_name, first.black_name) == (
        1,
        "Baumann, Lukas",
        "Fischer, Jonas",
    )
    bye = next(g for g in round1.games if g.black_rank is None)
    assert (bye.white_result, bye.state, bye.board) == ("U", ResultState.CONFIRMED, 5)

    detail = send(GetTournament(tournament_id=tournament.id))
    assert detail.sections[0].native is True
    assert detail.sections[0].rounds[0].boards == 4
    assert detail.sections[0].rounds[0].byes == 1

    # --- the hall enters results, one board goes wrong ---------------------
    phone_a, phone_b = device_of(tournament, "a"), device_of(tournament, "b")
    send(ClaimResult(game_id=boards[0].id, result=GameResult.WHITE_WIN), principal=phone_a)
    send(ClaimResult(game_id=boards[1].id, result=GameResult.DRAW), principal=phone_a)
    send(ClaimResult(game_id=boards[2].id, result=GameResult.WHITE_WIN), principal=phone_a)
    send(ClaimResult(game_id=boards[2].id, result=GameResult.BLACK_WIN), principal=phone_b)
    send(ResolveDispute(game_id=boards[2].id, result=GameResult.BLACK_WIN))
    # Nobody turned up on board 4.
    send(SetResult(game_id=boards[3].id, white_result="+", black_result="-"))

    with pytest.raises(Conflict, match="cannot be paired"):
        send(PairRound(section_id=section.id))

    # --- release: standings appear ----------------------------------------
    released = send(ReleaseRound(round_id=round1.id))
    assert released.standings_computed is True
    session.refresh(section)
    assert section.standings_after_round == 1
    table = send(GetStandings(tournament_id=tournament.id)).sections[0]
    assert table.after_round == 1
    assert table.tiebreak_names == ["BH/C1", "BH", "SB"]
    assert table.tiebreak_columns == 3
    # Four on a point: the bye (a virtual opponent under Swiss rules), the
    # two winners and the forfeit; the engine's order, not ours.
    assert [r.start_rank for r in table.rows][:5] == [9, 1, 7, 8, 2]
    assert all(r.points == 1.0 for r in table.rows[:4])
    assert {r.start_rank: r.points for r in table.rows}[5] == 0.0

    # --- a correction after release moves the table ------------------------
    send(SetResult(game_id=boards[0].id, white_result="=", black_result="="))
    table = send(GetStandings(tournament_id=tournament.id)).sections[0]
    assert {r.start_rank: r.points for r in table.rows}[1] == 0.5

    # --- pair round 2: round 1 closes ---------------------------------------
    paired2 = send(PairRound(section_id=section.id))
    assert paired2.previous_round_closed == 1
    session.refresh(round1)
    assert round1.state is RoundState.EXPORTED
    assert round1.exported_at is not None
    with pytest.raises(RoundFrozen, match="read-only"):
        send(SetResult(game_id=boards[0].id, white_result="1", black_result="0"))
    with pytest.raises(RoundFrozen, match="read-only"):
        send(ClaimResult(game_id=boards[0].id, result=GameResult.DRAW), principal=phone_a)
    round2 = _round(session, section, 2)
    first_pairing = [(g.white_rank, g.black_rank) for g in round2.games]

    # --- take it back, and the same pairing comes again --------------------
    undone = send(UnpairRound(round_id=round2.id))
    assert undone.previous_round_reopened == 1
    session.expire_all()
    assert session.get(Round, round2.id) is None
    round1 = _round(session, section, 1)
    assert round1.state is RoundState.CONFIRMED
    assert round1.exported_at is None
    send(PairRound(section_id=section.id))
    round2 = _round(session, section, 2)
    assert [(g.white_rank, g.black_rank) for g in round2.games] == first_pairing

    # --- results on it: it can no longer be unpaired -------------------------
    b2 = _boards(round2)
    send(ClaimResult(game_id=b2[0].id, result=GameResult.WHITE_WIN), principal=phone_a)
    with pytest.raises(Conflict, match="results have been entered") as excinfo:
        send(UnpairRound(round_id=round2.id))
    assert excinfo.value.details["boards"] == [1]
    for game in b2[1:]:
        send(SetResult(game_id=game.id, white_result="=", black_result="="))
    send(ReleaseRound(round_id=round2.id))

    # --- a late entry, an absence, a withdrawal ------------------------------
    late = send(AddPlayer(section_id=section.id, name="Late, Larry", rating=2400))
    assert late.start_rank == 10
    players = {p.name: p for p in send(ListPlayers(section_id=section.id)).players}
    send(WithdrawPlayer(player_id=players["Jenni, Rafael"].id))

    plan3 = send(PreviewPairing(section_id=section.id, absent=[Absence(start_rank=8, result="H")]))
    assert plan3.can_pair
    assert [p.name for p in plan3.withdrawn] == ["Jenni, Rafael"]
    assert plan3.players_in == 8
    assert {b.start_rank: b.result for b in plan3.byes} == {8: "H"}
    assert any(b.white_rank == 10 or b.black_rank == 10 for b in plan3.boards)

    paired3 = send(PairRound(section_id=section.id, absent=[Absence(start_rank=8, result="H")]))
    assert (paired3.boards, paired3.byes) == (4, 1)
    round3 = _round(session, section, 3)
    half = next(g for g in round3.games if g.black_rank is None)
    assert (half.white_rank, half.white_result, half.state) == (8, "H", ResultState.CONFIRMED)
    assert all(9 not in (g.white_rank, g.black_rank) for g in round3.games)
    # The engine saw the late entry with blank blocks for rounds 1 and 2.
    stored = parse(round3.source_trf)
    assert stored.player(10).rounds == {}
    assert stored.player(9).round(2) is not None

    for game in _boards(round3):
        send(SetResult(game_id=game.id, white_result="1", black_result="0"))
    send(ReleaseRound(round_id=round3.id))
    table = send(GetStandings(tournament_id=tournament.id)).sections[0]
    assert table.after_round == 3
    assert len(table.rows) == 10

    # --- the last declared round is played: nothing left to pair -----------
    with pytest.raises(Conflict, match="cannot be paired") as excinfo:
        send(PairRound(section_id=section.id))
    assert any("finished" in reason for reason in excinfo.value.details["reasons"])

    actions = [
        e.action
        for e in session.scalars(
            select(GameEvent)
            .where(GameEvent.section_id == section.id)
            .order_by(GameEvent.created_at)
        )
    ]
    assert actions.count(EventAction.ROUND_PAIRED) == 4
    assert actions.count(EventAction.ROUND_UNPAIRED) == 1
    assert actions.count(EventAction.STANDINGS_COMPUTED) >= 4


def test_a_forced_release_holds_the_table_and_the_next_pairing(
    send: Send, session: Session, tournament: Tournament
) -> None:
    created = send(CreateSection(tournament_id=tournament.id, name="A", declared_rounds=3))
    section = session.get(Section, created.section_id)
    assert section is not None
    enter(send, section, ROSTER[:4])
    send(PairRound(section_id=section.id))
    round1 = _round(session, section, 1)
    boards = _boards(round1)
    send(SetResult(game_id=boards[0].id, white_result="1", black_result="0"))

    released = send(ReleaseRound(round_id=round1.id, force=True))
    assert released.standings_computed is False
    assert "round 1 board 2" in released.standings_note
    session.refresh(section)
    assert section.standings_after_round is None

    plan = send(PreviewPairing(section_id=section.id))
    assert not plan.can_pair
    assert "boards without a confirmed result" in plan.blocked_by[0]

    # The arbiter fills the board in; the table follows and the pairing is unblocked.
    send(SetResult(game_id=boards[1].id, white_result="0", black_result="1"))
    session.refresh(section)
    assert section.standings_after_round == 1
    assert send(PreviewPairing(section_id=section.id)).can_pair
