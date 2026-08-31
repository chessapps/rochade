"""Import every use case so that its handler and route are registered.

Explicit rather than a package scan: a missing import here is a failing test,
whereas a scan that silently skips a file is a missing endpoint in production.
"""

from fastapi import APIRouter

from seebach.commands import (
    add_member,
    claim_result,
    create_tournament,
    export_round,
    import_round,
    issue_device_token,
    release_round,
    resolve_dispute,
    revoke_device,
    set_result,
)
from seebach.queries import (
    get_arbiter_queue,
    get_board_list,
    get_round,
    get_tournament,
    list_devices,
    list_tournaments,
    preview_import,
)

MODULES = (
    create_tournament,
    add_member,
    import_round,
    export_round,
    claim_result,
    set_result,
    resolve_dispute,
    release_round,
    issue_device_token,
    revoke_device,
    get_tournament,
    list_tournaments,
    get_round,
    preview_import,
    get_board_list,
    get_arbiter_queue,
    list_devices,
)


def api_router() -> APIRouter:
    router = APIRouter()
    for module in MODULES:
        router.include_router(module.router)
    return router
