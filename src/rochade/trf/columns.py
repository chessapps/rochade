"""Fixed-column layout of the TRF `001` player line.

Slices are 0-based half-open; the comment gives the 1-based inclusive columns
the FIDE spec uses, because that is how every reference table is written.
"""

from typing import Final

CODE: Final = slice(0, 3)  # 1-3    record identifier
START_RANK: Final = slice(4, 8)  # 5-8    starting rank number
SEX: Final = slice(9, 10)  # 10     sex
TITLE: Final = slice(10, 13)  # 11-13  title
NAME: Final = slice(14, 47)  # 15-47  name
RATING: Final = slice(48, 52)  # 49-52  FIDE rating
FEDERATION: Final = slice(53, 56)  # 54-56 federation
FIDE_ID: Final = slice(57, 68)  # 58-68  FIDE number
BIRTH_DATE: Final = slice(69, 79)  # 70-79 birth date
POINTS: Final = slice(80, 84)  # 81-84  points
RANK: Final = slice(85, 89)  # 86-89  rank

ROUNDS_START: Final = 91  # 92     first round block
ROUND_WIDTH: Final = 10
OPPONENT_OFFSET: Final = 0  # 92-95  opponent starting rank
COLOUR_OFFSET: Final = 5  # 97     colour
RESULT_OFFSET: Final = 7  # 99     result

OPPONENT_WIDTH: Final = 4

#: Width of the line up to and including the last fixed field.
HEADER_WIDTH: Final = 89


def round_base(round_no: int) -> int:
    """0-based index where the 1-based `round_no` block starts."""
    if round_no < 1:
        raise ValueError(f"round number must be >= 1, got {round_no}")
    return ROUNDS_START + ROUND_WIDTH * (round_no - 1)


def opponent_slice(round_no: int) -> slice:
    base = round_base(round_no) + OPPONENT_OFFSET
    return slice(base, base + OPPONENT_WIDTH)


def colour_index(round_no: int) -> int:
    return round_base(round_no) + COLOUR_OFFSET


def result_index(round_no: int) -> int:
    return round_base(round_no) + RESULT_OFFSET
