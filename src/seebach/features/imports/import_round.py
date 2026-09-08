"""Import a Vega TRF file as one section's state, up to and including a round.

Two things about this command are load-bearing:

**It replaces, it does not merge.** Vega's file is authoritative for tournament
state -- players, pairings, prior results -- so an import rebuilds our copy of
the section rather than reconciling field by field. Only `game_event` survives,
because it is append-only, ours alone, and anchored to a natural key.

**It is planned before it is applied.** `build_plan` does the whole diff without
touching anything, and is what `preview_import` next door calls. Nothing is
written until an arbiter has seen what will change.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from seebach.features.audit import record
from seebach.features.roster import roster_of
from seebach.interchange import (
    DEFAULT_MANAGER,
    InterchangeError,
    Manager,
    PairingRow,
    RoundDocument,
    UnknownManager,
    manager_for,
)
from seebach.platform.bus import bus
from seebach.platform.errors import Conflict, NotFound, ValidationFailed
from seebach.platform.http import get_context
from seebach.platform.mediator import Access, Command, Context
from seebach.shared.enums import EventAction, ResultState, RoundState
from seebach.shared.models import Game, Round, Section, SectionPlayer, Tournament
from seebach.trf.results import mirror

router = APIRouter(prefix="/tournaments", tags=["import"])


def resolve_manager(key: str) -> Manager:
    """Turn a manager key from a request into an adapter, or a 422.

    Shared with `preview_import`, which must resolve it identically -- a
    preview against a different adapter than the import would use is worse
    than no preview at all.
    """
    try:
        return manager_for(key)
    except UnknownManager as exc:
        raise ValidationFailed(str(exc), manager=key) from exc


# --- the plan ---------------------------------------------------------------


class PlayerChange(BaseModel):
    start_rank: int
    name: str
    rating: int | None = None


class ResultDisagreement(BaseModel):
    """A prior-round result in the file differs from the one we hold.

    Expected, not an error: an arbiter correcting an earlier round in Vega is
    normal and Vega is authoritative. It must be listed and acknowledged, never
    applied silently.
    """

    round_number: int
    white_name: str
    black_name: str | None
    ours: str
    theirs: str


class CarriedClaim(BaseModel):
    white_name: str
    black_name: str | None
    white_result: str
    state: ResultState


class ImportPlan(BaseModel):
    section_name: str
    section_exists: bool
    file_round: int
    expected_round: int
    is_expected_round: bool
    declared_rounds: int | None
    tournament_name: str

    players_total: int
    players_added: list[PlayerChange] = Field(default_factory=list)
    players_removed: list[PlayerChange] = Field(default_factory=list)
    players_renamed: list[str] = Field(default_factory=list)

    boards: int
    byes: int
    disagreements: list[ResultDisagreement] = Field(default_factory=list)
    claims_carried: list[CarriedClaim] = Field(default_factory=list)
    claims_dropped: list[CarriedClaim] = Field(default_factory=list)

    unknown_result_codes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    blocked_by: list[str] = Field(default_factory=list)

    @property
    def can_import(self) -> bool:
        return not self.blocked_by


@dataclass
class _Existing:
    """What we already hold for this section, in the shapes the plan needs."""

    section: Section | None
    players: dict[int, SectionPlayer] = field(default_factory=dict)
    rounds: dict[int, Round] = field(default_factory=dict)
    # (round, white_name, black_name) -> game
    games: dict[tuple[int, str, str | None], Game] = field(default_factory=dict)


@dataclass(frozen=True)
class _Carried:
    """An entered result, held across a rebuild of the round it belongs to."""

    white_name: str
    white_result: str
    black_result: str
    state: ResultState
    disputed_white_result: str | None


def build_plan(
    session: Session,
    *,
    tournament: Tournament,
    section_name: str,
    content: str,
    manager: Manager,
    force: bool = False,
) -> tuple[ImportPlan, RoundDocument]:
    """Diff a file against what we hold. Pure: reads only, writes nothing."""
    existing = _load_existing(session, tournament.id, section_name)
    # A manager whose export can arrive without its player list is handed the
    # roster from the last import, so the second round needs one file, not two.
    try:
        document = manager.read_round(content, roster_of(existing.section))
    except InterchangeError as exc:
        raise ValidationFailed(f"the file could not be read: {exc}", line_no=exc.line_no) from exc

    if not document.players:
        raise ValidationFailed("the file contains no player rows")

    file_round = document.rounds_present
    if file_round < 1:
        raise ValidationFailed("the file contains no rounds")

    expected = max(existing.rounds, default=0) + 1 if existing.rounds else 1
    # A TRF is a whole-tournament document, so the first import may legitimately
    # arrive mid-event carrying rounds 1..N -- an arbiter adopting the tool for
    # round 4 of a five-round open is the normal case, not an error. Ordering
    # only means something once we already hold rounds.
    first_import = not existing.rounds
    # Re-importing the round we already hold is a re-pair, not a mistake.
    is_expected = first_import or file_round in (expected, expected - 1)

    pairings = document.board_rows(file_round)
    plan = ImportPlan(
        section_name=section_name,
        section_exists=existing.section is not None,
        file_round=file_round,
        expected_round=expected,
        is_expected_round=is_expected,
        declared_rounds=document.declared_rounds,
        tournament_name=document.tournament_name,
        players_total=len(document.players),
        boards=sum(1 for p in pairings if not p.is_bye),
        byes=sum(1 for p in pairings if p.is_bye),
        unknown_result_codes=list(document.unknown_result_codes),
    )

    _diff_players(plan, document, existing)
    _diff_prior_results(plan, document, existing, file_round)
    _diff_claims(plan, pairings, existing, file_round)

    if not is_expected:
        plan.warnings.append(
            f"this file holds round {file_round}, but round {expected} was expected"
        )
    if document.unknown_result_codes:
        plan.warnings.append(
            "the file uses result codes we do not recognise: "
            + ", ".join(repr(c) for c in document.unknown_result_codes)
        )

    frozen = existing.rounds.get(file_round)
    if frozen is not None and frozen.state is RoundState.EXPORTED and not force:
        plan.blocked_by.append(
            f"round {file_round} has already been exported to the manager; "
            "re-importing it would overwrite results the manager already has"
        )
    if not first_import and file_round > expected:
        plan.blocked_by.append(
            f"round {file_round - 1} has not been imported yet -- rounds must arrive in order"
        )

    return plan, document


def _load_existing(session: Session, tournament_id: uuid.UUID, section_name: str) -> _Existing:
    section = session.scalar(
        select(Section).where(Section.tournament_id == tournament_id, Section.name == section_name)
    )
    if section is None:
        return _Existing(section=None)

    existing = _Existing(
        section=section,
        players={p.start_rank: p for p in section.players},
        rounds={r.number: r for r in section.rounds},
    )
    for round_ in section.rounds:
        for game in round_.games:
            existing.games[(round_.number, game.white_name, game.black_name)] = game
    return existing


def _diff_players(plan: ImportPlan, document: RoundDocument, existing: _Existing) -> None:
    incoming = {
        rank: PlayerChange(start_rank=rank, name=p.name, rating=p.rating)
        for rank, p in document.players.items()
    }
    held = existing.players

    plan.players_added = [c for rank, c in sorted(incoming.items()) if rank not in held]
    plan.players_removed = [
        PlayerChange(start_rank=p.start_rank, name=p.name, rating=p.rating)
        for rank, p in sorted(held.items())
        if rank not in incoming
    ]
    plan.players_renamed = [
        f"{rank}: {held[rank].name} -> {incoming[rank].name}"
        for rank in sorted(set(held) & set(incoming))
        if held[rank].name != incoming[rank].name
    ]


def _diff_prior_results(
    plan: ImportPlan, document: RoundDocument, existing: _Existing, file_round: int
) -> None:
    for round_no in range(1, file_round):
        for pairing in document.board_rows(round_no):
            game = existing.games.get((round_no, pairing.white_name, pairing.black_name))
            if game is None:
                continue
            if game.white_result != pairing.white_result and game.white_result != " ":
                plan.disagreements.append(
                    ResultDisagreement(
                        round_number=round_no,
                        white_name=pairing.white_name,
                        black_name=pairing.black_name,
                        ours=game.white_result,
                        theirs=pairing.white_result,
                    )
                )


def _diff_claims(
    plan: ImportPlan,
    pairings: list[PairingRow],
    existing: _Existing,
    file_round: int,
) -> None:
    """Which entered results survive a re-pair of the round we already hold.

    Matched by player pair, never by board: Vega renumbers boards when it
    re-pairs, so a board number is not an identity. The match is unordered,
    because a re-pair can also swap the colours. It is scoped to one round and
    one file, which is why the name is enough and nothing has to be persisted.
    """
    held = sorted(
        (
            game
            for key, game in existing.games.items()
            if key[0] == file_round and game.state is not ResultState.EMPTY
        ),
        key=lambda g: g.board,
    )
    if not held:
        return

    incoming = {pair_key(p.white_name, p.black_name) for p in pairings}

    for game in held:
        carried = CarriedClaim(
            white_name=game.white_name,
            black_name=game.black_name,
            white_result=game.white_result,
            state=game.state,
        )
        if pair_key(game.white_name, game.black_name) in incoming:
            plan.claims_carried.append(carried)
        else:
            plan.claims_dropped.append(carried)

    if plan.claims_dropped:
        plan.warnings.append(
            f"{len(plan.claims_dropped)} entered result(s) do not exist in the new pairing "
            "and will be dropped -- they stay in the audit log"
        )


def pair_key(white_name: str, black_name: str | None) -> tuple[str, ...]:
    """Identity of a game for carry-over: the player pair, order-independent."""
    if black_name is None:
        return (white_name,)
    return tuple(sorted((white_name, black_name)))


# --- the command ------------------------------------------------------------


class ImportRoundResult(BaseModel):
    section_id: uuid.UUID
    round_id: uuid.UUID
    round_number: int
    boards: int
    byes: int
    claims_carried: int
    claims_dropped: int


class ImportRound(Command):
    access = Access.ARBITER
    result_model = ImportRoundResult

    tournament_id: uuid.UUID
    section_name: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1)
    filename: str = Field(default="", max_length=255)
    #: Which manager produced this file. Per section, not per tournament: a
    #: tournament may hold groups run in different programs.
    manager: str = DEFAULT_MANAGER
    #: Set only after the arbiter has read a plan that reported a blocker.
    force: bool = False


@bus.register(ImportRound)
def handle(command: ImportRound, ctx: Context) -> ImportRoundResult:
    tournament = ctx.session.get(Tournament, command.tournament_id)
    if tournament is None:
        raise NotFound("tournament not found", tournament_id=str(command.tournament_id))

    manager = resolve_manager(command.manager)
    plan, document = build_plan(
        ctx.session,
        tournament=tournament,
        section_name=command.section_name,
        content=command.content,
        manager=manager,
        force=command.force,
    )
    if not plan.can_import:
        raise Conflict("this file cannot be imported", reasons=plan.blocked_by)

    section = _upsert_section(ctx, tournament, command.section_name, document, manager.key)
    carried = _carried_results(ctx, section, plan.file_round)
    _rebuild(ctx, section, document, plan.file_round, carried)
    ctx.session.flush()

    round_ = next(r for r in section.rounds if r.number == plan.file_round)
    round_.source_trf = command.content
    round_.source_filename = command.filename

    record(
        ctx,
        section_id=section.id,
        round_number=plan.file_round,
        action=EventAction.ROUND_IMPORTED,
        filename=command.filename,
        manager=manager.key,
        boards=plan.boards,
        byes=plan.byes,
        players=plan.players_total,
        disagreements=len(plan.disagreements),
        claims_dropped=[c.model_dump(mode="json") for c in plan.claims_dropped],
        forced=command.force,
    )

    return ImportRoundResult(
        section_id=section.id,
        round_id=round_.id,
        round_number=plan.file_round,
        boards=plan.boards,
        byes=plan.byes,
        claims_carried=len(plan.claims_carried),
        claims_dropped=len(plan.claims_dropped),
    )


def _upsert_section(
    ctx: Context, tournament: Tournament, name: str, document: RoundDocument, manager_key: str
) -> Section:
    section = ctx.session.scalar(
        select(Section).where(Section.tournament_id == tournament.id, Section.name == name)
    )
    if section is None:
        section = Section(tournament_id=tournament.id, name=name)
        ctx.session.add(section)
    section.manager = manager_key
    section.declared_rounds = document.declared_rounds
    ctx.session.flush()
    return section


def _carried_results(
    ctx: Context, section: Section, file_round: int
) -> dict[tuple[str, ...], _Carried]:
    """Snapshot entered results for the round about to be rebuilt."""
    carried: dict[tuple[str, ...], _Carried] = {}
    for round_ in section.rounds:
        if round_.number != file_round:
            continue
        for game in round_.games:
            if game.state is ResultState.EMPTY:
                continue
            carried[pair_key(game.white_name, game.black_name)] = _Carried(
                white_name=game.white_name,
                white_result=game.white_result,
                black_result=game.black_result,
                state=game.state,
                disputed_white_result=game.disputed_white_result,
            )
    return carried


def _rebuild(
    ctx: Context,
    section: Section,
    document: RoundDocument,
    file_round: int,
    carried: dict[tuple[str, ...], _Carried],
) -> None:
    """Replace players and rounds from the file. Audit events are untouched."""
    section.players.clear()
    section.rounds.clear()
    ctx.session.flush()

    for rank, player in sorted(document.players.items()):
        section.players.append(
            SectionPlayer(
                start_rank=rank,
                name=player.name,
                title=player.title,
                rating=player.rating,
                federation=player.federation,
                fide_id=player.fide_id,
            )
        )

    for round_no in range(1, file_round + 1):
        is_current = round_no == file_round
        round_ = Round(
            number=round_no,
            # Everything before the round we are importing is history that Vega
            # has already published; only the newest round is open for entry.
            state=RoundState.OPEN if is_current else RoundState.EXPORTED,
            source_trf="",
        )
        section.rounds.append(round_)

        for pairing in document.board_rows(round_no):
            game = Game(
                board=pairing.board,
                white_rank=pairing.white_rank,
                white_name=pairing.white_name,
                black_rank=pairing.black_rank,
                black_name=pairing.black_name,
                white_result=pairing.white_result,
                black_result=pairing.black_result,
                state=(ResultState.EMPTY if pairing.white_result == " " else ResultState.CONFIRMED),
            )
            if is_current:
                _apply_carried(game, carried)
            round_.games.append(game)


def _apply_carried(game: Game, carried: dict[tuple[str, ...], _Carried]) -> None:
    """Re-attach an entered result to the same pair of players in the new pairing.

    A re-pair can swap the colours, so the result is mirrored when it does --
    otherwise carrying a claim over would silently invert it.
    """
    entry = carried.get(pair_key(game.white_name, game.black_name))
    if entry is None:
        return

    flipped = entry.white_name != game.white_name
    game.white_result = entry.black_result if flipped else entry.white_result
    game.black_result = entry.white_result if flipped else entry.black_result
    game.state = entry.state
    disputed = entry.disputed_white_result
    game.disputed_white_result = _mirror_or_none(disputed) if flipped else disputed


def _mirror_or_none(code: str | None) -> str | None:
    if code is None:
        return None
    try:
        return mirror(code)
    except ValueError:
        return None


# --- route ------------------------------------------------------------------


class ImportRoundBody(BaseModel):
    section_name: str
    content: str
    filename: str = ""
    manager: str = DEFAULT_MANAGER
    force: bool = False


@router.post("/{tournament_id}/imports", response_model=ImportRoundResult, status_code=201)
def import_round(
    tournament_id: uuid.UUID,
    body: ImportRoundBody,
    ctx: Context = Depends(get_context),
) -> ImportRoundResult:
    command = ImportRound(tournament_id=tournament_id, **body.model_dump())
    result: ImportRoundResult = bus.send(command, ctx)
    return result
