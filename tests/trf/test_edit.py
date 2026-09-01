import pytest

from seebach.trf import Dialect, parse, serialize
from seebach.trf.edit import set_result
from seebach.trf.results import mirror, points_for

#: Built from character codes: every attempt to write this escape literally
#: had it turned into a real line break somewhere in the tooling.
CRLF = chr(13) + chr(10)


def test_setting_a_result_mirrors_onto_the_opponent(round3_text: str) -> None:
    trf = parse(round3_text)
    set_result(trf, 3, 1, "1")
    assert trf.player(1).round(3).result == "1"
    assert trf.player(3).round(3).result == "0"


def test_draw_mirrors_to_a_draw(round3_text: str) -> None:
    trf = parse(round3_text)
    set_result(trf, 3, 2, "=")
    assert trf.player(2).round(3).result == "="
    assert trf.player(4).round(3).result == "="


def test_forfeit_win_mirrors_to_forfeit_loss(round3_text: str) -> None:
    trf = parse(round3_text)
    set_result(trf, 3, 5, "+")
    assert trf.player(6).round(3).result == "-"


def test_bye_accepts_only_unplayed_codes(round3_text: str) -> None:
    trf = parse(round3_text)
    set_result(trf, 3, 9, "H")
    assert trf.player(9).round(3).result == "H"
    with pytest.raises(ValueError, match="has a bye"):
        set_result(trf, 3, 9, "1")


def test_unknown_code_is_rejected(round3_text: str) -> None:
    trf = parse(round3_text)
    with pytest.raises(ValueError, match="unknown TRF result code"):
        set_result(trf, 3, 1, "X")


def test_missing_round_is_rejected(round3_text: str) -> None:
    trf = parse(round3_text)
    with pytest.raises(ValueError, match="has no round 4"):
        set_result(trf, 4, 1, "1")


def test_a_file_with_no_points_column_is_left_alone() -> None:
    """Nothing to adjust means nothing to invent."""
    cells = list(" " * 89)
    cells[0:3] = "001"
    cells[4:8] = "   1"
    cells[14:47] = "Nopoints, Ned".ljust(33)
    line = "".join(cells) + "  0000 - U"
    trf = parse("012 T" + CRLF + line + CRLF)
    assert trf.player(1).points is None

    set_result(trf, 1, 1, "H")
    assert serialize(trf, Dialect.TRF16).count("0000 - H") == 1
    assert trf.points_changed == set()


def test_edits_appear_in_the_serialized_file(round3_text: str) -> None:
    trf = parse(round3_text)
    set_result(trf, 3, 1, "1")
    set_result(trf, 3, 5, "=")
    out = serialize(trf, Dialect.TRF16)

    reparsed = parse(out)
    assert reparsed.player(1).round(3).result == "1"
    assert reparsed.player(3).round(3).result == "0"
    assert reparsed.player(5).round(3).result == "="
    assert reparsed.player(6).round(3).result == "="
    # Everything else is untouched.
    assert len(out.split("\r\n")) == len(round3_text.split("\r\n"))
    assert reparsed.player(1).round(1).result == "1"


def test_only_the_result_and_points_columns_move(round3_text: str) -> None:
    """Setting one result touches two rows, and within them only two fields.

    Everything else on those lines -- and every other line in the file -- comes
    back byte for byte, which is the property the whole round trip rests on.
    """
    from seebach.trf import columns

    trf = parse(round3_text)
    set_result(trf, 3, 1, "1")
    before = round3_text.split(CRLF)
    after = serialize(trf, Dialect.TRF16).split(CRLF)

    differing = [i for i, (a, b) in enumerate(zip(before, after, strict=True)) if a != b]
    # Exactly the two player rows of that one game.
    assert len(differing) == 2

    allowed = set(range(columns.POINTS.start, columns.POINTS.stop))
    allowed.add(columns_result_index(3))
    for i in differing:
        diffs = {j for j, (a, b) in enumerate(zip(before[i], after[i], strict=True)) if a != b}
        assert diffs <= allowed
        assert columns_result_index(3) in diffs


def columns_result_index(round_no: int) -> int:
    from seebach.trf import columns

    return columns.result_index(round_no)


def test_points_move_by_what_we_wrote(round3_text: str) -> None:
    trf = parse(round3_text)
    set_result(trf, 3, 1, "1")
    reparsed = parse(serialize(trf, Dialect.TRF16))

    assert reparsed.player(1).points == 3.0  # 2.0 in the file, plus the win
    assert reparsed.player(3).points == 1.5  # 1.5 in the file, plus nothing
    assert reparsed.player(4).points == pytest.approx(1.5)  # untouched


def test_points_we_did_not_change_are_left_exactly_as_the_manager_wrote_them(
    round3_text: str,
) -> None:
    """Never recompute the whole column.

    Player 8 has a pairing-allocated bye scored 0.5 in this file. Our table says
    a `U` is worth 1.0, but what a PAB is worth is a tournament regulation, not
    a property of the letter -- some events award a half point. Recomputing
    would silently overwrite the arbiter's number with our assumption.
    """
    trf = parse(round3_text)
    assert trf.player(8).points == 0.5
    set_result(trf, 3, 1, "1")

    out = serialize(trf, Dialect.TRF16)
    assert parse(out).player(8).points == 0.5

    changed = [
        i
        for i, (a, b) in enumerate(zip(round3_text.split(CRLF), out.split(CRLF), strict=True))
        if a != b
    ]
    # Exactly the two rows of the one game we set.
    assert len(changed) == 2


def test_points_survive_double_digits() -> None:
    cells = list(" " * 89)
    cells[0:3] = "001"
    cells[4:8] = "   1"
    cells[14:47] = "Long, Player".ljust(33)
    cells[80:84] = "10.5"
    trf = parse("012 T\r\n" + "".join(cells) + "\r\n")
    assert trf.player(1).points == 10.5


def test_mirror_and_points_table_agree() -> None:
    for code in ("1", "0", "=", "W", "L", "D"):
        assert points_for(code) + points_for(mirror(code)) == 1.0


def test_byes_have_no_opponent_side() -> None:
    for code in ("H", "F", "U", "Z"):
        with pytest.raises(ValueError, match="no opponent side"):
            mirror(code)


def test_trf06_folds_characters_cp1252_cannot_carry() -> None:
    trf = parse("012 T\r\n001    1 m    Łukasz, Nowak\r\n")
    out = serialize(trf, Dialect.TRF06)
    assert "?ukasz" in out
    # Fixed columns are preserved: substitution is one character for one.
    assert len(out) == len(serialize(trf, Dialect.TRF16))


def test_an_explicit_opponent_code_must_make_a_game(round3_text: str) -> None:
    """("-", "-") is the one pair that is not a mirror; anything else is refused."""
    trf = parse(round3_text)
    game = next(p for p in trf.pairings(3) if not p.is_bye)
    set_result(trf, 3, game.white, "-", opponent_code="-")
    assert trf.player(game.white).round(3).result == "-"
    assert trf.player(game.black).round(3).result == "-"
    with pytest.raises(ValueError, match="not a game"):
        set_result(trf, 3, game.white, "1", opponent_code="1")
