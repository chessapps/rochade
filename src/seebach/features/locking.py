"""Row locks for the two places concurrency actually bites.

Claims arrive from many phones at once, and a release or export must not run
while a claim is landing. Both are solved by taking the round row first, so the
lock is held for the whole of one board's transition.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select

from seebach.platform.errors import NotFound, RoundFrozen
from seebach.platform.mediator import Context
from seebach.shared.enums import RoundState
from seebach.shared.models import Game, Round


def lock_round(ctx: Context, round_id: uuid.UUID) -> Round:
    round_ = ctx.session.scalar(select(Round).where(Round.id == round_id).with_for_update())
    if round_ is None:
        raise NotFound("round not found", round_id=str(round_id))
    return round_


def lock_round_of_game(ctx: Context, game_id: uuid.UUID) -> tuple[Round, Game]:
    """Take the round lock *before* reading the game, so ordering is consistent."""
    round_id = ctx.session.scalar(select(Game.round_id).where(Game.id == game_id))
    if round_id is None:
        raise NotFound("game not found", game_id=str(game_id))
    round_ = lock_round(ctx, round_id)
    game = ctx.session.get(Game, game_id)
    if game is None:
        raise NotFound("game not found", game_id=str(game_id))
    return round_, game


def require_open(round_: Round) -> None:
    """Results may only move while the round is open.

    Once exported the round is frozen: between rounds Vega owns the state, and
    letting both systems edit it is exactly the divergence the freeze prevents.
    """
    if round_.state is RoundState.EXPORTED:
        raise RoundFrozen(
            "this round has been exported to Vega and is read-only",
            round_number=round_.number,
        )
    if round_.state is not RoundState.OPEN:
        raise RoundFrozen(
            "this round has been released by the arbiter and no longer accepts entries",
            round_number=round_.number,
            state=round_.state.value,
        )
