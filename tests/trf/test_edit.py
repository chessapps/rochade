import pytest

from seebach.trf import Dialect, parse, serialize
from seebach.trf.edit import set_result
from seebach.trf.results import mirror, points_for


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


def test_only_the_result_columns_move(round3_text: str) -> None:
    trf = parse(round3_text)
    set_result(trf, 3, 1, "1")
    before = round3_text.split("\r\n")
    after = serialize(trf, Dialect.TRF16).split("\r\n")
    differing = [i for i, (a, b) in enumerate(zip(before, after, strict=True)) if a != b]
    # Exactly the two player rows of that one game.
    assert len(differing) == 2
    for i in differing:
        diffs = [j for j, (a, b) in enumerate(zip(before[i], after[i], strict=True)) if a != b]
        assert diffs == [columns_result_index(3)]


def columns_result_index(round_no: int) -> int:
    from seebach.trf import columns

    return columns.result_index(round_no)


def test_recompute_points(round3_text: str) -> None:
    trf = parse(round3_text)
    set_result(trf, 3, 1, "1")
    out = serialize(trf, Dialect.TRF16, recompute_points=True)
    reparsed = parse(out)
    assert reparsed.player(1).points == 3.0
    assert reparsed.player(3).points == 1.5
    # Unplayed codes still carry their points.
    assert reparsed.player(4).points == pytest.approx(1.5)


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
