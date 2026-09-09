"""M0 checks 1, 2, 4 and 7: what did the manager actually give us?

Throwaway. Point it at any file a tournament manager exported:

    python spikes/inspect_export.py path/to/export.trf
    python spikes/inspect_export.py path/to/export.trf --manager vega

It reads through the real adapter rather than a parallel copy, so a pass here
is evidence about the shipped code and not just about this script.

The headline it exists to answer is the cheap one that gates all the others:
does this file contain a round that has been PAIRED BUT NOT PLAYED? A FIDE
rating export describes completed games. If that is all we get, there is no
open board for anyone to enter and the loop cannot start, whatever the import
side turns out to support.
"""

from __future__ import annotations

import argparse
import pathlib
import sys
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from rochade.interchange import InterchangeError, RoundDocument, manager_for
from rochade.trf.results import RESULT_CODES

RECOGNISED = {"001", "012", "022", "032", "042", "052", "102", "XXR"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=pathlib.Path)
    parser.add_argument("--manager", default="vega", help="adapter to read through")
    args = parser.parse_args()

    raw = args.path.read_bytes()
    print(f"file            {args.path.name}  ({len(raw)} bytes)")
    print(f"encoding        {_encoding(raw)}")

    text = _decode(raw)
    print(f"line endings    {'CRLF' if chr(13) + chr(10) in text else 'LF'}")
    print(f"lines           {len(text.splitlines())}")
    print(f"adapter         {args.manager}")
    print()

    manager = manager_for(args.manager)
    try:
        document = manager.read_round(text)
    except InterchangeError as exc:
        print(f"READ FAILED     {exc}")
        print("  Check 2 fails. Nothing downstream can run.")
        return 1

    _records(text)
    _tournament(document)
    _rounds(document)
    _roundtrip(text, manager, document)
    _sample_line(text)
    return 0


def _encoding(raw: bytes) -> str:
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8 with BOM  <-- we strip nothing; check this survives the round trip"
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError:
        return "not utf-8 (cp1252 or latin-1)"
    return "utf-8"


def _decode(raw: bytes) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def _records(text: str) -> None:
    counts = Counter(line[:3] for line in text.splitlines() if line.strip())
    print("record types")
    for code, count in sorted(counts.items()):
        known = code in RECOGNISED
        note = "" if known else "  (retained verbatim, not modelled)"
        print(f"  {'read ' if known else 'kept '} {code!r:8} x{count}{note}")
    print()


def _tournament(document: RoundDocument) -> None:
    print("tournament")
    print(f"  name          {document.tournament_name!r}")
    print(f"  declared      {document.declared_rounds} rounds (XXR)")
    print(f"  rounds in file{document.rounds_present:>3}")
    print(f"  players       {len(document.players)}")
    if document.unknown_result_codes:
        print(f"  UNKNOWN CODES {document.unknown_result_codes}  <-- we do not model these")
    print()


def _rounds(document: RoundDocument) -> None:
    print("rounds")
    for round_no in range(1, document.rounds_present + 1):
        rows = document.board_rows(round_no)
        games = [r for r in rows if not r.is_bye]
        byes = [r for r in rows if r.is_bye]
        codes = Counter(r.white_result for r in games)
        print(
            f"  round {round_no}: {len(games)} games, {len(byes)} byes"
            f"  results={dict(codes)}  bye codes={sorted({r.white_result for r in byes})}"
        )
    print()

    print("CHECK 1 -- is there a paired-but-unplayed round?")
    if document.open_rounds:
        print(f"  YES: round(s) {document.open_rounds} have pairings and no results.")
        print("  That is the round players would enter. The loop can start.")
    else:
        print("  NO. Every round in this file already has results.")
        print("  We would import them all as CONFIRMED and there would be nothing to")
        print("  enter. Try exporting with the upcoming round selected; if the manager")
        print("  cannot do that, the outbound leg needs a different format.")
    print()


def _roundtrip(text: str, manager: object, document: RoundDocument) -> None:
    print("CHECK 4 -- lossless round trip on the untouched file")
    emitted = manager.write_results(document, document.rounds_present, [], stem="roundtrip")  # type: ignore[attr-defined]
    if emitted.content == text:
        print("  PASS: read -> write with no results is byte-identical.")
        print()
        return

    print("  DIFFERS. Every changed cell below is one we chose to write; anything")
    print("  else is a fidelity bug worth stopping for.")
    shown = 0
    for i, (a, b) in enumerate(
        zip(text.splitlines(), emitted.content.splitlines(), strict=False), 1
    ):
        if a == b or shown >= 5:
            continue
        cols = [j + 1 for j, (x, y) in enumerate(zip(a, b, strict=False)) if x != y]
        print(f"    line {i}, columns {cols}")
        print(f"      in : {a!r}")
        print(f"      out: {b!r}")
        shown += 1
    print()


def _sample_line(text: str) -> None:
    """Print one player row against a column ruler.

    TRF16 and TRF26 are both fixed-column formats. If a newer version moved a
    field, this is where it shows: check that rating, federation and the round
    blocks line up with the ruler.
    """
    row = next((line for line in text.splitlines() if line.startswith("001")), None)
    if row is None:
        return
    print("CHECK 7 -- column drift, one player row against the TRF16 ruler")
    print("  " + "".join(str((i // 10) % 10) for i in range(1, len(row) + 1)))
    print("  " + "".join(str(i % 10) for i in range(1, len(row) + 1)))
    print("  " + row)
    print()
    print("  expect: 5-8 rank | 10 sex | 11-13 title | 15-47 name | 49-52 rating")
    print("          54-56 fed | 58-68 FIDE id | 70-79 born | 81-84 points | 86-89 rank")
    print("          then 10-wide round blocks from 92: opponent 92-95, colour 97, result 99")
    print()
    print(f"  result codes we know: {' '.join(sorted(c for c in RESULT_CODES if c.strip()))}")


if __name__ == "__main__":
    raise SystemExit(main())
