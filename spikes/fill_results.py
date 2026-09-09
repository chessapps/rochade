"""M0 check 3, outbound half: produce the file we would hand back.

    python spikes/fill_results.py export.trf --all 1 -o filled.trf
    python spikes/fill_results.py export.trf --results "1:1,2:=,3:0" -o filled.trf

Goes through the real adapter, so what this writes is what the product writes.
Feed the output to the manager and see whether it merges -- that is the check.

Board numbers follow the FIDE order, which matched Swiss-Manager's pairing list; check
whether Vega prints the same before trusting them -- `inspect_export.py` shows
which board is which.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from rochade.interchange import ResultEntry, manager_for
from rochade.trf.results import RESULT_CODES


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=pathlib.Path)
    parser.add_argument("--manager", default="vega")
    parser.add_argument("--round", type=int, default=None, help="defaults to the open round")
    parser.add_argument("--all", dest="every", help="one code for every board, e.g. 1 or =")
    parser.add_argument("--results", help="per board, e.g. '1:1,2:=,3:0'")
    parser.add_argument("-o", "--out", type=pathlib.Path)
    args = parser.parse_args()

    manager = manager_for(args.manager)
    text = args.path.read_bytes().decode("utf-8", errors="replace")
    document = manager.read_round(text)

    round_no = args.round or (document.open_rounds[-1] if document.open_rounds else None)
    if round_no is None:
        print("No paired-but-unplayed round in this file, and no --round given.")
        print("Check 1 already failed; there is nothing to fill in.")
        return 1

    rows = {row.board: row for row in document.board_rows(round_no) if not row.is_bye}
    chosen = _chosen(args, sorted(rows))
    if not chosen:
        print("Nothing to write. Pass --all or --results.")
        return 2

    results = []
    for board, code in sorted(chosen.items()):
        row = rows.get(board)
        if row is None:
            print(f"  skip board {board}: not a played game in round {round_no}")
            continue
        if code not in RESULT_CODES:
            print(f"  skip board {board}: {code!r} is not a TRF result code")
            continue
        results.append(ResultEntry(white_rank=row.white_rank, white_result=code))
        print(f"  board {board}: {row.white_name} vs {row.black_name} -> {code!r}")

    dropped = manager.capabilities.drops([r.white_result for r in results])
    if dropped:
        print(f"\n  WARNING: {manager.label} cannot carry {dropped} -- they will be lost.")

    emitted = manager.write_results(document, round_no, results, stem=args.path.stem + "-filled")
    out = args.out or args.path.with_name(emitted.filename)
    out.write_text(emitted.content, encoding="utf-8", newline="")
    print(f"\nwrote {out}  ({len(results)} results into round {round_no})")
    print("Now import it into the manager. Check 3 is whether it merges.")
    return 0


def _chosen(args: argparse.Namespace, boards: list[int]) -> dict[int, str]:
    if args.every:
        return dict.fromkeys(boards, args.every)
    if not args.results:
        return {}
    chosen: dict[int, str] = {}
    for pair in args.results.split(","):
        board, _, code = pair.partition(":")
        chosen[int(board.strip())] = code.strip()
    return chosen


if __name__ == "__main__":
    raise SystemExit(main())
