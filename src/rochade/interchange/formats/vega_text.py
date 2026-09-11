"""Vega's tournament-folder files, read as one round.

Vega never exports the round it has just paired (its FIDE rating report
refuses while a game is unfinished), but it rewrites two plain files in the
tournament folder every time it pairs or the arbiter changes a pairing:
``crosstable.txt`` -- the players and every result so far -- and
``SortedPairs.txt`` -- the boards of the new round, by name. Handed over
together, in either order, they are the round; from the second round on the
pairing list alone will do, named from the roster we already hold.

What comes out is the same ``RoundDocument`` a TRF would have produced, and
its ``source`` *is* a TRF: the two files are turned into one with
``rochade.trf.build``, so the export leg patches result cells into a file we
wrote ourselves and hands Vega a TRF it can import. Prior rounds get their
board numbers from the FIDE rule, the new round keeps Vega's own.

Observed on Vega 12.1.8 -- see ``docs/m0-vega.md``.
"""

from __future__ import annotations

from collections.abc import Mapping

from rochade.interchange.document import PairingRow, PlayerRow, RoundDocument
from rochade.interchange.formats import trf as trf_format
from rochade.interchange.port import InterchangeError
from rochade.trf import Colour, RoundEntry
from rochade.trf.build import BuildDocument, BuildPlayer, build
from rochade.vega import (
    CrossTable,
    CrossTableError,
    SortedPairsError,
    looks_like_cross_table,
    looks_like_sorted_pairs,
    parse_cross_table,
    parse_sorted_pairs,
)

#: The pairing-allocated bye, as TRF spells it. Vega's list says "BYE" and
#: nothing about its value; a half-point bye is a player status there and the
#: player is simply absent from the list, as with Swiss-Manager.
BYE_CODE = "U"


def looks_like(content: str) -> bool:
    """Is this Vega's cross table and/or pairing list rather than a TRF?"""
    for line in _lines(content):
        if looks_like_cross_table(line) or looks_like_sorted_pairs(line.strip()):
            return True
    return False


def read_document(
    content: str, known_players: Mapping[int, PlayerRow] | None = None
) -> RoundDocument:
    cross_text, pairs_text = split_blocks(content)
    if pairs_text is None:
        raise InterchangeError(
            "this is crosstable.txt on its own; the pairing list belongs with it "
            "(SortedPairs.txt, from the tournament folder after pairing the round)"
        )
    try:
        pairs = parse_sorted_pairs(pairs_text)
    except SortedPairsError as exc:
        raise InterchangeError(f"SortedPairs.txt: {exc}", line_no=exc.line_no) from exc

    table: CrossTable | None = None
    if cross_text is not None:
        try:
            table = parse_cross_table(cross_text)
        except CrossTableError as exc:
            raise InterchangeError(f"crosstable.txt: {exc}", line_no=exc.line_no) from exc
        roster = {
            row.number: PlayerRow(
                start_rank=row.number,
                name=row.name,
                title=row.title,
                rating=row.rating,
                federation=row.federation,
                points=row.points,
            )
            for row in table.rows
        }
    elif known_players:
        roster = dict(known_players)
    else:
        raise InterchangeError(
            "this is SortedPairs.txt on its own; crosstable.txt belongs with it "
            "(both are in the tournament folder), or the boards have no start numbers"
        )

    by_name = {_key(p.name): rank for rank, p in roster.items()}

    def rank_of(name: str, board: int) -> int:
        rank = by_name.get(_key(name))
        if rank is None:
            hint = (
                "a player was added, so hand over crosstable.txt with the pairing list"
                if cross_text is None
                else "hand over both files from the same tournament folder"
            )
            raise InterchangeError(
                f"board {board} names {name!r}, who is not in the players -- {hint}"
            )
        return rank

    round_no = pairs.round_no
    history = _history(table, upto=round_no - 1, roster=roster)
    rounds: dict[int, dict[int, RoundEntry]] = {rank: {} for rank in roster}
    for rank, entries in history.items():
        rounds[rank].update(entries)

    new_round: list[PairingRow] = []
    seen: set[int] = set()
    for pair in pairs.boards:
        white = rank_of(pair.white, pair.board)
        black = None if pair.black is None else rank_of(pair.black, pair.board)
        for who in (white, black):
            if who is None:
                continue
            if who in seen:
                raise InterchangeError(
                    f"board {pair.board}: {roster[who].name!r} is paired twice in round {round_no}"
                )
            seen.add(who)
        if black is None:
            rounds[white][round_no] = RoundEntry(round_no, None, Colour.NONE, BYE_CODE)
        else:
            rounds[white][round_no] = RoundEntry(round_no, black, Colour.WHITE, " ")
            rounds[black][round_no] = RoundEntry(round_no, white, Colour.BLACK, " ")
        new_round.append(
            PairingRow(
                board=pair.board,
                white_rank=white,
                white_name=roster[white].name,
                black_rank=black,
                black_name=None if black is None else roster[black].name,
                white_result=BYE_CODE if black is None else " ",
            )
        )

    name = pairs.tournament_name or (table.tournament_name if table else "")
    text = build(
        BuildDocument(
            name=name,
            players=[
                BuildPlayer(
                    start_rank=rank,
                    name=player.name,
                    title=player.title,
                    rating=player.rating,
                    federation=player.federation,
                    fide_id=player.fide_id,
                    rounds=rounds[rank],
                )
                for rank, player in sorted(roster.items())
            ],
        )
    )
    # The TRF library numbers the earlier rounds' boards by the FIDE rule and
    # checks the file for us; the new round keeps the numbers Vega printed.
    document = trf_format.read_document(text)
    pairings = {r: rows for r, rows in document.pairings.items() if r < round_no}
    pairings[round_no] = sorted(new_round, key=lambda row: row.board)

    return RoundDocument(
        round_number=round_no,
        players={rank: roster[rank] for rank in sorted(roster)},
        pairings=pairings,
        source=text,
        tournament_name=name,
        declared_rounds=None,
        unknown_result_codes=table.unknown_cells if table else [],
        standings_from_file=False,
    )


