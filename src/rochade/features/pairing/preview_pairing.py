"""What pairing the next round would do. Writes nothing.

The arbiter sees the boards, the bye and who is left out before anything is
committed, the way the import preview shows a file's effect. The engine is
deterministic, so the pairing that follows is the one shown -- unless the
roster or the absences change in between, which is the point of looking.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from rochade.features.pairing.pair_round import Absence, PairingPlan, plan_pairing
from rochade.features.scoping import tournament_of_section
from rochade.platform.bus import bus
from rochade.platform.errors import NotFound
from rochade.platform.http import get_context
from rochade.platform.mediator import Access, Context, Query
from rochade.shared.models import Section

router = APIRouter(prefix="/sections", tags=["pairing"])


class PreviewPairing(Query):
    access = Access.ARBITER

    section_id: uuid.UUID
    absent: list[Absence] = Field(default_factory=list)

    def tournament_scope(self, session: Session) -> uuid.UUID | None:
        return tournament_of_section(session, self.section_id)


@bus.register(PreviewPairing)
def handle(query: PreviewPairing, ctx: Context) -> PairingPlan:
    section = ctx.session.get(Section, query.section_id)
    if section is None:
        raise NotFound("section not found", section_id=str(query.section_id))
    return plan_pairing(ctx, section, query.absent).plan


class PreviewBody(BaseModel):
    absent: list[Absence] = Field(default_factory=list)


@router.post("/{section_id}/pairings/preview", response_model=PairingPlan)
def preview_pairing(
    section_id: uuid.UUID, body: PreviewBody, ctx: Context = Depends(get_context)
) -> PairingPlan:
    result: PairingPlan = bus.send(PreviewPairing(section_id=section_id, **body.model_dump()), ctx)
    return result
