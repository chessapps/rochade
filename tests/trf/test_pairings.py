from seebach.trf import parse


def test_pairings_deduplicate_the_two_player_rows(round1_text: str) -> None:
    trf = parse(round1_text)
    pairings = trf.pairings(1)
    assert len(pairings) == 4
    assert [(p.white, p.black) for p in pairings] == [(1, 5), (3, 7), (6, 2), (8, 4)]
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
