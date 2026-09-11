"""What Vega's importer needs that TRF16 does not say: byte columns and a `142` line."""

from __future__ import annotations

import pathlib

from rochade.trf import columns, parse
from rochade.vega import to_vega

VEGA = pathlib.Path(__file__).resolve().parents[1] / "fixtures" / "vega"


def read(name: str) -> str:
    return (VEGA / name).read_bytes().decode("utf-8")


def test_names_are_padded_to_33_bytes_not_33_characters() -> None:
    """The character-padded file hung Vega; the byte-padded one imported, umlauts intact."""
    hangs = read("accents_charpad_hangs_vega.trf")
    imported = read("accents_bytepad_imported.trf")
    assert to_vega(hangs, declared_rounds=None) == imported
    for line in imported.split("\r\n"):
        if line.startswith("001"):
            name_bytes = line.encode("utf-8")
            # Every field after the name sits where an ASCII reader expects it.
            assert name_bytes[columns.RATING] in (
                b"2201",
                b"2150",
                b"2098",
                b"2044",
                b"1987",
                b"1922",
                b"1870",
                b"1804",
                b"1755",
            )


def test_the_round_count_travels_as_142_and_xxr_is_left_alone() -> None:
    out = to_vega(read("accents_charpad_hangs_vega.trf"), declared_rounds=5)
    lines = out.split("\r\n")
    assert "142 5" in lines
    assert lines.index("142 5") < next(i for i, line in enumerate(lines) if line.startswith("001"))
    assert "XXR 5" in lines
    # Our own parser reads the same count from either line.
    assert parse(out).declared_rounds == 5


def test_an_existing_142_line_is_updated_rather_than_doubled() -> None:
    player = "001    1      A, B                              1000 SUI" + " " * 25 + "0.0    1"
    text = f"012 T\r\n142 3\r\n{player}\r\n"
    out = to_vega(text, declared_rounds=7)
    assert out.count("142 ") == 1 and "142 7" in out


def test_nothing_to_do_for_ascii_and_no_round_count() -> None:
    text = read("round3_filled_we_wrote.trf")
    assert to_vega(text, declared_rounds=None) == text
