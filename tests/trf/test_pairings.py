import pathlib

from seebach.trf import parse

SM = pathlib.Path(__file__).resolve().parents[1] / "fixtures" / "swiss_manager"


def _sm_boards(path: str, round_no: int) -> list[tuple[int, int, int]]:
    """(board, white, black) as Swiss-Manager's own pairing file lists them."""
    rows = []
    for line in (SM / path).read_text(encoding="utf-8").splitlines()[1:]:
        rd, board, _, _, white, black, *_ = line.split(";")
        if int(rd) == round_no and int(black) != -1:
            rows.append((int(board), int(white), int(black)))
    return rows


def test_board_order_matches_swiss_manager_round3() -> None:
    """Round 3 as exported paired-but-unplayed; scores differ, so the FIDE order bites."""
    trf = parse((SM / "round3_paired.trf").read_bytes())
    ours = [(p.board, p.white, p.black) for p in trf.pairings(3) if not p.is_bye]
    assert ours == _sm_boards("pairings_round3_unplayed.txt", 3)


def test_board_order_matches_swiss_manager_round4() -> None:
    trf = parse((SM / "round4_paired.trf").read_bytes())
    ours = [(p.board, p.white, p.black) for p in trf.pairings(4) if not p.is_bye]
    assert ours == _sm_boards("pairings_rounds3-4_played.txt", 4)


def test_board_order_of_a_completed_round_uses_the_score_before_it() -> None:
    """Round 3 read from the round-4 export, where the points column includes round 3."""
    trf = parse((SM / "round4_paired.trf").read_bytes())
    ours = [(p.board, p.white, p.black) for p in trf.pairings(3) if not p.is_bye]
    assert ours == _sm_boards("pairings_rounds3-4_played.txt", 3)


def test_swiss_manager_round_count_comes_from_142() -> None:
    trf = parse((SM / "round3_paired.trf").read_bytes())
    assert trf.declared_rounds == 5
    assert trf.rounds_present == 3


def test_pairings_deduplicate_the_two_player_rows(round1_text: str) -> None:
    trf = parse(round1_text)
    pairings = trf.pairings(1)
    assert len(pairings) == 4
    # Round 1, nobody has points: boards go by the higher-ranked player.
    assert [(p.white, p.black) for p in pairings] == [(1, 5), (6, 2), (3, 7), (8, 4)]
    assert [p.board for p in pairings] == [1, 2, 3, 4]


def test_colour_orientation_is_respected(round1_text: str) -> None:
    trf = parse(round1_text)
    # Player 2 has black against 6, so the pairing must list 6 as white.
    board2 = next(p for p in trf.pairings(1) if 2 in (p.white, p.black))
    assert board2.white == 6
    assert board2.black == 2


def test_byes_sort_after_real_games(round3_text: str) -> None:
    trf = parse(round3_text)
    pairings = trf.pairings(1)
    real = [p for p in pairings if not p.is_bye]
    byes = [p for p in pairings if p.is_bye]
    assert [p.board for p in real] == list(range(1, len(real) + 1))
    assert [p.board for p in byes] == list(range(len(real) + 1, len(pairings) + 1))
    assert {p.white for p in byes} == {4, 8, 9}


def test_results_are_carried_from_both_sides(round3_text: str) -> None:
    trf = parse(round3_text)
    game = next(p for p in trf.pairings(2) if p.white == 5)
    assert (game.white, game.black) == (5, 7)
    assert (game.white_result, game.black_result) == ("+", "-")


def test_every_player_appears_exactly_once_per_round(round3_text: str) -> None:
    trf = parse(round3_text)
    for round_no in (1, 2, 3):
        seen = [r for p in trf.pairings(round_no) for r in (p.white, p.black) if r is not None]
        assert sorted(seen) == sorted(trf.players)


def test_board_order_third_key_is_the_higher_scorers_rank() -> None:
    """Built so that max and sum tie on two boards and only the third key decides.

    Boards 1v4 (scores ½ and 1½) and 2v3 (1½ and ½) tie on both. Swiss-Manager
    put 2v3 first -- rank 2 is the higher scorer there, rank 4 on the other --
    which is the FIDE rule and not "the lower of the two ranks".
    """
    trf = parse((SM / "tiebreak_probe_ours.trf").read_bytes())
    ours = [(p.board, p.white, p.black) for p in trf.pairings(3) if not p.is_bye]
    assert ours == _sm_boards("tiebreak_probe_pairings_by_sm.txt", 3)
    assert ours == [(1, 5, 8), (2, 2, 3), (3, 1, 4), (4, 6, 7)]
