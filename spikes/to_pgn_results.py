"""M0 check 3, the Swiss-Manager path: results as a headers-only PGN.

    python spikes/to_pgn_results.py export.trf --all 1 -o results.pgn

Swiss-Manager's version history lists no TRF *import* at all. What it does have
is `File / Import PGN-File (results)`, added 2021-07-20 "especially for online
tournaments" -- and that is how the wider ecosystem already feeds results back
into it. So if the TRF leg fails check 3, this is the next thing to try.

Throwaway on purpose. If M0 says PGN is the inbound format, this gets rewritten
properly as `interchange/formats/pgn.py` behind the manager port; it does not
graduate as-is.

**PGN loses things TRF carries.** There is no notation for a forfeit, a
half-point bye or a pairing-allocated bye -- only a game result. Every code
this drops is printed, because a silent downgrade at a real event is the
failure this whole design is trying to avoid.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from seebach.interchange import manager_for

#: What a TRF code becomes in PGN, and what that costs.
PGN_RESULT = {
    "1": ("1-0", None),
    "=": ("1/2-1/2", None),
    "0": ("0-1", None),
    "W": ("1-0", "unrated win becomes an ordinary win"),
    "D": ("1/2-1/2", "unrated draw becomes an ordinary draw"),
    "L": ("0-1", "unrated loss becomes an ordinary loss"),
    "+": ("1-0", "FORFEIT WIN becomes a played win -- the forfeit is lost"),
    "-": ("0-1", "FORFEIT LOSS becomes a played loss -- the forfeit is lost"),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=pathlib.Path)
    parser.add_argument("--manager", default="vega", help="adapter used to READ the file")
    parser.add_argument("--round", type=int, default=None)
    parser.add_argument("--all", dest="every", default="=", help="one code for every board")
    parser.add_argument("--event", default="")
    parser.add_argument("-o", "--out", type=pathlib.Path)
    args = parser.parse_args()

    document = manager_for(args.manager).read_round(
        args.path.read_bytes().decode("utf-8", errors="replace")
    )
    round_no = args.round or (document.open_rounds[-1] if document.open_rounds else None)
    if round_no is None:
        print("No paired-but-unplayed round, and no --round given.")
        return 1

    games: list[str] = []
    lost: list[str] = []
    for row in document.board_rows(round_no):
        if row.is_bye:
            lost.append(
                f"  board {row.board}: {row.white_name} has a bye -- PGN has no game for it"
            )
            continue
        mapped = PGN_RESULT.get(args.every)
        if mapped is None:
            print(f"{args.every!r} has no PGN equivalent at all.")
            return 2
        result, cost = mapped
        if cost:
            lost.append(f"  board {row.board}: {cost}")
        games.append(_game(args.event or document.tournament_name, round_no, row, result))

    text = "\n\n".join(games) + "\n"
    out = args.out or args.path.with_suffix(f".round{round_no}.pgn")
    out.write_text(text, encoding="utf-8")

    print(f"wrote {out}  ({len(games)} games)")
    if lost:
        print("\nWhat this format cannot carry:")
        print("\n".join(lost))
    print("\nNow try 'File / Import PGN-File (results)'. Check 3 is whether it merges.")
    return 0


def _game(event: str, round_no: int, row: object, result: str) -> str:
    tags = {
        "Event": event or "?",
        "Site": "?",
        "Date": "????.??.??",
        "Round": str(round_no),
        "Board": str(row.board),  # type: ignore[attr-defined]
        "White": row.white_name,  # type: ignore[attr-defined]
        "Black": row.black_name or "?",  # type: ignore[attr-defined]
        "Result": result,
    }
    header = "\n".join(f'[{key} "{value}"]' for key, value in tags.items())
    # A PGN game with no moves is its tags, a blank line, then the result token.
    return f"{header}\n\n{result}"


if __name__ == "__main__":
    raise SystemExit(main())