def split_blocks(content: str) -> tuple[str | None, str | None]:
    """Cut one content string into the cross table and the pairing list.

    Either may be absent and either may come first. The cross table is taken
    from its "Cross Table at round N" line; the two title lines Vega writes
    above it are not needed, so a pairing list that swallows them is fine.
    """
    cross: list[str] = []
    pairs: list[str] = []
    current: list[str] | None = None
    for line in _lines(content):
        if looks_like_cross_table(line):
            current = cross
        elif looks_like_sorted_pairs(line.strip()):
            current = pairs
        if current is not None:
            current.append(line)
    return ("\n".join(cross) if cross else None, "\n".join(pairs) if pairs else None)


def _history(
    table: CrossTable | None, *, upto: int, roster: Mapping[int, PlayerRow]
) -> dict[int, dict[int, RoundEntry]]:
    """Earlier rounds from the cross table, as TRF round entries per player.

    A forfeit cell names the opponent but not the colour; the lower start
    number is written as white so the pair stays consistent. The Dutch rules
    do not count unplayed games for colour, so the guess costs nothing in the
    next pairing.
    """
    out: dict[int, dict[int, RoundEntry]] = {}
    if table is None:
        return out
    for row in table.rows:
        entries: dict[int, RoundEntry] = {}
        for cell in row.cells:
            if cell.round_no > upto or not cell.known or cell.result == " ":
                continue
            if cell.opponent is None:
                entries[cell.round_no] = RoundEntry(cell.round_no, None, Colour.NONE, cell.result)
                continue
            if cell.opponent not in roster:
                raise InterchangeError(
                    f"crosstable.txt: round {cell.round_no} pairs {row.name!r} with start "
                    f"number {cell.opponent}, which the table does not have"
                )
            colour = (
                Colour(cell.colour)
                if cell.colour != "-"
                else (Colour.WHITE if row.number < cell.opponent else Colour.BLACK)
            )
            entries[cell.round_no] = RoundEntry(cell.round_no, cell.opponent, colour, cell.result)
        out[row.number] = entries
    return out


def _key(name: str) -> str:
    return " ".join(name.casefold().split())


def _lines(content: str) -> list[str]:
    return [
        line.lstrip("﻿") for line in content.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    ]
