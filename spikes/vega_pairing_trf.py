"""Turn the pairing Vega writes on disk into the TRF Rochade would hold.

Vega's FIDE rating report refuses to save while a paired round has no
results (seen 2026-09-11, 12.1.8: "In round 3 table 1 there is an unfinished
game. Please insert the result or no report will be saved"), so the round
Vega just paired never reaches us as a TRF. What Vega does write, at every
pairing, is `engine.man` in the tournament folder: one line with the number
of pairs, then `white black` start numbers per board in board order, the bye
as `black = 0`.

    python spikes/vega_pairing_trf.py spikes/out/m0-seed.trf spikes/out/engine.man \
        -o spikes/out/vega-round3.trf

reads the tournament as we last knew it, appends the paired round unplayed,
and writes the file `fill_results.py` expects -- the same state Swiss-Manager
hands over in its export.

Kept as the probe it was. The product does not read `engine.man`: it is the
engine's output and goes stale the moment the arbiter changes a board by hand
(seen 2026-09-11), while `SortedPairs.txt` beside it is rewritten. See
`rochade.interchange.formats.vega_text`.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from rochade.trf import Colour, RoundEntry, parse
from rochade.trf.build import BuildDocument, BuildPlayer, build


def read_man(path: pathlib.Path) -> list[tuple[int, int]]:
    lines = [ln.split() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    count = int(lines[0][0])
    pairs = [(int(a), int(b)) for a, b in lines[1 : 1 + count]]
    if len(pairs) != count:
        raise SystemExit(f"{path}: announced {count} pairs, found {len(pairs)}")
    return pairs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trf", type=pathlib.Path, help="the tournament as we last knew it")
    parser.add_argument("man", type=pathlib.Path, help="engine.man written by Vega")
    parser.add_argument("--round", type=int, default=None, help="defaults to the next round")
    parser.add_argument(
        "--rounds", type=int, default=None, help="XXR to write; defaults to the input's"
    )
    parser.add_argument("-o", "--out", type=pathlib.Path, required=True)
    args = parser.parse_args()

    known = parse(args.trf.read_bytes().decode("utf-8"))
    round_no = args.round or known.rounds_present + 1
    pairs = read_man(args.man)

    rounds: dict[int, dict[int, RoundEntry]] = {
        p.start_rank: dict(p.rounds) for p in known.players.values()
    }
    for white, black in pairs:
        if black == 0:
            rounds[white][round_no] = RoundEntry(round_no, None, Colour.NONE, "U")
            continue
        rounds[white][round_no] = RoundEntry(round_no, black, Colour.WHITE, " ")
        rounds[black][round_no] = RoundEntry(round_no, white, Colour.BLACK, " ")

    players = [
        BuildPlayer(
            start_rank=p.start_rank,
            name=p.name,
            sex=p.sex,
            title=p.title,
            rating=p.rating,
            federation=p.federation,
            fide_id=p.fide_id,
            birth_date=p.birth_date,
            rounds=rounds[p.start_rank],
        )
        for p in known.players.values()
    ]
    header = {line.code: line.raw[4:].strip() for line in known.lines if line.code != "001"}
    document = BuildDocument(
        name=header.get("012", ""),
        players=players,
        city=header.get("022", ""),
        federation=header.get("032", ""),
        start_date=header.get("042", ""),
        end_date=header.get("052", ""),
        declared_rounds=args.rounds or (int(header["XXR"]) if "XXR" in header else None),
    )
    args.out.write_text(build(document), encoding="utf-8", newline="")
    print(f"wrote {args.out}: round {round_no}, {len(pairs)} pairs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
