"""Resolve the caller's per-tournament role and refuse what it does not cover.

Every message declares an `access` level. Staff levels are hierarchical; the
device level is not -- a device token may only ever do device things, and only
in the tournament it was minted for.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from seebach.platform.errors import Forbidden, Unauthenticated
from seebach.platform.mediator import ACCESS_RANK, ROLE_RANK, Access, Context, Message, Next
from seebach.shared.enums import PrincipalKind
from seebach.shared.models import TournamentMember


def authorize(message: Message, ctx: Context, nxt: Next) -> Any:
    access = type(message).access
    if access is Access.PUBLIC:
        return nxt()

    principal = ctx.principal
    if principal.kind is PrincipalKind.SYSTEM:
        # In-process only. Nothing that parses a request can produce it, so it
        # is a bootstrap and test affordance rather than a bypass.
        return nxt()

    scope = message.tournament_scope(ctx.session)

    if access is Access.DEVICE:
        _authorize_device(principal, scope, ctx)
        return nxt()

    if principal.kind is not PrincipalKind.STAFF:
        raise Forbidden("this action requires a signed-in staff account")
    if scope is None:
        if access is Access.STAFF:
            # Unscoped staff actions -- creating a tournament, listing your own.
            # There is no membership to check because there is no tournament yet.
            return nxt()
        raise Forbidden("this action is scoped to a tournament that could not be resolved")

    member = ctx.session.scalar(
        select(TournamentMember).where(
            TournamentMember.tournament_id == scope,
            TournamentMember.subject == principal.subject,
        )
    )
    if member is None:
        raise Forbidden("you are not a member of this tournament")
    if ROLE_RANK[member.role] < ACCESS_RANK[access]:
        raise Forbidden(
            f"this action requires the {access.value} role; you have {member.role.value}"
        )

    ctx.role = member.role
    return nxt()


def _authorize_device(principal: Any, scope: Any, ctx: Context) -> None:
    if principal.kind is PrincipalKind.STAFF:
        # Staff may exercise the hall endpoints too; useful for an arbiter
        # entering a result from their own phone.
        return
    if principal.kind is not PrincipalKind.DEVICE:
        raise Unauthenticated("a device token is required")
    if scope is not None and principal.tournament_id != scope:
        raise Forbidden("this device is not admitted to that tournament")
