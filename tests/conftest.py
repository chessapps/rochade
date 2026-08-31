import pathlib

import pytest

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> pathlib.Path:
    return FIXTURES


@pytest.fixture
def round1_text() -> str:
    return (FIXTURES / "round1_pairings.trf").read_bytes().decode("utf-8")


@pytest.fixture
def round3_text() -> str:
    return (FIXTURES / "round3_messy.trf").read_bytes().decode("utf-8")
