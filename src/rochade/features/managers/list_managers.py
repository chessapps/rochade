"""Which tournament managers this build can talk to, and what each one costs.

The admin app needs this to offer a choice on import, but the capability flags
matter more than the list: an arbiter about to send results to a program that
cannot carry a forfeit should be told before the round, not after it.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from rochade.interchange import Support, available
from rochade.platform.bus import bus
from rochade.platform.http import get_context
from rochade.platform.mediator import Access, Context, Query

router = APIRouter(prefix="/managers", tags=["managers"])


class ManagerSummary(BaseModel):
    key: str
    label: str
    reads_format: str
    writes_format: str
    exports_unplayed_round: Support
    merges_on_import: Support
    #: False while any capability is still UNVERIFIED -- that is, until the M0
    #: spike has actually been run against the real program. Shown to the
    #: arbiter, because "we read this in the manual" is not the same claim as
    #: "we watched it work".
    verified: bool
    result_codes_out: list[str] = Field(default_factory=list)
    #: One menu path each -- what the arbiter does in the manager before and
    #: after a round here. Shown at those two moments and nowhere else.
    export_howto: str = ""
    import_howto: str = ""
    notes: list[str] = Field(default_factory=list)


class ListManagers(Query):
    access = Access.STAFF


@bus.register(ListManagers)
def handle(query: ListManagers, ctx: Context) -> list[ManagerSummary]:
    return [
        ManagerSummary(
            key=manager.key,
            label=manager.label,
            reads_format=manager.capabilities.reads_format,
            writes_format=manager.capabilities.writes_format,
            exports_unplayed_round=manager.capabilities.exports_unplayed_round,
            merges_on_import=manager.capabilities.merges_on_import,
            verified=manager.capabilities.verified,
            result_codes_out=sorted(manager.capabilities.result_codes_out),
            export_howto=manager.capabilities.export_howto,
            import_howto=manager.capabilities.import_howto,
            notes=list(manager.capabilities.notes),
        )
        for manager in available()
    ]


@router.get("", response_model=list[ManagerSummary])
def list_managers(ctx: Context = Depends(get_context)) -> list[ManagerSummary]:
    result: list[ManagerSummary] = bus.send(ListManagers(), ctx)
    return result
