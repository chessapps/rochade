"""Dry-run an import and return the diff. Writes nothing.

This is what makes the manual handoff safe: an arbiter sees exactly what a file
will do -- which players arrive, which leave, which earlier results Vega has
changed, which entered results a re-pair would drop -- before anything is
committed.

The plan itself is built by `import_round`, which owns it, and which sits
next to this file because preview and commit are one workflow for the arbiter.
That is the whole argument for grouping by feature rather than by whether a
message happens to write.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from rochade.features.imports.import_round import (
    ImportPlan,
    build_plan,
    require_file_driven,
    resolve_manager,
)
from rochade.platform.bus import bus
from rochade.platform.errors import NotFound
from rochade.platform.http import get_context
from rochade.platform.mediator import Access, Context, Query
from rochade.shared.models import Tournament

router = APIRouter(prefix="/tournaments", tags=["import"])


class PreviewImport(Query):
    access = Access.ARBITER

    tournament_id: uuid.UUID
    section_name: str
    content: str
    force: bool = False


@bus.register(PreviewImport)
def handle(query: PreviewImport, ctx: Context) -> ImportPlan:
    tournament = ctx.session.get(Tournament, query.tournament_id)
    if tournament is None:
        raise NotFound("tournament not found", tournament_id=str(query.tournament_id))

    plan, _ = build_plan(
        ctx.session,
        tournament=tournament,
        section_name=query.section_name,
        content=query.content,
        manager=require_file_driven(resolve_manager(tournament.manager)),
        force=query.force,
    )
    return plan


class PreviewBody(BaseModel):
    section_name: str
    content: str
    force: bool = False


@router.post("/{tournament_id}/imports/preview", response_model=ImportPlan)
def preview_import(
    tournament_id: uuid.UUID, body: PreviewBody, ctx: Context = Depends(get_context)
) -> ImportPlan:
    result: ImportPlan = bus.send(
        PreviewImport(tournament_id=tournament_id, **body.model_dump()), ctx
    )
    return result
