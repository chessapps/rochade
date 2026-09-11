"""The manager port and its adapters.

Importing this package registers every adapter, the same way `registry.py`
registers every route: explicit, so a missing adapter is an import error rather
than an endpoint that silently is not there.
"""

from rochade.interchange import gacrux as _gacrux  # noqa: F401
from rochade.interchange import swiss_manager as _swiss_manager  # noqa: F401
from rochade.interchange import vega as _vega  # noqa: F401  (registers on import)
from rochade.interchange.document import (
    ManagerFile,
    PairingRow,
    PlayerRow,
    ResultEntry,
    RoundDocument,
)
from rochade.interchange.port import (
    Capabilities,
    InterchangeError,
    Manager,
    ManagerInfo,
    Support,
    UnknownManager,
    available,
    manager_for,
    register,
)

DEFAULT_MANAGER = "vega"


def label_of(key: str) -> str:
    """The manager's display name, or the key when the adapter is gone."""
    try:
        return manager_for(key).label
    except UnknownManager:  # pragma: no cover - an adapter was removed after use
        return key


def native_of(key: str) -> bool:
    """Does Rochade itself pair this program's tournaments?"""
    try:
        return manager_for(key).capabilities.native
    except UnknownManager:  # pragma: no cover - an adapter was removed after use
        return False


__all__ = [
    "DEFAULT_MANAGER",
    "Capabilities",
    "InterchangeError",
    "Manager",
    "ManagerFile",
    "ManagerInfo",
    "PairingRow",
    "PlayerRow",
    "ResultEntry",
    "RoundDocument",
    "Support",
    "UnknownManager",
    "available",
    "label_of",
    "manager_for",
    "native_of",
    "register",
]
