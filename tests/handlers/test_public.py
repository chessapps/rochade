"""What the public sees of a tournament: only once published, and never a claim."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from rochade.features.games.claim_result import ClaimResult
from rochade.features.games.set_result import SetResult
from rochade.features.imports.import_round import ImportRound
from rochade.features.public.get_public_player import GetPublicPlayer
from rochade.features.public.get_public_round import GetPublicRound
from rochade.features.public.get_public_standings import GetPublicStandings
from rochade.features.public.get_public_tournament import GetPublicTournament
from rochade.features.public.list_public_tournaments import ListPublicTournaments
from rochade.features.public.shown import Shown, shown_result
from rochade.features.rounds.release_round import ReleaseRound
from rochade.features.tournaments.publish_tournament import PublishTournament
from rochade.platform.errors import NotFound
from rochade.platform.http import ANONYMOUS
from rochade.platform.mediator import Principal
from rochade.shared.enums import GameResult, PrincipalKind, RoundState
from rochade.shared.models import Game, Round, Tournament
from tests.conftest import Send

pytestmark = pytest.mark.db

SLUG = "rochade-open-2026"


@pytest.fixture
def round_(send: Send, session: Session, tournament: Tournament, round1_text: str) -> Round:
    send(ImportRound(tournament_id=tournament.id, section_name="A", content=round1_text))
    return session.scalars(select(Round)).one()


def device_of(tournament: Tournament, name: str = "phone-1") -> Principal:
    return Principal(
        kind=PrincipalKind.DEVICE,
        subject=f"device:{name}",
        device_id=uuid.uuid4(),
        tournament_id=tournament.id,
    )


def publish(send: Send, tournament: Tournament) -> None:
    send(PublishTournament(tournament_id=tournament.id, published=True))


def test_an_unpublished_tournament_is_not_there(
    send: Send, tournament: Tournament, round_: Round
) -> None:
    section_id = round_.section_id
    assert send(ListPublicTournaments(), principal=ANONYMOUS) == []
    # The slug exists once the tournament was published and hidden again; a
    # hidden tournament answers like one that never was.
    publish(send, tournament)
    send(PublishTournament(tournament_id=tournament.id, published=False))
    for query in (
        GetPublicTournament(slug=SLUG),
        GetPublicRound(slug=SLUG, section_id=section_id, number=1),
        GetPublicStandings(slug=SLUG, section_id=section_id),
        GetPublicPlayer(slug=SLUG, section_id=section_id, start_rank=1),
    ):
        with pytest.raises(NotFound):
            send(query, principal=ANONYMOUS)


def test_the_front_door_lists_a_published_tournament(
    send: Send, tournament: Tournament, round_: Round
) -> None:
    publish(send, tournament)
    listed = send(ListPublicTournaments(), principal=ANONYMOUS)
    assert [t.slug for t in listed] == [SLUG]
    assert listed[0].name == "Rochade Open 2026"
    section = listed[0].sections[0]
    assert (section.name, section.rounds_held, section.in_play) == ("A", 1, True)

    detail = send(GetPublicTournament(slug=SLUG), principal=ANONYMOUS)
    assert detail.slug == SLUG
    assert len(detail.sections) == 1
    assert detail.sections[0].players == 8
    assert [(r.number, r.state, r.boards, r.results_in) for r in detail.sections[0].rounds] == [
        (1, RoundState.OPEN, 4, 0)
    ]


def test_results_show_as_preliminary_then_confirmed_and_claims_stay_private(
    send: Send, tournament: Tournament, round_: Round
) -> None:
    publish(send, tournament)
    boards = sorted(round_.games, key=lambda g: g.board)
    first, second, third = boards[0], boards[1], boards[2]

    send(
        ClaimResult(game_id=first.id, result=GameResult.WHITE_WIN), principal=device_of(tournament)
    )
    send(SetResult(game_id=second.id, white_result="=", black_result="="))
    send(
        ClaimResult(game_id=third.id, result=GameResult.BLACK_WIN),
        principal=device_of(tournament, "phone-1"),
    )
    send(
        ClaimResult(game_id=third.id, result=GameResult.WHITE_WIN),
        principal=device_of(tournament, "phone-2"),
    )

    shown = send(
        GetPublicRound(slug=SLUG, section_id=round_.section_id, number=1), principal=ANONYMOUS
    )
    by_board = {b.board: b for b in shown.boards}
    assert (by_board[1].result, by_board[1].state) == ("1-0", Shown.PRELIMINARY)
    assert (by_board[2].result, by_board[2].state) == ("½-½", Shown.CONFIRMED)
    # The disputed board: the first claim stands, marked preliminary, and
    # nothing in the answer carries the second one.
    assert (by_board[3].result, by_board[3].state) == ("0-1", Shown.PRELIMINARY)
    assert "disputed" not in by_board[3].model_dump()
    assert (by_board[4].result, by_board[4].state) == ("", Shown.PENDING)

    assert by_board[1].white.name == "Baumann, Lukas"
    assert (by_board[1].white.title, by_board[1].white.rating) == ("FM", 2201)


def test_a_player_page_lists_every_game_from_their_side(
    send: Send, tournament: Tournament, round_: Round
) -> None:
    publish(send, tournament)
    boards = sorted(round_.games, key=lambda g: g.board)
    send(SetResult(game_id=boards[0].id, white_result="0", black_result="1"))

    black = send(
        GetPublicPlayer(
            slug=SLUG, section_id=round_.section_id, start_rank=boards[0].black_rank or 0
        ),
        principal=ANONYMOUS,
    )
    assert black.name == boards[0].black_name
    assert len(black.games) == 1
    game = black.games[0]
    assert (game.round_number, game.board, game.colour.value if game.colour else None) == (
        1,
        1,
        "black",
    )
    assert game.opponent is not None and game.opponent.name == "Baumann, Lukas"
    assert (game.result, game.score, game.state) == ("0-1", 1.0, Shown.CONFIRMED)
    # No standings were imported for a Vega tournament's first round.
    assert (black.rank, black.points) == (None, None)

    with pytest.raises(NotFound):
        send(
            GetPublicPlayer(slug=SLUG, section_id=round_.section_id, start_rank=99),
            principal=ANONYMOUS,
        )


def test_a_section_id_only_answers_under_its_own_tournament(
    send: Send, session: Session, tournament: Tournament, round_: Round
) -> None:
    publish(send, tournament)
    other = Tournament(name="Other", manager="vega", slug="other", published=True)
    session.add(other)
    session.commit()
    with pytest.raises(NotFound, match="section not found"):
        send(
            GetPublicRound(slug="other", section_id=round_.section_id, number=1),
            principal=ANONYMOUS,
        )


def test_changing_the_slug_moves_the_tournament(
    send: Send, tournament: Tournament, round_: Round
) -> None:
    publish(send, tournament)
    send(PublishTournament(tournament_id=tournament.id, published=True, slug="moved"))
    with pytest.raises(NotFound):
        send(GetPublicTournament(slug=SLUG), principal=ANONYMOUS)
    assert send(GetPublicTournament(slug="moved"), principal=ANONYMOUS).slug == "moved"


def test_a_released_round_is_confirmed_throughout(
    send: Send, tournament: Tournament, round_: Round
) -> None:
    publish(send, tournament)
    for game in round_.games:
        if game.black_rank is not None:
            send(SetResult(game_id=game.id, white_result="1", black_result="0"))
    send(ReleaseRound(round_id=round_.id))

    shown = send(
        GetPublicRound(slug=SLUG, section_id=round_.section_id, number=1), principal=ANONYMOUS
    )
    assert shown.state is RoundState.CONFIRMED
    assert {b.state for b in shown.boards if b.black is not None} == {Shown.CONFIRMED}
    detail = send(GetPublicTournament(slug=SLUG), principal=ANONYMOUS)
    summary = detail.sections[0].rounds[0]
    assert (summary.results_in, summary.boards) == (4, 4)
    assert summary.updated_at is not None


@pytest.mark.parametrize(
    ("white", "black", "black_rank", "shown"),
    [
        ("1", "0", 2, "1-0"),
        ("=", "=", 2, "½-½"),
        ("0", "1", 2, "0-1"),
        ("W", "L", 2, "1-0"),
        ("+", "-", 2, "+:-"),
        ("+", " ", 2, "+:-"),
        ("1", " ", 2, "1-0"),
        ("-", "+", 2, "-:+"),
        ("-", "-", 2, "-:-"),
        (" ", " ", 2, ""),
        ("U", " ", None, "1"),
        ("H", " ", None, "½"),
        ("Z", " ", None, "0"),
        (" ", " ", None, ""),
    ],
)
def test_how_a_result_is_printed(
    white: str, black: str, black_rank: int | None, shown: str
) -> None:
    game = Game(
        board=1,
        white_rank=1,
        white_name="A",
        black_rank=black_rank,
        black_name="B" if black_rank else None,
        white_result=white,
        black_result=black,
    )
    assert shown_result(game) == shown


def test_standings_come_back_empty_until_the_manager_gave_some(
    send: Send, tournament: Tournament, round_: Round
) -> None:
    publish(send, tournament)
    table = send(GetPublicStandings(slug=SLUG, section_id=round_.section_id), principal=ANONYMOUS)
    assert table.section_name == "A"
    assert table.rows == []
    assert table.rounds_held == 1
