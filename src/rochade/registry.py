"""Import every use case so that its handler and route are registered.

Explicit rather than a package scan: a missing import here is a failing test,
whereas a scan that silently skips a file is a missing endpoint in production.

Grouped by feature, in the same order as the REST surface, so this file reads
as a table of contents for the API.
"""

from fastapi import APIRouter

from rochade.features.auth import get_auth_config
from rochade.features.boards import get_board_list
from rochade.features.devices import (
    issue_device_token,
    join_code,
    join_device,
    list_devices,
    remove_device,
    revoke_device,
)
from rochade.features.games import claim_result, resolve_dispute, set_result
from rochade.features.imports import import_round, preview_import
from rochade.features.managers import list_managers
from rochade.features.pairing import (
    compute_standings,
    pair_round,
    preview_pairing,
    unpair_round,
)
from rochade.features.players import add_player, list_players, update_player, withdraw_player
from rochade.features.queue import get_arbiter_queue
from rochade.features.rounds import (
    confirm_boards,
    export_round,
    get_round,
    get_round_events,
    release_round,
)
from rochade.features.sections import create_section
from rochade.features.standings import get_standings, import_standings, name_tiebreaks
from rochade.features.tournaments import (
    add_member,
    create_tournament,
    delete_tournament,
    get_tournament,
    list_tournaments,
)

#: Every module that owns routes, in REST order.
MODULES = (
    # /api/auth
    get_auth_config,
    # /api/managers
    list_managers,
    # /api/tournaments
    create_tournament,
    list_tournaments,
    get_tournament,
    add_member,
    delete_tournament,
    # /api/tournaments/{id}/imports
    preview_import,
    import_round,
    # /api/tournaments/{id}/sections -- a section Rochade pairs itself
    create_section,
    # /api/tournaments/{id}/boards
    get_board_list,
    # /api/tournaments/{id}/queue
    get_arbiter_queue,
    # /api/tournaments/{id}/devices, /api/devices/{id}
    issue_device_token,
    list_devices,
    remove_device,
    revoke_device,
    # /api/tournaments/{id}/standings
    get_standings,
    import_standings,
    name_tiebreaks,
    join_code,
    join_device,
    # /api/sections/{id}/players, /api/players/{id}
    list_players,
    add_player,
    update_player,
    withdraw_player,
    # /api/sections/{id}/pairings, /api/sections/{id}/standings
    preview_pairing,
    pair_round,
    compute_standings,
    # /api/rounds/{id}
    get_round,
    get_round_events,
    confirm_boards,
    release_round,
    export_round,
    unpair_round,
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
