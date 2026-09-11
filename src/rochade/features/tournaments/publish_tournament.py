"""Make a tournament readable by anyone, or hide it again.

Off by default. The public app (`apps/live`) reads only published
tournaments, by slug, through the queries under `features/public/`; an
unpublished tournament answers there exactly like one that does not exist.

The slug is chosen once, from the name, the first time the tournament is
published, and kept from then on: a link that was posted keeps working after
the tournament is hidden and shown again. The arbiter may set a different one
at any time; the old link then stops working, which is what changing it means.
"""

from __future__ import annotations

import re
import unicodedata
import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from rochade.platform.bus import bus
from rochade.platform.errors import NotFound, ValidationFailed
from rochade.platform.http import get_context
from rochade.platform.mediator import Access, Command, Context
from rochade.shared.models import Tournament

router = APIRouter(prefix="/tournaments", tags=["tournaments"])

_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class Publication(BaseModel):
    published: bool
    #: None until the tournament has been published once.
    slug: str | None


class PublishTournament(Command):
    access = Access.ARBITER
    result_model = Publication

    tournament_id: uuid.UUID
    published: bool
    #: Lower-case words joined by single dashes. Omitted: the slug is derived
    #: from the name on first publication and left alone afterwards.
    slug: str | None = Field(default=None, max_length=80)

    def check(self) -> None:
        if self.slug is not None and not _SLUG.match(self.slug):
            raise ValidationFailed(
                "a slug is lower-case letters, digits and single dashes", slug=self.slug
            )


@bus.register(PublishTournament)
def handle(command: PublishTournament, ctx: Context) -> Publication:
    tournament = ctx.session.get(Tournament, command.tournament_id)
    if tournament is None:
        raise NotFound("tournament not found", tournament_id=str(command.tournament_id))

    if command.slug is not None:
        wanted = command.slug
        if wanted != tournament.slug and _taken(ctx, wanted):
            raise ValidationFailed("another tournament already uses that slug", slug=wanted)
        tournament.slug = wanted
    elif tournament.slug is None and command.published:
        tournament.slug = _free_slug(ctx, slugify(tournament.name) or "tournament")

    tournament.published = command.published
    try:
        ctx.session.flush()
    except IntegrityError:
        # Two publications raced for one slug; the unique constraint decided.
        raise ValidationFailed(
            "another tournament already uses that slug", slug=tournament.slug
        ) from None
    return Publication(published=tournament.published, slug=tournament.slug)


def slugify(name: str) -> str:
    """``Zürich Open 2026`` becomes ``zurich-open-2026``."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    words = re.findall(r"[a-z0-9]+", ascii_name.lower())
    return "-".join(words)[:60].strip("-")


def _taken(ctx: Context, slug: str) -> bool:
    return ctx.session.scalar(select(Tournament.id).where(Tournament.slug == slug)) is not None


def _free_slug(ctx: Context, base: str) -> str:
    if not _taken(ctx, base):
        return base
    for n in range(2, 1000):
        candidate = f"{base}-{n}"
        if not _taken(ctx, candidate):
            return candidate
    raise RuntimeError("could not find a free slug")  # pragma: no cover


class PublicationBody(BaseModel):
    published: bool
    slug: str | None = Field(default=None, max_length=80)


@router.put("/{tournament_id}/publication", response_model=Publication)
def publish_tournament(
    tournament_id: uuid.UUID, body: PublicationBody, ctx: Context = Depends(get_context)
) -> Publication:
    result: Publication = bus.send(
        PublishTournament(tournament_id=tournament_id, **body.model_dump()), ctx
    )
    return result
