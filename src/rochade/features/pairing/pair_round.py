"""Pair the next round of a section Rochade runs itself.

The counterpart of `import_round` for a native section, and built the same
way: `plan_pairing` works out everything without writing -- who is in, who
is out, what the engine says -- and `preview_pairing` next door shows that
to the arbiter before this command commits it.

Committing does three things at once. It writes the round and its boards,
open for entry. It seeds the start ranks if this is round 1. And it closes
the round before: the new pairing stands on those results, so from here on
they are read-only, exactly as an export freezes a manager's round.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from rochade.features.audit import record
from rochade.features.locking import lock_round
from rochade.features.pairing.compute_standings import engine_failure
from rochade.features.pairing.seeding import provisional_ranks, seed
from rochade.features.pairing.trf_of import build_document
from rochade.features.scoping import tournament_of_section
from rochade.gacrux import EngineError, EnginePair, pair
from rochade.interchange import native_of
from rochade.platform.bus import bus
from rochade.platform.errors import Conflict, NotFound
from rochade.platform.http import get_context
from rochade.platform.mediator import Access, Command, Context
from rochade.shared.enums import EventAction, ResultState, RoundState
from rochade.shared.models import Game, Round, Section, SectionPlayer
from rochade.trf import Colour, RoundEntry, parse
from rochade.trf.build import BuildPlayer, build

router = APIRouter(prefix="/sections", tags=["pairing"])

#: A pairing-allocated bye is a full point (C.04.1.d); a requested absence
#: is half a point or none, as the arbiter says.
PAB = "U"


class Absence(BaseModel):
    """A player who sits this round out, and what it is worth to them."""

    start_rank: int
    result: Literal["H", "Z"] = "Z"


class PlayerRef(BaseModel):
    start_rank: int
    name: str


class PairingBoard(BaseModel):
    board: int
    white_rank: int
    white_name: str
    black_rank: int
    black_name: str


class PairingBye(BaseModel):
    board: int
    start_rank: int
    name: str
    result: str


class PairingPlan(BaseModel):
    section_id: uuid.UUID
    section_name: str
    round_number: int
    declared_rounds: int | None
    #: This pairing seeds the start ranks (round 1): the numbers shown are
    #: the ones the players will hold from then on.
    seeds: bool
    players_in: int
    boards: list[PairingBoard] = Field(default_factory=list)
    byes: list[PairingBye] = Field(default_factory=list)
    withdrawn: list[PlayerRef] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    blocked_by: list[str] = Field(default_factory=list)

    @property
    def can_pair(self) -> bool:
        return not self.blocked_by


@dataclass
class _Planned:
    plan: PairingPlan
    #: The TRF the engine read -- stored with the round for the record.
    trf: str
    pairs: list[EnginePair]
    ranks: dict[SectionPlayer, int]
    absent: dict[int, str]


def plan_pairing(ctx: Context, section: Section, absent: list[Absence]) -> _Planned:
    """Everything the pairing needs, and nothing written."""
    rounds = sorted(section.rounds, key=lambda r: r.number)
    previous = rounds[-1] if rounds else None
    next_no = (previous.number + 1) if previous else 1
    seeds = previous is None
    ranks = (
        provisional_ranks(section.players) if seeds else {p: p.start_rank for p in section.players}
    )
    by_rank = {rank: player for player, rank in ranks.items()}

    plan = PairingPlan(
        section_id=section.id,
        section_name=section.name,
        round_number=next_no,
        declared_rounds=section.declared_rounds,
        seeds=seeds,
        players_in=0,
    )

    if not native_of(section.manager):
        plan.blocked_by.append("this section is paired by its pairing program, not here")
    if previous is not None:
        if previous.state is RoundState.OPEN:
            plan.blocked_by.append(
                f"round {previous.number} is still open for entry; release it first"
            )
        elif any(g.state is not ResultState.CONFIRMED for g in previous.games):
            boards = sorted(g.board for g in previous.games if g.state is not ResultState.CONFIRMED)
            plan.blocked_by.append(
                f"round {previous.number} has boards without a confirmed result "
                f"({', '.join(str(b) for b in boards)}); the next pairing stands on them"
            )
    if section.declared_rounds is not None and next_no > section.declared_rounds:
        plan.blocked_by.append(
            f"all {section.declared_rounds} rounds have been played; the section is finished"
        )

    absent_by_rank: dict[int, str] = {}
    for entry in absent:
        player = by_rank.get(entry.start_rank)
        if player is None:
            plan.blocked_by.append(f"no player has start number {entry.start_rank}")
            continue
        if entry.start_rank in absent_by_rank:
            plan.blocked_by.append(f"start number {entry.start_rank} is listed absent twice")
            continue
        if player.withdrawn_from_round is not None and player.withdrawn_from_round <= next_no:
            plan.warnings.append(f"{player.name} is withdrawn already; the absence is redundant")
            continue
        absent_by_rank[entry.start_rank] = entry.result

    withdrawn = [
        p
        for p in section.players
        if p.withdrawn_from_round is not None and p.withdrawn_from_round <= next_no
    ]
    plan.withdrawn = [
        PlayerRef(start_rank=ranks[p], name=p.name)
        for p in sorted(withdrawn, key=lambda p: ranks[p])
    ]
    out = {ranks[p] for p in withdrawn} | set(absent_by_rank)
    plan.players_in = len(section.players) - len(out)
    if plan.players_in < 2:
        plan.blocked_by.append("at least two players must be in the round to pair it")

    trf = build(build_document(section, upto_round=next_no - 1, ranks=ranks))
    if plan.blocked_by:
        return _Planned(plan=plan, trf=trf, pairs=[], ranks=ranks, absent=absent_by_rank)

    try:
        pairs = pair(
            trf,
            round_no=next_no,
            top_colour=section.top_board_colour if next_no == 1 else None,
            unpaired=sorted(out),
        )
    except EngineError as exc:
        raise engine_failure(exc, f"the pairing engine could not pair round {next_no}") from exc

    _fill_boards(plan, pairs, absent_by_rank, section, ranks, next_no)
    if len(section.players) % 2 == 0 and any(b.result == PAB for b in plan.byes):
        plan.warnings.append("an even field ends up with a bye because someone sits out")
    return _Planned(plan=plan, trf=trf, pairs=pairs, ranks=ranks, absent=absent_by_rank)


def _fill_boards(
    plan: PairingPlan,
    pairs: list[EnginePair],
    absent: dict[int, str],
    section: Section,
    ranks: dict[SectionPlayer, int],
    round_no: int,
) -> None:
    """Number the boards in the FIDE order, the way every other round here is numbered.

    The engine lists pairs; the board numbers come from the same rule the
    import uses (`TrfFile.pairings`), so a native round and an imported one
    read the same way on the wall.
    """
    document = build_document(section, upto_round=round_no - 1, ranks=ranks)
    by_rank = {p.start_rank: p for p in document.players}
    extended: list[BuildPlayer] = []
    for player in document.players:
        rounds = dict(player.rounds)
        rounds.pop(round_no, None)
        extended.append(
            BuildPlayer(
                start_rank=player.start_rank,
                name=player.name,
                sex=player.sex,
                title=player.title,
                rating=player.rating,
                federation=player.federation,
                fide_id=player.fide_id,
                birth_date=player.birth_date,
                rounds=rounds,
            )
        )
    lookup = {p.start_rank: p for p in extended}

    def entry(rank: int, opponent: int | None, colour: Colour, result: str) -> None:
        player = lookup[rank]
        rounds = dict(player.rounds)
        rounds[round_no] = RoundEntry(
            round_no=round_no, opponent=opponent, colour=colour, result=result
        )
        lookup[rank] = BuildPlayer(
            start_rank=player.start_rank,
            name=player.name,
            sex=player.sex,
            title=player.title,
            rating=player.rating,
            federation=player.federation,
            fide_id=player.fide_id,
            birth_date=player.birth_date,
            rounds=rounds,
        )

    for pairing in pairs:
        if pairing.black is None:
            entry(pairing.white, None, Colour.NONE, PAB)
        else:
            entry(pairing.white, pairing.black, Colour.WHITE, " ")
            entry(pairing.black, pairing.white, Colour.BLACK, " ")
    for rank, code in absent.items():
        entry(rank, None, Colour.NONE, code)

    trf = parse(build(replace(document, players=list(lookup.values()))))
    for board in trf.pairings(round_no):
        if board.black is None:
            plan.byes.append(
                PairingBye(
                    board=board.board,
                    start_rank=board.white,
                    name=by_rank[board.white].name,
                    result=board.white_result,
                )
            )
        else:
            plan.boards.append(
                PairingBoard(
                    board=board.board,
                    white_rank=board.white,
                    white_name=by_rank[board.white].name,
                    black_rank=board.black,
                    black_name=by_rank[board.black].name,
                )
            )


# --- the command ------------------------------------------------------------


class PairRoundResult(BaseModel):
    section_id: uuid.UUID
    round_id: uuid.UUID
    round_number: int
    boards: int
    byes: int
    #: This pairing fixed the start ranks (round 1).
    seeded: bool
    #: The round closed by this pairing, if there was one.
    previous_round_closed: int | None


class PairRound(Command):
    access = Access.ARBITER
    result_model = PairRoundResult

    section_id: uuid.UUID
    absent: list[Absence] = Field(default_factory=list, max_length=500)

    def tournament_scope(self, session: Session) -> uuid.UUID | None:
        return tournament_of_section(session, self.section_id)


def lock_section(ctx: Context, section_id: uuid.UUID) -> Section:
    """Take the section row, so two pairings of the same round cannot both run."""
    section = ctx.session.scalar(select(Section).where(Section.id == section_id).with_for_update())
    if section is None:
        raise NotFound("section not found", section_id=str(section_id))
    return section


def lock_section_and_newest_round(
    ctx: Context, section_id: uuid.UUID
) -> tuple[Section, Round | None]:
    """Round first, then section: the one lock order every native write uses.

    A correction on a released board holds that round's row and then touches
    the section (the standings). A pairing must take the same two locks in
    the same order, or the two can wait on each other for ever. The newest
    round is read without a lock first; once both rows are held it is read
    again, since another pairing may have landed in between.
    """
    newest_id = ctx.session.scalar(
        select(Round.id)
        .where(Round.section_id == section_id)
        .order_by(Round.number.desc())
        .limit(1)
    )
    newest = lock_round(ctx, newest_id) if newest_id is not None else None
    section = lock_section(ctx, section_id)
    ctx.session.refresh(section)
    latest = max(section.rounds, key=lambda r: r.number, default=None)
    if (latest.id if latest else None) != (newest.id if newest else None):
        raise Conflict(
            "another pairing landed a moment ago; look again", section_id=str(section_id)
        )
    return section, newest


@bus.register(PairRound)
def handle(command: PairRound, ctx: Context) -> PairRoundResult:
    section, _previous = lock_section_and_newest_round(ctx, command.section_id)
    planned = plan_pairing(ctx, section, command.absent)
    plan = planned.plan
    if not plan.can_pair:
        raise Conflict("this round cannot be paired", reasons=plan.blocked_by)

    # Round 1 fixes the start ranks. `reordered` says whether that moved anyone.
    reordered = seed(section) if plan.seeds else False

    previous = max(section.rounds, key=lambda r: r.number, default=None)
    if previous is not None:
        previous.state = RoundState.EXPORTED
        previous.exported_at = datetime.now(UTC)

    round_ = Round(
        number=plan.round_number,
        state=RoundState.OPEN,
        source_trf=planned.trf,
        source_filename="gacrux",
    )
    section.rounds.append(round_)
    by_rank = {p.start_rank: p for p in section.players}
    for board in plan.boards:
        round_.games.append(
            Game(
                board=board.board,
                white_rank=board.white_rank,
                white_name=by_rank[board.white_rank].name,
                black_rank=board.black_rank,
                black_name=by_rank[board.black_rank].name,
            )
        )
    for bye in plan.byes:
        round_.games.append(
            Game(
                board=bye.board,
                white_rank=bye.start_rank,
                white_name=by_rank[bye.start_rank].name,
                white_result=bye.result,
                state=ResultState.CONFIRMED,
            )
        )
    ctx.session.flush()

    record(
        ctx,
        section_id=section.id,
        round_number=round_.number,
        action=EventAction.ROUND_PAIRED,
        boards=len(plan.boards),
        byes=[b.model_dump(mode="json") for b in plan.byes],
        withdrawn=[p.model_dump(mode="json") for p in plan.withdrawn],
        absent=[{"start_rank": r, "result": c} for r, c in sorted(planned.absent.items())],
        seeded=plan.seeds,
        reordered=reordered,
        top_board_colour=section.top_board_colour if plan.round_number == 1 else None,
        engine_pairs=[[p.white, p.black or 0] for p in planned.pairs],
        previous_round_closed=previous.number if previous else None,
    )

    return PairRoundResult(
        section_id=section.id,
        round_id=round_.id,
        round_number=round_.number,
        boards=len(plan.boards),
        byes=len(plan.byes),
        seeded=plan.seeds,
        previous_round_closed=previous.number if previous else None,
    )


class PairBody(BaseModel):
    absent: list[Absence] = Field(default_factory=list)


@router.post("/{section_id}/pairings", response_model=PairRoundResult, status_code=201)
def pair_round(
    section_id: uuid.UUID, body: PairBody, ctx: Context = Depends(get_context)
) -> PairRoundResult:
    result: PairRoundResult = bus.send(PairRound(section_id=section_id, **body.model_dump()), ctx)
    return result
