"""Every native use case is scoped to its tournament.

A section, player or round id is a capability only inside the tournament it
belongs to: an arbiter of another event, holding a valid id, gets a 403 and
nothing else. One parametrised test over every new message, so a message
added without a scope cannot slip past.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from rochade.features.pairing.compute_standings import ComputeStandings
from rochade.features.pairing.pair_round import PairRound
from rochade.features.pairing.preview_pairing import PreviewPairing
from rochade.features.pairing.unpair_round import UnpairRound
from rochade.features.players.add_player import AddPlayer
from rochade.features.players.list_players import ListPlayers
from rochade.features.players.update_player import UpdatePlayer
from rochade.features.players.withdraw_player import ReinstatePlayer, WithdrawPlayer
from rochade.features.sections.create_section import CreateSection
from rochade.platform.errors import Forbidden
from rochade.platform.mediator import Message, Principal
from rochade.shared.enums import PrincipalKind, Role
from rochade.shared.models import Section, Tournament, TournamentMember
from tests.conftest import Send
from tests.handlers.test_players import ROSTER, enter

pytestmark = [pytest.mark.db, pytest.mark.manager("gacrux")]

STRANGER = Principal(kind=PrincipalKind.STAFF, subject="stranger@example.test")


@pytest.fixture
def ids(send: Send, session: Session, tournament: Tournament) -> dict[str, object]:
    created = send(CreateSection(tournament_id=tournament.id, name="A", declared_rounds=3))
    section = session.get(Section, created.section_id)
    assert section is not None
    enter(send, section, ROSTER[:4])
    paired = send(PairRound(section_id=section.id))
    player = section.players[0]
    # The stranger runs a tournament of their own, so they are staff with a role somewhere.
    other = Tournament(name="Elsewhere", manager="gacrux")
    session.add(other)
    session.flush()
    session.add(TournamentMember(tournament_id=other.id, subject=STRANGER.subject, role=Role.OWNER))
    session.commit()
    return {
        "tournament": tournament.id,
        "section": section.id,
        "player": player.id,
        "round": paired.round_id,
    }


def _messages(ids: dict[str, object]) -> list[Message]:
    section, player, round_ = ids["section"], ids["player"], ids["round"]
    return [
        CreateSection(tournament_id=ids["tournament"], name="B", declared_rounds=3),  # type: ignore[arg-type]
        ListPlayers(section_id=section),  # type: ignore[arg-type]
        AddPlayer(section_id=section, name="Intruder, Ivan"),  # type: ignore[arg-type]
        UpdatePlayer(player_id=player, name="Someone, Else"),  # type: ignore[arg-type]
        WithdrawPlayer(player_id=player),  # type: ignore[arg-type]
        ReinstatePlayer(player_id=player),  # type: ignore[arg-type]
        PreviewPairing(section_id=section),  # type: ignore[arg-type]
        PairRound(section_id=section),  # type: ignore[arg-type]
        ComputeStandings(section_id=section),  # type: ignore[arg-type]
        UnpairRound(round_id=round_),  # type: ignore[arg-type]
    ]


def test_a_member_of_another_tournament_is_refused_everywhere(
    send: Send, ids: dict[str, object]
) -> None:
    for message in _messages(ids):
        with pytest.raises(Forbidden):
            send(message, principal=STRANGER)


def test_an_assistant_may_read_but_not_write(
    send: Send, session: Session, tournament: Tournament, ids: dict[str, object]
) -> None:
    helper = Principal(kind=PrincipalKind.STAFF, subject="helper@example.test")
    session.add(
        TournamentMember(tournament_id=tournament.id, subject=helper.subject, role=Role.ASSISTANT)
    )
    session.commit()
    listed = send(ListPlayers(section_id=ids["section"]), principal=helper)  # type: ignore[arg-type]
    assert len(listed.players) == 4
    for message in _messages(ids)[2:]:
        with pytest.raises(Forbidden):
            send(message, principal=helper)
