"""Vega's tournament-folder files, read as one round.

Vega never exports the round it has just paired (its FIDE rating report
refuses while a game is unfinished), but it writes plain files into the
tournament folder whenever it pairs. ``SortedPairs.txt`` is the boards of the
new round, by name, rewritten at every pairing and every manual change to
one. The players and every result so far come from one of two files beside
it: ``engine26.trf``, the TRF Vega hands its pairing engine (written every
time the engine runs, from round 1 on, with colours, byes and the round
count, but with the names squashed to ``BaumannLukas``), or
``crosstable.txt``, which Vega only starts writing once a result exists.
Either with the pairing list, in any order, is the round; from the second
round on the pairing list alone will do, named from the roster we already
hold.

What comes out is the same ``RoundDocument`` a TRF would have produced, and
its ``source`` *is* a TRF: the two files are turned into one with
``rochade.trf.build``, so the export leg patches result cells into a file we
wrote ourselves and hands Vega a TRF it can import. Prior rounds get their
board numbers from the FIDE rule, the new round keeps Vega's own.

Observed on Vega 12.1.8 -- see ``docs/m0-vega.md``.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

from rochade.interchange.document import PairingRow, PlayerRow, RoundDocument
from rochade.interchange.formats import trf as trf_format
from rochade.interchange.port import InterchangeError
from rochade.trf import Colour, RoundEntry, TrfParseError, parse
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
from rochade.vega.sorted_pairs import SortedPairs

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
    cross_text, pairs_text, trf_text = split_blocks(content)
    if pairs_text is None:
        raise InterchangeError(
            "this is the players on their own; the pairing list belongs with them "
            "(SortedPairs.txt, from the tournament folder after pairing the round)"
        )
    try:
        pairs = parse_sorted_pairs(pairs_text)
    except SortedPairsError as exc:
        raise InterchangeError(f"SortedPairs.txt: {exc}", line_no=exc.line_no) from exc
    round_no = pairs.round_no

    table: CrossTable | None = None
    declared_rounds: int | None = None
    extras: dict[int, tuple[str, str]] = {}
    history: dict[int, dict[int, RoundEntry]] = {}
    if trf_text is not None:
        roster, history, extras, declared_rounds = _from_trf(
            trf_text, pairs, known_players, upto=round_no - 1
        )
    elif cross_text is not None:
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
            "this is SortedPairs.txt on its own; the players belong with it -- "
            "engine26.trf or crosstable.txt from the same tournament folder"
        )
    if table is not None:
        history = _history(table, upto=round_no - 1, roster=roster)

    by_name = {_squash(p.name): rank for rank, p in roster.items()}

    def rank_of(name: str, board: int) -> int:
        rank = by_name.get(_squash(name))
        if rank is None:
            hint = (
                "a player was added, so hand over engine26.trf (or crosstable.txt) "
                "with the pairing list"
                if cross_text is None and trf_text is None
                else "hand over the files from the same tournament folder"
            )
            raise InterchangeError(
                f"board {board} names {name!r}, who is not in the players -- {hint}"
            )
        return rank

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
                    sex=extras.get(rank, ("", ""))[0],
                    title=player.title,
                    rating=player.rating,
                    federation=player.federation,
                    fide_id=player.fide_id,
                    birth_date=extras.get(rank, ("", ""))[1],
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
        declared_rounds=declared_rounds,
        unknown_result_codes=table.unknown_cells if table else [],
        standings_from_file=False,
    )


def split_blocks(content: str) -> tuple[str | None, str | None, str | None]:
    """Cut one content string into the cross table, the pairing list and the TRF.

    Any may be absent and they may come in any order. The cross table is taken
    from its "Cross Table at round N" line; the two title lines Vega writes
    above it are not needed, so a pairing list that swallows them is fine. A
    TRF announces itself with its record codes, one per line.
    """
    cross: list[str] = []
    pairs: list[str] = []
    trf: list[str] = []
    current: list[str] | None = None
    for line in _lines(content):
        if looks_like_cross_table(line):
            current = cross
        elif looks_like_sorted_pairs(line.strip()):
            current = pairs
        elif _TRF_LINE.match(line) and current is not trf:
            current = trf
        if current is not None:
            current.append(line)
    return (
        "\n".join(cross) if cross else None,
        "\n".join(pairs) if pairs else None,
        "\n".join(trf) if trf else None,
    )


#: A TRF record: a three-digit code (or an XX extension) and a space.
_TRF_LINE = re.compile(r"^(\d{3}|XX[A-Z])( |$)")


def _from_trf(
    text: str,
    pairs: SortedPairs,
    known_players: Mapping[int, PlayerRow] | None,
    *,
    upto: int,
) -> tuple[
    dict[int, PlayerRow],
    dict[int, dict[int, RoundEntry]],
    dict[int, tuple[str, str]],
    int | None,
]:
    """The roster and history from ``engine26.trf``.

    Vega squashes names in this file (``Baumann, Lukas`` becomes
    ``BaumannLukas``), so every player on the pairing list is renamed to the
    list's spelling, and a player who sat the round out keeps the name we
    already hold or, failing that, an unsquashed guess. The file is written
    when the engine pairs, before the pairing, so it ends one round before
    the list; if it ends earlier the engine did not run for the last round
    and its results are missing -- the cross table is the way then.
    """
    try:
        trf = parse(text)
    except TrfParseError as exc:
        raise InterchangeError(f"engine26.trf: {exc}", line_no=exc.line_no) from exc
    if not trf.players:
        raise InterchangeError("engine26.trf: no players in it")
    if trf.rounds_present < upto:
        raise InterchangeError(
            f"engine26.trf ends at round {trf.rounds_present} but the pairing list is "
            f"round {upto + 1}: Vega did not run its engine for round {upto}, so the "
            "file is behind -- hand over crosstable.txt instead"
        )
    listed = {
        _squash(name): name
        for pair in pairs.boards
        for name in (pair.white, pair.black)
        if name is not None
    }
    roster: dict[int, PlayerRow] = {}
    history: dict[int, dict[int, RoundEntry]] = {}
    extras: dict[int, tuple[str, str]] = {}
    for rank, player in trf.players.items():
        held = known_players.get(rank) if known_players else None
        name = listed.get(_squash(player.name)) or (held.name if held else None)
        roster[rank] = PlayerRow(
            start_rank=rank,
            name=name or _unsquash(player.name),
            title=player.title,
            rating=player.rating or None,  # 0 is Vega's unrated
            federation=player.federation,
            fide_id="" if player.fide_id in ("", "0") else player.fide_id,
            points=player.points,
        )
        history[rank] = {
            r: entry for r, entry in player.rounds.items() if r <= upto and entry.result != " "
        }
        extras[rank] = (player.sex, player.birth_date)
    return roster, history, extras, trf.declared_rounds


def _unsquash(name: str) -> str:
    """``BaumannLukas`` -> ``Baumann, Lukas``: Vega's squash undone at the
    first lower-to-upper step. A guess, used only for a player the pairing
    list does not name and the section does not hold yet."""
    match = re.search(r"[a-z\u00df-\u00ff][A-Z\u00c0-\u00de]", name)
    if match is None:
        return name
    cut = match.start() + 1
    return f"{name[:cut]}, {name[cut:]}"


def _squash(name: str) -> str:
    """The name as Vega's engine file spells it, casefolded: letters and digits only."""
    return "".join(ch for ch in name.casefold() if ch.isalnum())


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


def _lines(content: str) -> list[str]:
    return [
        line.lstrip("﻿") for line in content.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    ]
