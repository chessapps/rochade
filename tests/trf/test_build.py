"""The from-scratch TRF builder, checked against the parser it must satisfy."""

from __future__ import annotations

import pathlib

from hypothesis import given, settings
from hypothesis import strategies as st

from rochade.trf import Colour, Dialect, RoundEntry, parse, serialize
from rochade.trf.build import BuildDocument, BuildPlayer, build

FIXTURES = pathlib.Path(__file__).resolve().parents[1] / "fixtures"


def _entry(round_no: int, opponent: int | None, colour: str, result: str) -> RoundEntry:
    return RoundEntry(round_no=round_no, opponent=opponent, colour=Colour(colour), result=result)


def _messy() -> BuildDocument:
    """The nine players of round3_messy.trf, rebuilt from typed rows."""
    rows = [
        (1, "m", "FM", "Baumann, Lukas", 2201, "SUI", "1300001", "1990/04/02"),
        (2, "m", "", "Chen, Wei", 2150, "SUI", "1300002", "1995/11/23"),
        (3, "w", "WFM", "Dubois, Elise", 2098, "FRA", "1300003", "2001/07/09"),
        (4, "m", "", "Egger, Tobias", 2044, "AUT", "1300004", "1988/01/30"),
        (5, "m", "", "Fischer, Jonas", 1987, "GER", "1300005", "2003/05/17"),
        (6, "w", "", "Gruber, Sarah", 1922, "SUI", "1300006", "1999/09/12"),
        (7, "m", "", "Huber, Marco", 1870, "SUI", "1300007", "1975/12/01"),
        (8, "w", "", "Iten, Nadia", 1804, "SUI", "1300008", "2007/02/28"),
        (9, "m", "", "Jenni, Rafael", 1755, "SUI", "1300009", "2010/06/05"),
    ]
    games: dict[int, list[tuple[int | None, str, str]]] = {
        1: [(5, "w", "1"), (2, "b", "1"), (3, "w", " ")],
        2: [(6, "b", "1"), (1, "w", "0"), (4, "b", " ")],
        3: [(7, "w", "="), (8, "b", "1"), (1, "b", " ")],
        4: [(None, "-", "H"), (9, "w", "1"), (2, "w", " ")],
        5: [(1, "b", "0"), (7, "w", "+"), (6, "w", " ")],
        6: [(2, "w", "0"), (None, "-", "Z"), (5, "b", " ")],
        7: [(3, "b", "="), (5, "b", "-"), (8, "w", " ")],
        8: [(None, "-", "U"), (3, "w", "0"), (7, "b", " ")],
        9: [(None, "-", "Z"), (4, "b", "0"), (None, "-", "Z")],
    }
    players = [
        BuildPlayer(
            start_rank=rank,
            sex=sex,
            title=title,
            name=name,
            rating=rating,
            federation=fed,
            fide_id=fide,
            birth_date=birth,
            rounds={
                i: _entry(i, opp, col, res) for i, (opp, col, res) in enumerate(games[rank], 1)
            },
        )
        for rank, sex, title, name, rating, fed, fide, birth in rows
    ]
    return BuildDocument(
        name="Rochade Open 2026",
        city="Rochade",
        federation="SUI",
        start_date="2026/03/14",
        end_date="2026/03/15",
        declared_rounds=5,
        players=players,
    )


def test_the_player_lines_match_the_hand_built_fixture() -> None:
    """Same players, same games: the 001 lines come out the same.

    Two allowances. The fixture keeps the trailing blank of an unplayed
    result and the builder trims it, as real files do. And the fixture's
    hand-typed points give player 8 half a point for a pairing-allocated bye,
    where the code table (and C.04.1) says a full one, which also moves the
    provisional ranks; those two cells are compared in the next test.
    """
    ours = [line for line in build(_messy()).split("\r\n") if line.startswith("001")]
    theirs = [
        line.rstrip()
        for line in (FIXTURES / "round3_messy.trf").read_bytes().decode().split("\r\n")
        if line.startswith("001")
    ]
    mask = slice(80, 89)
    assert [o[: mask.start] + o[mask.stop :] for o in ours] == [
        t[: mask.start] + t[mask.stop :] for t in theirs
    ]
    assert ours[7][80:84] == " 1.0"


def test_the_parser_reads_back_every_field() -> None:
    document = _messy()
    trf = parse(build(document))
    assert trf.name == "Rochade Open 2026"
    assert trf.city == "Rochade"
    assert trf.federation == "SUI"
    assert trf.declared_rounds == 5
    assert trf.rounds_present == 3
    assert len(trf.players) == 9

    egger = trf.player(4)
    assert (egger.title, egger.rating, egger.federation) == ("", 2044, "AUT")
    assert egger.fide_id == "1300004"
    assert egger.birth_date == "1988/01/30"
    assert egger.points == 1.5
    assert egger.round(1) is not None and egger.round(1).is_bye
    assert egger.round(1).result == "H"
    assert egger.round(2).opponent == 9
    assert egger.round(2).colour is Colour.WHITE

    jenni = trf.player(9)
    assert jenni.points == 0.0
    assert jenni.round(3).result == "Z"


