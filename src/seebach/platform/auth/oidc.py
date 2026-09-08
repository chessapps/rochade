"""OIDC bearer verification against the configured issuer's JWKS.

The API only ever sees a standard OIDC JWT, which is what keeps the IdP
swappable -- Zitadel is a deployment choice, not an architectural one.
"""

from __future__ import annotations

import threading
import time
from typing import Any

import httpx
from jose import jwt
from jose.exceptions import JWTError

from seebach.platform.config import Settings, settings
from seebach.platform.errors import Unauthenticated

_lock = threading.Lock()
_cached: dict[str, Any] | None = None
_last_fetch = 0.0
#: How often the key set is refetched at most. A token naming an unknown `kid`
#: triggers a refetch, and the `kid` comes from the unverified header, so
#: without a floor anyone could turn the API into a load generator against
#: the issuer. Real rotations happen months apart; a minute is nothing.
REFETCH_INTERVAL = 60.0


def jwks_url(config: Settings) -> str:
    if config.oidc_jwks_url:
        return config.oidc_jwks_url
    return f"{config.oidc_issuer.rstrip('/')}/oauth/v2/keys"


def issuer_request(config: Settings, url: str) -> tuple[str, dict[str, str]]:
    """Rewrite a public issuer URL to the in-stack address, keeping the host.

    Zitadel resolves its instance from the Host header, so a request that goes
    to http://zitadel:8080 must still say it is for auth.example.com.
    """
    if not config.oidc_internal_url:
        return url, {}
    public = httpx.URL(config.oidc_issuer)
    target = httpx.URL(url)
    if target.host != public.host:
        return url, {}
    internal = httpx.URL(config.oidc_internal_url)
    rewritten = target.copy_with(scheme=internal.scheme, host=internal.host, port=internal.port)
    return str(rewritten), {"Host": public.netloc.decode()}


def _fetch_jwks(config: Settings) -> dict[str, Any]:
    url, headers = issuer_request(config, jwks_url(config))
    response = httpx.get(url, headers=headers, timeout=10.0)
    response.raise_for_status()
    data: dict[str, Any] = response.json()
    return data


def _jwks(config: Settings, *, kid: str | None) -> dict[str, Any]:
    """The key set, refetched when a token names a key we have not seen.

    Keys rotate; a process that cached the set at start-up would otherwise
    reject every token until it was restarted. Refetches are rate-limited,
    and an issuer that cannot be reached is a 401, not a crash.
    """
    global _cached, _last_fetch
    with _lock:
        stale = _cached is None or (kid is not None and not _has_kid(_cached, kid))
        if stale and time.monotonic() - _last_fetch >= REFETCH_INTERVAL:
            _last_fetch = time.monotonic()
            try:
                _cached = _fetch_jwks(config)
            except httpx.HTTPError as exc:
                if _cached is None:
                    raise Unauthenticated(
                        f"the sign-in service could not be reached: {exc}"
                    ) from exc
        if _cached is None:
            raise Unauthenticated("the sign-in service could not be reached; try again shortly")
        return _cached


def _has_kid(jwks: dict[str, Any], kid: str) -> bool:
    return any(key.get("kid") == kid for key in jwks.get("keys", []))


def reset_cache() -> None:
    global _cached, _last_fetch
    with _lock:
        _cached = None
        _last_fetch = 0.0


def looks_like_jwt(token: str) -> bool:
    return token.count(".") == 2 and all(token.split("."))


def verify(token: str) -> dict[str, Any]:
    config = settings()
    audience = config.token_audience
    if not audience:
        # Without an audience any client of the issuer could sign in here.
        # Closed, not open: the setup step normally supplies the client id.
        raise Unauthenticated(
            "staff sign-in is misconfigured: no SEEBACH_OIDC_CLIENT_ID or SEEBACH_OIDC_AUDIENCE"
        )
    try:
        kid = jwt.get_unverified_header(token).get("kid")
        claims: dict[str, Any] = jwt.decode(
            token,
            _jwks(config, kid=kid),
            audience=audience,
            issuer=config.oidc_issuer,
            options={"verify_at_hash": False},
        )
    except JWTError as exc:
        raise Unauthenticated(f"token rejected: {exc}") from exc
    if "sub" not in claims:
        raise Unauthenticated("token has no subject")
    return claims
