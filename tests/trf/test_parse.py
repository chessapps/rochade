import pytest

from rochade.trf import Colour, Dialect, TrfParseError, parse, serialize
from rochade.trf.model import TrfFile


def test_headers_are_read(round1_text: str) -> None:
    trf = parse(round1_text)
    assert trf.name == "Rochade Open 2026"
    assert trf.city == "Rochade"
    assert trf.federation == "SUI"
    assert trf.start_date == "2026/03/14"
    assert trf.chief_arbiter == "Muster, Anna"
    assert trf.declared_rounds == 5


def test_players_are_read(round1_text: str) -> None:
    trf = parse(round1_text)
    assert len(trf.players) == 8
    p = trf.player(3)
    assert p.name == "Dubois, Elise"
    assert p.title == "WFM"
    assert p.sex == "w"
    assert p.rating == 2098
    assert p.federation == "FRA"
    assert p.fide_id == "1300003"
    assert p.birth_date == "2001/07/09"
    assert p.points == 0.0
    assert p.rank == 3


def test_round_blocks_are_read(round3_text: str) -> None:
    trf = parse(round3_text)
    first = trf.player(1).round(1)
    assert first is not None
    assert (first.opponent, first.colour, first.result) == (5, Colour.WHITE, "1")

    bye = trf.player(4).round(1)
    assert bye is not None
    assert bye.opponent is None
    assert bye.colour is Colour.NONE
    assert bye.result == "H"


def test_pending_round_has_blank_results(round3_text: str) -> None:
    trf = parse(round3_text)
    playing = [p for p in trf.players.values() if (e := p.round(3)) and e.opponent is not None]
    assert len(playing) == 8
    assert all(p.round(3).result == " " for p in playing)
    # The withdrawn player carries a zero-point bye, not a blank.
    assert trf.player(9).round(3).result == "Z"
    assert trf.rounds_present == 3
    assert trf.round_count == 5


def test_declared_rounds_wins_over_rounds_present(round3_text: str) -> None:
    trf = parse(round3_text)
    assert trf.declared_rounds == 5
    assert trf.round_count == 5


def test_unknown_line_types_survive() -> None:
    text = "012 Test\r\n999 something we do not model\r\nXXR 3\r\n"
    trf = parse(text)
    assert serialize(trf, Dialect.TRF16) == text
    assert [line.code for line in trf.lines] == ["012", "999", "XXR"]


def test_unknown_result_code_is_reported_not_fatal() -> None:
    line = "001    1 m    A, B" + " " * 100
    line = line[:89] + "     2 w Q"
    trf = parse(line + "\r\n001    2 m    C, D" + " " * 71 + "     1 b Q\r\n")
    assert trf.unknown_result_codes == ["Q"]
    entry = trf.player(1).round(1)
    assert entry is not None and entry.result == "Q"


def test_player_line_without_rank_is_fatal() -> None:
    with pytest.raises(TrfParseError) as excinfo:
        parse("001      m    A, B\r\n")
    assert excinfo.value.line_no == 1


def test_duplicate_rank_is_fatal(round1_text: str) -> None:
    lines = round1_text.split("\r\n")
    doubled = "\r\n".join([*lines, lines[-2]])
    with pytest.raises(TrfParseError, match="duplicate starting rank"):
        parse(doubled)


def test_empty_file() -> None:
    trf = parse("")
    assert trf.players == {}
    assert isinstance(trf, TrfFile)


def test_bytes_input_falls_back_to_cp1252() -> None:
    trf = parse("012 Café".encode("cp1252", "replace"))
    assert trf.name.startswith("Cafe")