def test_points_come_from_the_results_and_ranks_follow_them() -> None:
    trf = parse(build(_messy()))
    assert {rank: p.points for rank, p in trf.players.items()} == {
        1: 2.0,
        2: 1.0,
        3: 1.5,
        4: 1.5,
        5: 1.0,
        6: 0.0,
        7: 0.5,
        8: 1.0,
        9: 0.0,
    }
    assert trf.player(1).rank == 1
    assert trf.player(3).rank == 2
    assert trf.player(4).rank == 3


def test_board_order_of_an_open_round_is_the_fide_order() -> None:
    trf = parse(build(_messy()))
    boards = [(p.board, p.white, p.black) for p in trf.pairings(3)]
    # Before round 3: 1 has 2.0; 3 and 4 have 1.5; 2, 5 and 8 have 1.0; 7 has
    # 0.5; 6 and 9 nothing. Higher score first, then the sum, byes last.
    assert boards == [(1, 1, 3), (2, 4, 2), (3, 7, 8), (4, 5, 6), (5, 9, None)]


def test_a_late_entry_has_blank_blocks_for_rounds_it_missed() -> None:
    late = BuildPlayer(start_rank=3, name="Late, Larry", rounds={2: _entry(2, 1, "b", "0")})
    others = [
        BuildPlayer(
            start_rank=1,
            name="One, Ann",
            rounds={1: _entry(1, 2, "w", "1"), 2: _entry(2, 3, "w", "1")},
        ),
        BuildPlayer(
            start_rank=2,
            name="Two, Bob",
            rounds={1: _entry(1, 1, "b", "0"), 2: _entry(2, None, "-", "U")},
        ),
    ]
    text = build(BuildDocument(name="Late", players=[*others, late]))
    line = next(line for line in text.split("\r\n") if line.startswith("001    3"))
    assert line[91:101] == " " * 10
    trf = parse(text)
    assert trf.player(3).round(1) is None
    assert trf.player(3).round(2).opponent == 1
    assert trf.player(3).points == 0.0


def test_a_document_with_no_rounds_is_just_a_roster() -> None:
    text = build(
        BuildDocument(
            name="Fresh",
            declared_rounds=5,
            top_colour="white",
            players=[BuildPlayer(start_rank=1, name="A"), BuildPlayer(start_rank=2, name="B")],
        )
    )
    assert "XXR 5\r\n" in text
    assert "XXC white1\r\n" in text
    assert text.endswith("\r\n")
    trf = parse(text)
    assert trf.rounds_present == 0
    assert [p.name for p in trf.players.values()] == ["A", "B"]


def test_an_unrated_player_has_a_blank_rating_cell() -> None:
    text = build(BuildDocument(name="U", players=[BuildPlayer(start_rank=1, name="Nobody")]))
    assert parse(text).player(1).rating is None


_names = st.text(
    alphabet=st.characters(min_codepoint=32, max_codepoint=126, blacklist_characters=","),
    min_size=1,
    max_size=25,
)


@st.composite
def _documents(draw: st.DrawFn) -> BuildDocument:
    count = draw(st.integers(min_value=2, max_value=8))
    rounds = draw(st.integers(min_value=0, max_value=4))
    players: list[BuildPlayer] = []
    for rank in range(1, count + 1):
        entries: dict[int, RoundEntry] = {}
        for round_no in range(1, rounds + 1):
            if draw(st.booleans()):
                continue
            result = draw(st.sampled_from(["1", "=", "0", "+", "-", "H", "U", "Z", " "]))
            if result in ("H", "U", "Z"):
                entries[round_no] = _entry(round_no, None, "-", result)
            else:
                opponent = draw(
                    st.integers(min_value=1, max_value=count).filter(lambda o, me=rank: o != me)
                )
                entries[round_no] = _entry(round_no, opponent, draw(st.sampled_from("wb")), result)
        players.append(
            BuildPlayer(
                start_rank=rank,
                name=draw(_names).strip() or "X",
                rating=draw(st.one_of(st.none(), st.integers(min_value=1000, max_value=2900))),
                rounds=entries,
            )
        )
    return BuildDocument(name="Prop", players=players, declared_rounds=rounds or None)


@given(_documents())
@settings(max_examples=60, deadline=None)
def test_build_then_parse_then_serialize_is_byte_stable(document: BuildDocument) -> None:
    text = build(document)
    trf = parse(text)
    assert serialize(trf, Dialect.TRF16) == text
    for player in document.players:
        parsed = trf.player(player.start_rank)
        assert parsed.name == player.name[:33].strip()
        assert parsed.rating == player.rating
        assert {r: (e.opponent, e.colour, e.result) for r, e in parsed.rounds.items()} == {
            r: (e.opponent, e.colour, e.result) for r, e in player.rounds.items()
        }
