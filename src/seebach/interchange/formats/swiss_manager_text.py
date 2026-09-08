"""Swiss-Manager's two text exports, read as one round.

`Extras -> Daten Import/Export` writes the tournament as plain text in two
pieces: **Spielerdaten**, which is the players by start number, and
**Spielerauslosung**, which is the boards of one or more rounds. Neither goes
near the TRF16 export, and both are four clicks.

They are read here as a single document because that is what they are: the
pairing file names nobody, the player file pairs nobody, and they join on the
start number. The two files arrive as one content string, in either order, with
their own header lines telling them apart -- so an arbiter can hand over both
without anyone having to invent an envelope format.

From the second round on, the player file is optional: the roster we hold from
the last import names the start numbers just as well, and only changes when a
player is added or removed, which the next player file corrects.

A half-point bye is a player status in Swiss-Manager, not a pairing, so it does
not appear in either file; a player holding one is simply absent from that
round. TRF16 would have said `H`. Nothing else observed on 15.0.0.3 is lost.
"""

from __future__ import annotations

from collections.abc import Mapping

from seebach.interchange.document import PairingRow, PlayerRow, RoundDocument
from seebach.interchange.port import InterchangeError
from seebach.swiss_manager.pairing_file import HEADER as PAIRING_HEADER
from seebach.swiss_manager.pairing_file import PairingFileError, parse_pairing_file
from seebach.swiss_manager.player_file import (
    PlayerFileError,
    by_start_number,
    looks_like_player_file,
    parse_player_file,
)

#: The pairing-allocated bye, as TRF spells it. Swiss-Manager's own row says
#: nothing about what a bye is worth -- that is a tournament setting there --
#: so the code is ours to supply, and this is the one it always means.
BYE_CODE = "U"


def looks_like(content: str) -> bool:
    """Is this Swiss-Manager's text export rather than a TRF?"""
    for line in content.replace("\r\n", "\n").split("\n"):
        stripped = line.strip().lstrip("﻿")
        if not stripped:
            continue
        if stripped == PAIRING_HEADER or looks_like_player_file(stripped):
            return True
    return False


def read_document(
    content: str, known_players: Mapping[int, PlayerRow] | None = None
) -> RoundDocument:
    """Join the two files; or the pairings alone with the roster already held."""
    players_text, pairings_text = split_blocks(content)
    if pairings_text is None:
        raise InterchangeError(
            "this is the player file on its own; the pairings belong with it "
            "(Extras → Daten Import/Export → Spielerauslosung)"
        )

    if players_text is not None:
        try:
            roster: Mapping[int, PlayerRow] = {
                number: PlayerRow(
                    start_rank=number,
                    name=player.name,
                    title=player.title,
                    rating=player.rating,
                    federation=player.federation,
                    fide_id=player.fide_id,
                    points=player.points,
                    tiebreaks=player.tiebreaks,
                    rank=player.rank,
                )
                for number, player in by_start_number(parse_player_file(players_text)).items()
            }
        except PlayerFileError as exc:
            raise InterchangeError(f"player file: {exc}", line_no=exc.line_no) from exc
    elif known_players:
        roster = known_players
    else:
        raise InterchangeError(
            "this is the pairing file on its own; the player file belongs with it "
            "(Extras → Daten Import/Export → Spielerdaten), or the boards have no names"
        )
    try:
        lines = parse_pairing_file(pairings_text)
    except PairingFileError as exc:
        raise InterchangeError(f"pairing file: {exc}", line_no=exc.line_no) from exc

    if not lines:
        raise InterchangeError("the pairing file has no boards")

    def name_of(start_number: int) -> str:
        player = roster.get(start_number)
        if player is None:
            if players_text is None:
                raise InterchangeError(
                    f"the pairings use start number {start_number}, which the last "
                    "player file did not have -- a player was added, so export "
                    "Spielerdaten again and hand it over with the pairings"
                )
            raise InterchangeError(
                f"the pairings use start number {start_number}, which the player file "
                "does not have -- export both files from the same tournament"
            )
        return player.name

    pairings: dict[int, list[PairingRow]] = {}
    for line in sorted(lines, key=lambda row: (row.round_no, row.board)):
        pairings.setdefault(line.round_no, []).append(
            PairingRow(
                board=line.board,
                white_rank=line.white,
                white_name=name_of(line.white),
                black_rank=line.black,
                black_name=None if line.is_bye else name_of(line.black or 0),
                white_result=BYE_CODE if line.is_bye else line.white_result,
                black_result=" " if line.is_bye else line.black_result,
            )
        )

    return RoundDocument(
        round_number=max(pairings),
        players={number: roster[number] for number in sorted(roster)},
        pairings=pairings,
        source=content,
        standings_from_file=players_text is not None,
    )


def split_blocks(content: str) -> tuple[str | None, str | None]:
    """Cut one content string into its player and pairing halves.

    Either may be absent and either may come first; anything before the first
    header is ignored, which is what makes a plain `cat` of the two files work.
    """
    players: list[str] = []
    pairings: list[str] = []
    current: list[str] | None = None
    for line in content.replace("\r\n", "\n").split("\n"):
        stripped = line.strip().lstrip("﻿")
        if stripped == PAIRING_HEADER:
            current = pairings
        elif looks_like_player_file(stripped):
            current = players
        if current is not None:
            current.append(line.lstrip("﻿"))
    return (
        "\n".join(players) if players else None,
        "\n".join(pairings) if pairings else None,
    )
