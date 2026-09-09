"""Re-importing a round that is already open.

The awkward case the plan calls out: a late entry arrives, the arbiter re-pairs
in Vega, and the new file has different boards while we already hold entered
results. Allowed, but never silent.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from rochade.features.games.claim_result import ClaimResult
from rochade.features.imports.import_round import ImportRound
from rochade.features.imports.preview_import import PreviewImport
from rochade.shared.enums import EventAction, GameResult, ResultState
from rochade.shared.models import GameEvent, Round, Tournament
from tests.conftest import Send
from tests.handlers.test_result_flow import device_of

pytestmark = pytest.mark.db


def _repair(text: str, swaps: dict[int, tuple[int, str]]) -> str:
    """Rewrite round 1 opponents/colours to simulate a Vega re-pair."""
    from rochade.trf import Dialect, parse, serialize

    trf = parse(text)
    for rank, (opponent, colour) in swaps.items():
        entry = trf.player(rank).rounds[1]
        entry.opponent = opponent
        entry.colour = type(entry.colour)(colour)
    return serialize(trf, Dialect.TRF16)


def test_a_claim_survives_a_repair_that_keeps_the_pair(
    send: Send, session: Session, tournament: Tournament, round1_text: str
) -> None:
    send(ImportRound(tournament_id=tournament.id, section_name="A", content=round1_text))
    round_ = session.scalars(select(Round)).one()
    board = next(g for g in round_.games if (g.white_rank, g.black_rank) == (1, 5))
    send(
        ClaimResult(game_id=board.id, result=GameResult.WHITE_WIN),
        principal=device_of(tournament),
    )

    # Same pairing, re-issued. Everything carries.
    result = send(ImportRound(tournament_id=tournament.id, section_name="A", content=round1_text))
    assert result.claims_carried == 1
    assert result.claims_dropped == 0

    reloaded = session.scalars(select(Round)).one()
    carried = next(g for g in reloaded.games if (g.white_rank, g.black_rank) == (1, 5))
    assert carried.state is ResultState.CLAIMED
    assert carried.white_result == "1"


def test_a_claim_is_mirrored_when_the_repair_swaps_colours(
    send: Send, session: Session, tournament: Tournament, round1_text: str
) -> None:
    send(ImportRound(tournament_id=tournament.id, section_name="A", content=round1_text))
    round_ = session.scalars(select(Round)).one()
    board = next(g for g in round_.games if (g.white_rank, g.black_rank) == (1, 5))
    send(
        ClaimResult(game_id=board.id, result=GameResult.WHITE_WIN),
        principal=device_of(tournament),
    )

    swapped = _repair(round1_text, {1: (5, "b"), 5: (1, "w")})
    result = send(ImportRound(tournament_id=tournament.id, section_name="A", content=swapped))
    assert result.claims_carried == 1

    reloaded = session.scalars(select(Round)).one()
    game = next(g for g in reloaded.games if {g.white_rank, g.black_rank} == {1, 5})
    assert (game.white_rank, game.black_rank) == (5, 1)
    # Player 1 still won: the same outcome, told from the other side.
    assert (game.white_result, game.black_result) == ("0", "1")
    assert game.state is ResultState.CLAIMED


def test_a_claim_whose_pair_no_longer_exists_is_dropped_and_reported(
    send: Send, session: Session, tournament: Tournament, round1_text: str
) -> None:
    send(ImportRound(tournament_id=tournament.id, section_name="A", content=round1_text))
    round_ = session.scalars(select(Round)).one()
    board = next(g for g in round_.games if (g.white_rank, g.black_rank) == (1, 5))
    send(
        ClaimResult(game_id=board.id, result=GameResult.WHITE_WIN),
        principal=device_of(tournament),
    )

    # 1 now plays 6 and 5 plays 2; the claimed pair is gone.
    repaired = _repair(round1_text, {1: (6, "w"), 6: (1, "b"), 5: (2, "w"), 2: (5, "b")})

    plan = send(PreviewImport(tournament_id=tournament.id, section_name="A", content=repaired))
    assert len(plan.claims_dropped) == 1
    assert plan.claims_dropped[0].white_name == "Baumann, Lukas"
    assert any("will be dropped" in w for w in plan.warnings)

    result = send(ImportRound(tournament_id=tournament.id, section_name="A", content=repaired))
    assert result.claims_dropped == 1

    reloaded = session.scalars(select(Round)).one()
    assert all(g.state is ResultState.EMPTY for g in reloaded.games)

    # The dropped claim stays in the audit log.
    events = session.scalars(
        select(GameEvent).where(GameEvent.action == EventAction.ROUND_IMPORTED)
    ).all()
    assert events[-1].payload["claims_dropped"][0]["white_name"] == "Baumann, Lukas"
    claims = session.scalars(
        select(GameEvent).where(GameEvent.action == EventAction.RESULT_CLAIMED)
    ).all()
    assert len(claims) == 1


def test_a_late_entrant_is_reported_as_added(
    send: Send, session: Session, tournament: Tournament, round1_text: str, round3_text: str
) -> None:
    send(ImportRound(tournament_id=tournament.id, section_name="A", content=round1_text))
    # The messy fixture has a ninth player the first file did not.
    with_late_entry = _first_round_only(round3_text)
    plan = send(
        PreviewImport(tournament_id=tournament.id, section_name="A", content=with_late_entry)
    )
    assert [p.name for p in plan.players_added] == ["Jenni, Rafael"]
    assert plan.players_removed == []


def _first_round_only(text: str) -> str:
    from rochade.trf import columns

    lines = []
    for line in text.split("\r\n"):
        if line.startswith("001"):
            line = line[: columns.round_base(2)].rstrip()
        lines.append(line)
    return "\r\n".join(lines)
