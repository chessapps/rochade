"""The manager port and its adapters.

Importing this package registers every adapter, the same way `registry.py`
registers every route: explicit, so a missing adapter is an import error rather
than an endpoint that silently is not there.
"""

from seebach.interchange import swiss_manager as _swiss_manager  # noqa: F401
from seebach.interchange import vega as _vega  # noqa: F401  (registers on import)
from seebach.interchange.document import (
    ManagerFile,
    PairingRow,
    PlayerRow,
    ResultEntry,
    RoundDocument,
)
from seebach.interchange.port import (
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
    "manager_for",
    "register",
]
