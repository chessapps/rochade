"""How the admin app should sign in: the one thing it asks before it has a
credential.

With an issuer configured it starts an OIDC authorization-code flow against
it; without one, and with dev auth switched on, it shows the token field.
Nothing here is secret -- a public client id and an issuer URL are what any
browser sees in the first redirect anyway.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from seebach.platform.bus import bus
from seebach.platform.config import settings
from seebach.platform.http import get_public_context
from seebach.platform.mediator import Access, Context, Query

router = APIRouter(prefix="/auth", tags=["auth"])


class AuthConfig(BaseModel):
    #: Empty when staff auth is in the dev bootstrap mode.
    issuer: str
    client_id: str
    #: Whether a bare token is accepted as the staff subject.
    dev_auth: bool


class GetAuthConfig(Query):
    access = Access.PUBLIC


@bus.register(GetAuthConfig)
def handle(query: GetAuthConfig, ctx: Context) -> AuthConfig:
    config = settings()
    return AuthConfig(
        issuer=config.oidc_issuer,
        client_id=config.oidc_client_id,
        dev_auth=config.dev_auth_enabled,
    )


@router.get("/config", response_model=AuthConfig)
def get_auth_config(ctx: Context = Depends(get_public_context)) -> AuthConfig:
    result: AuthConfig = bus.send(GetAuthConfig(), ctx)
    return result
