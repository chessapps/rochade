"""The manager port: the one interface every tournament manager plugs into.

The port is not "which file format". It is *who owns the pairings and the
standings*. Vega and Swiss-Manager answer by exchanging files; our own
implementation, when it arrives, will answer without a file existing at all,
and it satisfies the same interface.

An adapter must declare what it cannot do. `Capabilities` is part of the
interface rather than a footnote, because the failure this design is most
exposed to -- handing a manager a file it silently mangles -- is only visible
if the adapter says in advance what it drops.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import ClassVar, Protocol, runtime_checkable

from seebach.interchange.document import ManagerFile, ResultEntry, RoundDocument


class Support(StrEnum):
    """Whether a behaviour has actually been observed against the real program.

    UNVERIFIED is the honest default and the whole point of the enum: until the
    M0 spike is run against a program, we are repeating documentation rather
    than reporting a fact, and an arbiter deserves to be told which it is.
    """

    YES = "yes"
    NO = "no"
    UNVERIFIED = "unverified"


@dataclass(frozen=True, slots=True)
class Capabilities:
    #: Does the manager export a round that is paired but not yet played? If
    #: not, there is no open board for players to enter and the loop cannot
    #: start, whatever the import side supports.
    exports_unplayed_round: Support = Support.UNVERIFIED
    #: Does importing our file merge into the existing tournament, rather than
    #: rejecting it or creating a duplicate?
    merges_on_import: Support = Support.UNVERIFIED
    #: TRF result codes that survive the outbound trip. Anything a round holds
    #: that is not in here is lost, and the arbiter is told before exporting.
    result_codes_out: frozenset[str] = frozenset()
    #: Named from our side, so there is no "inbound to whom" ambiguity:
    #: what we read from the manager, and what we write back to it. They are
    #: not always the same format.
    reads_format: str = ""
    writes_format: str = ""
    notes: tuple[str, ...] = ()

    def drops(self, codes: Sequence[str]) -> list[str]:
        """Which of these result codes this manager cannot carry out."""
        return sorted({c for c in codes if c.strip() and c not in self.result_codes_out})

    @property
    def verified(self) -> bool:
        return Support.UNVERIFIED not in (self.exports_unplayed_round, self.merges_on_import)


@runtime_checkable
class Manager(Protocol):
    """What every adapter provides. Two methods, one direction each."""

    key: ClassVar[str]
    label: ClassVar[str]
    capabilities: ClassVar[Capabilities]

    def read_round(self, content: str) -> RoundDocument:
        """Turn one manager export into a format-neutral document."""
        ...

    def write_results(
        self,
        document: RoundDocument,
        round_number: int,
        results: Sequence[ResultEntry],
        *,
        stem: str,
    ) -> ManagerFile:
        """Write confirmed results back into something the manager will take."""
        ...


_REGISTRY: dict[str, Manager] = {}


def register(manager: Manager) -> Manager:
    if manager.key in _REGISTRY:
        raise RuntimeError(f"a manager is already registered as {manager.key!r}")
    _REGISTRY[manager.key] = manager
    return manager


def manager_for(key: str) -> Manager:
    try:
        return _REGISTRY[key]
    except KeyError:
        known = ", ".join(sorted(_REGISTRY)) or "none"
        raise UnknownManager(f"no manager adapter named {key!r}; known: {known}") from None


def available() -> list[Manager]:
    return [_REGISTRY[key] for key in sorted(_REGISTRY)]


class UnknownManager(LookupError):
    pass


class InterchangeError(ValueError):
    """An adapter could not read what the manager gave it.

    Formats differ, so the exception a format library raises differs too. This
    is the one type the features catch, which is what keeps them free of any
    knowledge about TRF.
    """

    def __init__(self, message: str, *, line_no: int | None = None) -> None:
        super().__init__(message)
        self.line_no = line_no


@dataclass(frozen=True, slots=True)
class ManagerInfo:
    """The read-only view the admin app needs to offer a choice."""

    key: str
    label: str
    capabilities: Capabilities
    warnings: tuple[str, ...] = field(default_factory=tuple)
