"""M0 check 5: two exports of the same tournament, and what moved between them.

    python spikes/compare_exports.py before.trf after.trf

The scenario this exists for: a late entrant arrives, the arbiter re-pairs in
the manager, and exports again. We need to be able to tell the new file from
the one we already hold and say exactly which boards changed -- because we may
be holding entered results for boards that no longer exist.

Deliberately matches the way the product does it: pairs of players, unordered,
never board numbers. Managers renumber boards when they re-pair, so a board
number is not an identity. This mirrors `pair_key` in
`features/imports/import_round.py`.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from seebach.interchange import RoundDocument, manager_for


def pair_key(white: str, black: str | None) -> tuple[str, ...]:
    return (white,) if black is None else tuple(sorted((white, black)))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=pathlib.Path)
    parser.add_argument("after", type=pathlib.Path)
    parser.add_argument("--manager", default="vega")
    parser.add_argument("--round", type=int, default=None)
    args = parser.parse_args()

    manager = manager_for(args.manager)
    before = manager.read_round(args.before.read_bytes().decode("utf-8", errors="replace"))
    after = manager.read_round(args.after.read_bytes().decode("utf-8", errors="replace"))

    print(f"before  round {before.rounds_present}, {len(before.players)} players")
    print(f"after   round {after.rounds_present}, {len(after.players)} players")
    print()

    _players(before, after)
    round_no = args.round or max(before.rounds_present, after.rounds_present)
    _pairings(before, after, round_no)
    _prior_results(before, after, round_no)
    return 0


def _players(before: RoundDocument, after: RoundDocument) -> None:
    old = {rank: p.name for rank, p in before.players.items()}
    new = {rank: p.name for rank, p in after.players.items()}

    print("players")
    for rank in sorted(set(new) - set(old)):
        print(f"  ADDED   {rank}: {new[rank]}")
    for rank in sorted(set(old) - set(new)):
        print(f"  GONE    {rank}: {old[rank]}")
    for rank in sorted(set(old) & set(new)):
        if old[rank] != new[rank]:
            print(f"  RENAMED {rank}: {old[rank]} -> {new[rank]}")
    if set(old) == set(new) and all(old[r] == new[r] for r in old):
        print("  unchanged")
    print()


def _pairings(before: RoundDocument, after: RoundDocument, round_no: int) -> None:
    old = {pair_key(r.white_name, r.black_name): r for r in before.board_rows(round_no)}
    new = {pair_key(r.white_name, r.black_name): r for r in after.board_rows(round_no)}

    print(f"round {round_no} pairings")
    for key in sorted(set(new) - set(old)):
        row = new[key]
        print(f"  NEW     board {row.board}: {row.white_name} vs {row.black_name or 'bye'}")
    for key in sorted(set(old) - set(new)):
        row = old[key]
        print(f"  DROPPED board {row.board}: {row.white_name} vs {row.black_name or 'bye'}")
        print("          any result entered here would be lost on re-import")
    for key in sorted(set(old) & set(new)):
        a, b = old[key], new[key]
        if a.board != b.board:
            print(
                f"  MOVED   {a.white_name} vs {a.black_name or 'bye'}: board {a.board} -> {b.board}"
            )
        elif a.white_name != b.white_name:
            print(
                f"  COLOURS swapped: {a.white_name} vs {a.black_name}"
                f" -> {b.white_name} vs {b.black_name}"
            )
    print()


def _prior_results(before: RoundDocument, after: RoundDocument, round_no: int) -> None:
    """A changed earlier result is normal -- the manager is authoritative.

    It must still be visible: an arbiter correcting round 2 after we exported it
    is exactly the divergence the import diff exists to surface.
    """
    print("earlier rounds")
    changed = False
    for earlier in range(1, round_no):
        old = {pair_key(r.white_name, r.black_name): r for r in before.board_rows(earlier)}
        for key, new_row in (
            (pair_key(r.white_name, r.black_name), r) for r in after.board_rows(earlier)
        ):
            old_row = old.get(key)
            if old_row is None or old_row.white_result == new_row.white_result:
                continue
            changed = True
            print(
                f"  round {earlier}: {new_row.white_name} vs {new_row.black_name or 'bye'} "
                f"{old_row.white_result!r} -> {new_row.white_result!r}"
            )
    if not changed:
        print("  unchanged")


if __name__ == "__main__":
    raise SystemExit(main())
