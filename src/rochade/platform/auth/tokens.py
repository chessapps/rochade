"""Device tokens.

Issued by the app, never by the IdP, because the thing being admitted is a
phone in a hall for one day -- not a person with an account. Stored hashed, so
a database read cannot mint access.
"""

from __future__ import annotations

import hashlib
import secrets

TOKEN_BYTES = 32


def mint() -> tuple[str, str]:
    """Return `(token, token_hash)`. The token is shown once, in a QR code."""
    token = secrets.token_urlsafe(TOKEN_BYTES)
    return token, hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
