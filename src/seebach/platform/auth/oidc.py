"""OIDC bearer verification against the configured issuer's JWKS.

The API only ever sees a standard OIDC JWT, which is what keeps the IdP
swappable -- Zitadel is a deployment choice, not an architectural one.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import httpx
from jose import jwt
from jose.exceptions import JWTError

from seebach.platform.config import settings
from seebach.platform.errors import Unauthenticated


@lru_cache(maxsize=1)
def _jwks() -> dict[str, Any]:
    config = settings()
    url = config.oidc_jwks_url or f"{config.oidc_issuer.rstrip('/')}/oauth/v2/keys"
    response = httpx.get(url, timeout=10.0)
    response.raise_for_status()
    data: dict[str, Any] = response.json()
    return data


def verify(token: str) -> dict[str, Any]:
    config = settings()
    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            _jwks(),
            audience=config.oidc_audience,
            issuer=config.oidc_issuer,
            options={"verify_at_hash": False},
        )
    except JWTError as exc:
        raise Unauthenticated(f"token rejected: {exc}") from exc
    if "sub" not in claims:
        raise Unauthenticated("token has no subject")
    return claims
