"""Import every use case so that its handler and route are registered.

Explicit rather than a package scan: a missing import here is a failing test,
whereas a scan that silently skips a file is a missing endpoint in production.

Grouped by feature, in the same order as the REST surface, so this file reads
as a table of contents for the API.
"""

from fastapi import APIRouter

from seebach.features.boards import get_board_list
from seebach.features.devices import issue_device_token, list_devices, revoke_device
from seebach.features.games import claim_result, resolve_dispute, set_result
from seebach.features.imports import import_round, preview_import
from seebach.features.managers import list_managers
from seebach.features.queue import get_arbiter_queue
from seebach.features.rounds import export_round, get_round, get_round_events, release_round
from seebach.features.tournaments import (
    add_member,
    create_tournament,
    get_tournament,
    list_tournaments,
)

#: Every module that owns routes, in REST order.
MODULES = (
    # /api/managers
    list_managers,
    # /api/tournaments
    create_tournament,
    list_tournaments,
    get_tournament,
    add_member,
    # /api/tournaments/{id}/imports
    preview_import,
    import_round,
    # /api/tournaments/{id}/boards
    get_board_list,
    # /api/tournaments/{id}/queue
    get_arbiter_queue,
    # /api/tournaments/{id}/devices, /api/devices/{id}
    issue_device_token,
    list_devices,
    revoke_device,
    # /api/rounds/{id}
    get_round,
    get_round_events,
    release_round,
    export_round,
    # /api/games/{id}
    claim_result,
    set_result,
    resolve_dispute,
)


def api_router() -> APIRouter:
    router = APIRouter()
    for module in MODULES:
        router.include_router(module.router)
    return router
