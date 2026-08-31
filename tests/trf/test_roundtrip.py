"""Round-trip identity: parse -> serialize is byte-stable for untouched input.

This is the primary contract of the library. State bounces between Vega and us
every round, so anything we do not understand must come back out unchanged.
"""

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from seebach.trf import Dialect, parse, serialize

RESULTS = ["1", "=", "0", "+", "-", "W", "D", "L", " "]
BYE_RESULTS = ["H", "F", "U", "Z"]


def test_roundtrip_identity_pairings(round1_text: str) -> None:
    assert serialize(parse(round1_text), Dialect.TRF16) == round1_text


def test_roundtrip_identity_messy(round3_text: str) -> None:
    assert serialize(parse(round3_text), Dialect.TRF16) == round3_text


def test_roundtrip_preserves_unix_newlines(round1_text: str) -> None:
    unix = round1_text.replace("\r\n", "\n")
    assert serialize(parse(unix), Dialect.TRF16) == unix


def test_roundtrip_preserves_missing_trailing_newline(round1_text: str) -> None:
    trimmed = round1_text.rstrip("\r\n")
    assert serialize(parse(trimmed), Dialect.TRF16) == trimmed


def test_roundtrip_preserves_trailing_blank_trim(round1_text: str) -> None:
    """A pending result sitting past the end of a trimmed line stays trimmed."""
    trimmed = "\r\n".join(line.rstrip() for line in round1_text.split("\r\n"))
    assert serialize(parse(trimmed), Dialect.TRF16) == trimmed


def test_roundtrip_preserves_unmodelled_columns() -> None:
    """Columns we never parse -- here a trailing rating-change field -- survive."""
    line = (
        "001    1 m    Solo, Han                         2100 SUI     1300001 "
        "1990/01/01  0.0    1  0000 - U   SOMETHING WE DO NOT MODEL"
    )
    text = f"012 T\r\n{line}\r\nXXR 1\r\n"
    assert serialize(parse(text), Dialect.TRF16) == text


# --- property tests ---------------------------------------------------------

names = st.text(
    alphabet=st.characters(min_codepoint=32, max_codepoint=126, blacklist_characters=""),
    min_size=1,
    max_size=25,
)


@st.composite
def documents(draw: st.DrawFn) -> str:
    count = draw(st.integers(min_value=2, max_value=8))
    rounds = draw(st.integers(min_value=0, max_value=4))
    newline = draw(st.sampled_from(["\r\n", "\n"]))
    lines = [f"012 {draw(names)}", f"XXR {rounds}"]

    for rank in range(1, count + 1):
        line = list(" " * 89)
        line[0:3] = "001"
        line[4:8] = f"{rank:4d}"
        line[14:47] = draw(names).ljust(33)[:33]
        line[80:84] = f"{draw(st.floats(0, 9)):4.1f}"
        line[85:89] = f"{rank:4d}"
        raw = "".join(line)
        for _ in range(rounds):
            is_bye = draw(st.booleans())
            if is_bye:
                raw += "  0000 - " + draw(st.sampled_from(BYE_RESULTS))
            else:
                opp = draw(st.integers(1, count))
                raw += f"  {opp:4d} " + draw(st.sampled_from("wb")) + " "
                raw += draw(st.sampled_from(RESULTS))
        if draw(st.booleans()):
            raw = raw.rstrip()
        lines.append(raw)

    text = newline.join(lines)
    if draw(st.booleans()):
        text += newline
    return text


@given(documents())
@settings(max_examples=250, suppress_health_check=[HealthCheck.too_slow])
def test_roundtrip_is_byte_stable(text: str) -> None:
    assert serialize(parse(text), Dialect.TRF16) == text


@given(documents())
@settings(max_examples=100)
def test_parse_is_idempotent(text: str) -> None:
    once = serialize(parse(text), Dialect.TRF16)
    assert serialize(parse(once), Dialect.TRF16) == once
